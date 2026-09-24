"""Leastness diagnosis without source/FIFO alignment.

The algorithm asks at most n maximal-exclusion safety queries, then either
provides a least-cut certificate or two feasible cuts with infeasible meet.
It does not solve a minimum-cost knapsack when a least cut does not exist.
"""
from __future__ import annotations
from contracts import Instance, bits, _safe_admitted, verify


def upper(q: tuple[int, ...], e: int) -> int:
    return (1 << e) | sum(1 << j for j in range(e + 1, len(q)) if q[j] >> e & 1)


def analyze(x: Instance) -> dict:
    x.validate(aligned=False)
    all_events = (1 << x.n) - 1
    necessary = 0
    reasons = []
    feasible_exclusions = []
    missing = [(i, j) for j in range(x.n) for i in bits(x.p[j])
               if x.lane[i] != x.lane[j]]
    for e in range(x.n):
        up = upper(x.q, e)
        maximum_without_e = all_events ^ up
        if _safe_admitted(x, maximum_without_e):
            feasible_exclusions.append(maximum_without_e)
            continue
        necessary |= 1 << e
        unsupported_roots = up & x.unsupported
        if unsupported_roots:
            root = next(bits(unsupported_roots))
            reason = {'event': e, 'root': root, 'kind': 'unsupported'}
        else:
            order_root = next(((i, j) for i, j in missing if up >> i & 1), None)
            if order_root is not None:
                root, later = order_root
                reason = {'event': e, 'root': root, 'kind': 'order', 'later': later}
            else:
                lane = next(k for k, cap in enumerate(x.capacity)
                            if sum(x.weight[i] for i in bits(up) if x.lane[i] == k) > cap)
                reason = {'event': e, 'root': e, 'kind': 'cone_capacity', 'lane': lane}
        reasons.append(reason)
    if _safe_admitted(x, necessary):
        return {'kind': 'least', 'cut': {'drain': list(bits(necessary)), 'necessity': reasons}}
    a = all_events
    for b in feasible_exclusions:
        meet = a & b
        if not _safe_admitted(x, meet):
            return {'kind': 'no_least', 'left': list(bits(a)), 'right': list(bits(b))}
        a = meet
    raise AssertionError('the maximal-exclusion intersection must equal the forced set')


def _mask(value, n: int) -> int:
    if type(value) is not list or len(value) > n:
        raise ValueError('cut must be a bounded sorted list')
    if any(type(e) is not int or not 0 <= e < n for e in value):
        raise ValueError('invalid event identifier')
    if value != sorted(set(value)):
        raise ValueError('duplicate or unsorted event identifiers')
    return sum(1 << e for e in value)


def verify_analysis(x: Instance, cert: dict) -> bool:
    """Validate without running analyze or its maximal-exclusion algorithm."""
    try:
        x.validate(aligned=False)
        if type(cert) is not dict:
            return False
        if cert.get('kind') == 'least':
            return set(cert) == {'kind', 'cut'} and verify(x, cert['cut'])
        if cert.get('kind') == 'no_least':
            if set(cert) != {'kind', 'left', 'right'}:
                return False
            a, b = _mask(cert['left'], x.n), _mask(cert['right'], x.n)
            return _safe_admitted(x, a) and _safe_admitted(x, b) and not _safe_admitted(x, a & b)
        return False
    except (ValueError, TypeError, KeyError, IndexError, OverflowError):
        return False
