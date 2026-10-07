"""Exact cut certificates for sealed, event-distinguishing FIFO epochs.

All orders are strict and supplied in a common topological numbering.  This
module is not an ISA or hardware verifier.  See proofs/model.md for the contract.
Only the Python standard library is used.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

MAX_EVENTS = 512
MAX_INTEGER = 2**63 - 1


def bits(mask: int) -> Iterable[int]:
    while mask:
        low = mask & -mask
        yield low.bit_length() - 1
        mask ^= low


def closure(n: int, edges: Iterable[tuple[int, int]]) -> tuple[int, ...]:
    """Predecessor bitsets, including paths but excluding each vertex itself."""
    if type(n) is not int or not 0 <= n <= MAX_EVENTS:
        raise ValueError('event count outside the admitted grammar')
    pred = [0] * n
    for i, j in edges:
        if type(i) is not int or type(j) is not int or not 0 <= i < j < n:
            raise ValueError('edges require distinct, topologically numbered events')
        pred[j] |= 1 << i
    for j in range(n):
        for i in tuple(bits(pred[j])):
            pred[j] |= pred[i]
    return tuple(pred)


@dataclass(frozen=True)
class Instance:
    p: tuple[int, ...]
    q: tuple[int, ...]
    lane: tuple[int, ...]
    weight: tuple[int, ...]
    capacity: tuple[int, ...]
    unsupported: int = 0

    @property
    def n(self) -> int:
        return len(self.p)

    def validate(self, aligned: bool = True) -> None:
        n = self.n
        if n > MAX_EVENTS or len(self.q) != n or len(self.lane) != n or len(self.weight) != n:
            raise ValueError('inconsistent or excessive event count')
        if not self.capacity or len(self.capacity) > MAX_EVENTS:
            raise ValueError('one or more bounded lanes are required')
        if any(type(x) is not int or not 0 <= x <= MAX_INTEGER for x in self.capacity):
            raise ValueError('invalid lane capacity')
        if any(type(x) is not int or not 1 <= x <= MAX_INTEGER for x in self.weight):
            raise ValueError('event sizes must be positive bounded integers')
        if any(type(x) is not int or not 0 <= x < len(self.capacity) for x in self.lane):
            raise ValueError('invalid lane index')
        if type(self.unsupported) is not int or not 0 <= self.unsupported < (1 << n):
            raise ValueError('invalid unsupported-event mask')
        for rel in (self.p, self.q):
            for j, preds in enumerate(rel):
                if type(preds) is not int or not 0 <= preds < (1 << j):
                    raise ValueError('order is not strict and topologically numbered')
                for i in bits(preds):
                    if rel[i] & ~preds:
                        raise ValueError('order is not transitively closed')
        if any(a & ~b for a, b in zip(self.p, self.q)):
            raise ValueError('source order must extend the virtual order')
        if aligned:
            for j in range(n):
                for i in range(j):
                    if self.lane[i] == self.lane[j] and not (self.q[j] >> i & 1):
                        raise ValueError('a native lane must be a chain of the source drain order')


def lower_closure(q: tuple[int, ...], mask: int) -> int:
    out = mask
    for i in bits(mask):
        out |= q[i]
    return out


def mandatory_roots(x: Instance) -> dict[int, dict]:
    roots: dict[int, dict] = {}
    for i in bits(x.unsupported):
        roots[i] = {'kind': 'unsupported', 'root': i}
    for j in range(x.n):
        for i in bits(x.p[j]):
            if x.lane[i] != x.lane[j]:
                roots.setdefault(i, {'kind': 'order', 'root': i, 'later': j})
    for lane, capacity in enumerate(x.capacity):
        queue = [i for i in range(x.n) if x.lane[i] == lane]
        remaining = sum(x.weight[i] for i in queue)
        for i in queue:
            if remaining <= capacity:
                break
            roots.setdefault(i, {'kind': 'capacity', 'root': i})
            remaining -= x.weight[i]
    return roots


def synthesize(x: Instance) -> dict:
    x.validate()
    roots = mandatory_roots(x)
    d = lower_closure(x.q, sum(1 << i for i in roots))
    reasons = []
    for e in bits(d):
        root = next(r for r in roots if r == e or x.q[r] >> e & 1)
        reasons.append({'event': e, **roots[root]})
    return {'drain': list(bits(d)), 'necessity': reasons}


def safe(x: Instance, d: int) -> bool:
    """Check postconditions directly; does not call the synthesis algorithm."""
    x.validate(aligned=False)
    return _safe_admitted(x, d)


def _safe_admitted(x: Instance, d: int) -> bool:
    """Pure postconditions, called only after the immutable instance is validated."""
    if type(d) is not int or not 0 <= d < (1 << x.n):
        return False
    if any(x.q[e] & ~d for e in bits(d)) or x.unsupported & ~d:
        return False
    loads = [0] * len(x.capacity)
    for i in bits(((1 << x.n) - 1) ^ d):
        loads[x.lane[i]] += x.weight[i]
    if any(load > cap for load, cap in zip(loads, x.capacity)):
        return False
    for j in range(x.n):
        if d >> j & 1:
            continue
        for i in bits(x.p[j] & ~d):
            if x.lane[i] != x.lane[j]:
                return False
    return True


def verify(x: Instance, cert: dict, require_least: bool = True) -> bool:
    """Separate certificate validator: safety plus per-event lower bounds.

    Neither mandatory_roots nor synthesize is called by this validator.  Invalid
    metadata is rejected, rather than repaired or interpreted permissively.
    """
    try:
        x.validate(aligned=False)
        if type(cert) is not dict or set(cert) != {'drain', 'necessity'}:
            return False
        drain, reasons = cert['drain'], cert['necessity']
        if type(drain) is not list or any(type(e) is not int or not 0 <= e < x.n for e in drain):
            return False
        if drain != sorted(set(drain)):
            return False
        d = sum(1 << e for e in drain)
        if not _safe_admitted(x, d):
            return False
        if not require_least:
            return True
        if type(reasons) is not list or len(reasons) != len(drain):
            return False
        explained = set()
        for reason in reasons:
            if type(reason) is not dict:
                return False
            e, r, kind = reason.get('event'), reason.get('root'), reason.get('kind')
            if type(e) is not int or type(r) is not int or not 0 <= r < x.n:
                return False
            if e not in drain or e in explained or not (d >> r & 1):
                return False
            if e != r and not (x.q[r] >> e & 1):
                return False
            if kind == 'unsupported':
                if set(reason) != {'event', 'root', 'kind'} or not (x.unsupported >> r & 1):
                    return False
            elif kind == 'order':
                j = reason.get('later')
                if set(reason) != {'event', 'root', 'kind', 'later'}:
                    return False
                if type(j) is not int or not 0 <= j < x.n or not (x.p[j] >> r & 1) or x.lane[r] == x.lane[j]:
                    return False
            elif kind == 'capacity':
                if set(reason) != {'event', 'root', 'kind'}:
                    return False
                # A suffix is forced only when it lies in the root's Q-upset.
                if any(x.lane[i] == x.lane[r] and i > r and not (x.q[i] >> r & 1)
                       for i in range(x.n)):
                    return False
                suffix = sum(x.weight[i] for i in range(r, x.n) if x.lane[i] == x.lane[r])
                if suffix <= x.capacity[x.lane[r]]:
                    return False
            elif kind == 'cone_capacity':
                lane = reason.get('lane')
                if set(reason) != {'event', 'root', 'kind', 'lane'}:
                    return False
                if type(lane) is not int or not 0 <= lane < len(x.capacity):
                    return False
                forced_remaining = sum(x.weight[i] for i in range(x.n)
                                       if x.lane[i] == lane and (i == r or x.q[i] >> r & 1))
                if forced_remaining <= x.capacity[lane]:
                    return False
            else:
                return False
            explained.add(e)
        return explained == set(drain)
    except (ValueError, TypeError, KeyError, IndexError, OverflowError):
        return False
