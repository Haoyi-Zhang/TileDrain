"""Small exact oracle based on enumeration, not the least-cut formula."""
from itertools import permutations
from contracts import Instance


def all_forward_posets(n: int):
    edges = [(i, j) for j in range(n) for i in range(j)]
    seen = set()
    # Deliberately independent scalar Floyd-Warshall closure.
    for mask in range(1 << len(edges)):
        a = [[False] * n for _ in range(n)]
        for k, (i, j) in enumerate(edges):
            a[i][j] = bool(mask >> k & 1)
        for k in range(n):
            for i in range(n):
                for j in range(n):
                    a[i][j] = a[i][j] or (a[i][k] and a[k][j])
        p = tuple(sum((1 << i) for i in range(n) if a[i][j]) for j in range(n))
        if p not in seen:
            seen.add(p)
            yield p


def legal_sequence(seq: tuple[int, ...], p: tuple[int, ...]) -> bool:
    pos = {event: i for i, event in enumerate(seq)}
    return all(not (p[j] >> i & 1) or pos[i] < pos[j]
               for i in seq for j in seq)


def structural_cuts(p: tuple[int, ...], q: tuple[int, ...], lane: tuple[int, ...]):
    n = len(p)
    eligible = []
    destination_traces = 0
    for d in range(1 << n):
        ds = tuple(i for i in range(n) if d >> i & 1)
        rs = tuple(i for i in range(n) if not (d >> i & 1))
        # A drain must be a prefix of SOME full source linearization. No closure formula.
        drain_possible = False
        for seq in permutations(range(n)):
            if set(seq[:len(ds)]) == set(ds) and legal_sequence(seq, q):
                drain_possible = True
                break
        if not drain_possible:
            continue
        good = True
        for seq in permutations(rs):
            pos = {e: k for k, e in enumerate(seq)}
            if any(lane[i] == lane[j] and i < j and pos[i] > pos[j] for i in rs for j in rs):
                continue
            destination_traces += 1
            if not legal_sequence(seq, p):
                good = False
                break
        if good:
            eligible.append(d)
    return eligible, destination_traces


def feasible_from_structure(x: Instance, structural: list[int]) -> list[int]:
    feasible = []
    for d in structural:
        remaining = [i for i in range(x.n) if not (d >> i & 1)]
        if any(x.unsupported >> i & 1 for i in remaining):
            continue
        if any(sum(x.weight[i] for i in remaining if x.lane[i] == k) > cap
               for k, cap in enumerate(x.capacity)):
            continue
        feasible.append(d)
    return feasible
