"""Capacity-robust source/FIFO alignment after mandatory completion.

The theorem is relative to fixed P, Q, lane assignment, unsupported set and
positive sizes. Capacities alone vary. See proofs/model.md.
"""
from __future__ import annotations
from contracts import Instance, bits, lower_closure


def noncapacity_roots(x: Instance) -> dict[int, dict]:
    roots = {e: {'kind': 'unsupported', 'root': e} for e in bits(x.unsupported)}
    for later in range(x.n):
        for root in bits(x.p[later]):
            if x.lane[root] != x.lane[later]:
                roots.setdefault(root, {'kind': 'order', 'root': root, 'later': later})
    return roots


def mandatory_mask(x: Instance) -> int:
    return lower_closure(x.q, sum(1 << e for e in noncapacity_roots(x)))


def effectively_aligned(x: Instance) -> bool:
    x.validate(aligned=False)
    b = mandatory_mask(x)
    return all(x.lane[i] != x.lane[j] or x.q[j] >> i & 1
               for j in range(x.n) if not (b >> j & 1)
               for i in range(j) if not (b >> i & 1))


def synthesize_effective(x: Instance) -> dict:
    x.validate(aligned=False)
    roots = noncapacity_roots(x)
    b = lower_closure(x.q, sum(1 << e for e in roots))
    for lane, capacity in enumerate(x.capacity):
        queue = [e for e in range(x.n) if x.lane[e] == lane and not (b >> e & 1)]
        if any(not (x.q[j] >> i & 1) for t, j in enumerate(queue) for i in queue[:t]):
            raise ValueError('a surviving lane is not a source-order chain')
        remaining = sum(x.weight[e] for e in queue)
        for e in queue:
            if remaining <= capacity:
                break
            roots.setdefault(e, {'kind': 'cone_capacity', 'root': e, 'lane': lane})
            remaining -= x.weight[e]
    d = lower_closure(x.q, sum(1 << e for e in roots))
    reasons = []
    for e in bits(d):
        root = next(r for r in roots if r == e or x.q[r] >> e & 1)
        reasons.append({'event': e, **roots[root]})
    return {'drain': list(bits(d)), 'necessity': reasons}


def obstruction_capacity(x: Instance) -> tuple[int, ...] | None:
    """Return an integer capacity vector with no least cut, or None if robust.

    Full lane loads are allowed mathematically; a returned capacity beyond the
    implementation's scalar bound is rejected explicitly by Instance.validate.
    The consumed experimental inputs are small enough to remain in the grammar.
    """
    x.validate(aligned=False)
    b = mandatory_mask(x)
    queues = [[e for e in range(x.n) if x.lane[e] == lane and not (b >> e & 1)]
              for lane in range(len(x.capacity))]
    capacities = [sum(x.weight[e] for e in queue) for queue in queues]
    for lane, queue in enumerate(queues):
        tail = set(queue)
        while tail:
            minima = [e for e in sorted(tail) if not any(x.q[e] >> f & 1 for f in tail)]
            if len(minima) > 1:
                capacities[lane] = max(sum(x.weight[f] for f in tail
                                          if f == e or x.q[f] >> e & 1) for e in tail)
                if capacities[lane] >= sum(x.weight[e] for e in tail):
                    raise AssertionError('positive-size fork must have a proper upper cone')
                result = tuple(capacities)
                Instance(x.p, x.q, x.lane, x.weight, result, x.unsupported).validate(False)
                return result
            if not minima:
                raise AssertionError('finite strict order must have a minimal element')
            tail.remove(minima[0])
    return None
