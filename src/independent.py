"""Independent certificate checks from primitive contract fields.

This module intentionally does not call the analyzer, the aligned synthesizer,
``contracts.safe``, ``contracts._safe_admitted``, or ``contracts.verify``.
It duplicates the small admission and postcondition checks with ordinary sets
and loops so that exhaustive campaigns can detect implementation coupling.
"""
from __future__ import annotations
from typing import Any

MAX_EVENTS = 512
MAX_INTEGER = 2**63 - 1


def _predecessors(mask: int) -> set[int]:
    out: set[int] = set()
    bit = 0
    while mask:
        if mask & 1:
            out.add(bit)
        bit += 1
        mask >>= 1
    return out


def _validate_instance(x: Any) -> bool:
    try:
        p, q, lane, weight, capacity = x.p, x.q, x.lane, x.weight, x.capacity
        n = len(p)
        if not 0 <= n <= MAX_EVENTS:
            return False
        if not all(type(v) is tuple for v in (p, q, lane, weight, capacity)):
            return False
        if len(q) != n or len(lane) != n or len(weight) != n:
            return False
        if not 1 <= len(capacity) <= MAX_EVENTS:
            return False
        if any(type(v) is not int or not 0 <= v <= MAX_INTEGER for v in capacity):
            return False
        if any(type(v) is not int or not 1 <= v <= MAX_INTEGER for v in weight):
            return False
        if any(type(v) is not int or not 0 <= v < len(capacity) for v in lane):
            return False
        unsupported = x.unsupported
        if type(unsupported) is not int or not 0 <= unsupported < (1 << n):
            return False
        for rel in (p, q):
            for j, preds in enumerate(rel):
                if type(preds) is not int or not 0 <= preds < (1 << j):
                    return False
                pred_set = _predecessors(preds)
                # Transitive closure: every predecessor's predecessors occur too.
                if any(_predecessors(rel[i]) - pred_set for i in pred_set):
                    return False
        if any(p[j] & ~q[j] for j in range(n)):
            return False
        return True
    except (AttributeError, TypeError, ValueError, OverflowError):
        return False


def _mask(events: Any, n: int) -> int | None:
    # Validate the bounded JSON list and every scalar before any operation
    # (sorting or hashing) that assumes homogeneous, hashable integers.
    if type(events) is not list or len(events) > n:
        return None
    if any(type(e) is not int or not 0 <= e < n for e in events):
        return None
    if len(events) != len(set(events)) or events != sorted(events):
        return None
    return sum(1 << e for e in events)


def independent_safe(x: Any, drain: int) -> bool:
    """Recompute all finite postconditions without the production checker."""
    if not _validate_instance(x):
        return False
    n = len(x.p)
    if type(drain) is not int or not 0 <= drain < (1 << n):
        return False
    drained = {e for e in range(n) if drain >> e & 1}
    residual = set(range(n)) - drained

    # The source drain must be a Q-ideal.
    for e in drained:
        if _predecessors(x.q[e]) - drained:
            return False
    if any(x.unsupported >> e & 1 for e in residual):
        return False
    for l, cap in enumerate(x.capacity):
        total = sum(x.weight[e] for e in residual if x.lane[e] == l)
        if total > cap:
            return False
    # Within-lane order follows the common topological numbering.  Every
    # residual required pair on different lanes would admit a reversing FIFO
    # interleaving and is therefore forbidden.
    for later in residual:
        for earlier in _predecessors(x.p[later]) & residual:
            if x.lane[earlier] != x.lane[later]:
                return False
    return True


def _precedes_or_equals(x: Any, event: int, root: int) -> bool:
    return event == root or bool(x.q[root] >> event & 1)


def independent_verify_cut(x: Any, cert: Any, require_least: bool = True) -> bool:
    if not _validate_instance(x) or type(cert) is not dict or set(cert) != {'drain', 'necessity'}:
        return False
    drain = _mask(cert.get('drain'), len(x.p))
    if drain is None or not independent_safe(x, drain):
        return False
    if not require_least:
        return True
    reasons = cert.get('necessity')
    if type(reasons) is not list or len(reasons) != len(cert['drain']):
        return False
    explained: set[int] = set()
    for reason in reasons:
        if type(reason) is not dict:
            return False
        event, root, kind = reason.get('event'), reason.get('root'), reason.get('kind')
        if type(event) is not int or type(root) is not int:
            return False
        if event not in cert['drain'] or event in explained or not 0 <= root < len(x.p):
            return False
        if not _precedes_or_equals(x, event, root):
            return False
        if kind == 'unsupported':
            if set(reason) != {'event', 'root', 'kind'} or not (x.unsupported >> root & 1):
                return False
        elif kind == 'order':
            if set(reason) != {'event', 'root', 'kind', 'later'}:
                return False
            later = reason.get('later')
            if type(later) is not int or not 0 <= later < len(x.p):
                return False
            if not (x.p[later] >> root & 1) or x.lane[root] == x.lane[later]:
                return False
        elif kind == 'cone_capacity':
            if set(reason) != {'event', 'root', 'kind', 'lane'}:
                return False
            l = reason.get('lane')
            if type(l) is not int or not 0 <= l < len(x.capacity):
                return False
            cone_load = sum(
                x.weight[e]
                for e in range(len(x.p))
                if x.lane[e] == l and (e == root or x.q[e] >> root & 1)
            )
            if cone_load <= x.capacity[l]:
                return False
        elif kind == 'capacity':
            if set(reason) != {'event', 'root', 'kind'}:
                return False
            l = x.lane[root]
            # This legacy reason is valid only for a fully Q-aligned lane.
            same_lane_after = [e for e in range(root + 1, len(x.p)) if x.lane[e] == l]
            if any(not (x.q[e] >> root & 1) for e in same_lane_after):
                return False
            suffix_load = sum(x.weight[e] for e in range(root, len(x.p)) if x.lane[e] == l)
            if suffix_load <= x.capacity[l]:
                return False
        else:
            return False
        explained.add(event)
    return explained == set(cert['drain'])


def independent_verify_analysis(x: Any, cert: Any) -> bool:
    """Validate a least or no-least outcome without the production verifier."""
    if not _validate_instance(x) or type(cert) is not dict:
        return False
    if cert.get('kind') == 'least':
        return set(cert) == {'kind', 'cut'} and independent_verify_cut(x, cert.get('cut'))
    if cert.get('kind') == 'no_least':
        if set(cert) != {'kind', 'left', 'right'}:
            return False
        left = _mask(cert.get('left'), len(x.p))
        right = _mask(cert.get('right'), len(x.p))
        if left is None or right is None:
            return False
        return independent_safe(x, left) and independent_safe(x, right) and not independent_safe(x, left & right)
    return False
