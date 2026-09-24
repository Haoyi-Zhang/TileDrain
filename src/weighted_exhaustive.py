"""Complete weighted microdomain through three events.

For n=0..3, enumerate every naturally numbered P subset Q, two-lane
assignment, unsupported mask, event-size vector in {1,2}^n, and every capacity
from zero through each lane's full load.  The production analyzer is compared
with the independent permutation/interleaving oracle and the independent
certificate validator.  Capacity-universal groups are also checked against the
residual-chain criterion and the constructive obstruction.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import itertools
import json
import resource
import time
from pathlib import Path

from contracts import Instance, verify
from general import analyze, verify_analysis
from independent import independent_verify_analysis
from oracle import all_forward_posets, structural_cuts, feasible_from_structure
from robust import effectively_aligned, obstruction_capacity, synthesize_effective


def run(out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    by_n: list[dict] = []
    group_path = out / 'weighted-exhaustive-groups.csv.gz'
    with gzip.open(group_path, 'wt', newline='') as raw:
        writer = csv.writer(raw)
        writer.writerow([
            'n', 'p_index', 'q_index', 'lane_bits', 'unsupported', 'weight_code',
            'capacity_instances', 'all_least', 'effective_alignment',
            'obstruction_capacity_0', 'obstruction_capacity_1'
        ])
        for n in range(4):
            ps = list(all_forward_posets(n))
            stats = dict(
                n=n, fixed_weighted_contracts=0, capacity_instances=0,
                least=0, no_least=0, robust_contracts=0,
                obstruction_contracts=0, oracle_mismatches=0,
                production_certificate_failures=0,
                independent_certificate_failures=0,
                effective_certificate_failures=0,
                destination_traces_examined=0,
            )
            for pi, p in enumerate(ps):
                for qi, q in enumerate(ps):
                    if any(a & ~b for a, b in zip(p, q)):
                        continue
                    for lane in itertools.product(range(2), repeat=n):
                        structural, traces = structural_cuts(p, q, lane)
                        stats['destination_traces_examined'] += traces
                        lane_bits = sum(lane[e] << e for e in range(n))
                        for unsupported in range(1 << n):
                            for weight in itertools.product((1, 2), repeat=n):
                                loads = tuple(sum(weight[e] for e in range(n) if lane[e] == l) for l in range(2))
                                all_least = True
                                capacity_count = 0
                                full = Instance(p, q, lane, weight, loads, unsupported)
                                effective = effectively_aligned(full)
                                for capacity in itertools.product(*(range(load + 1) for load in loads)):
                                    x = Instance(p, q, lane, weight, capacity, unsupported)
                                    feasible = feasible_from_structure(x, structural)
                                    if not feasible:
                                        raise AssertionError('all-event drain missing from oracle')
                                    meet = (1 << n) - 1
                                    for drain in feasible:
                                        meet &= drain
                                    oracle_least = meet in feasible
                                    cert = analyze(x)
                                    if (cert['kind'] == 'least') != oracle_least:
                                        stats['oracle_mismatches'] += 1
                                        raise AssertionError(('weighted leastness mismatch', n, pi, qi, lane, unsupported, weight, capacity))
                                    if oracle_least:
                                        selected = sum(1 << e for e in cert['cut']['drain'])
                                        if selected != meet:
                                            stats['oracle_mismatches'] += 1
                                            raise AssertionError('weighted least cut differs from oracle meet')
                                        stats['least'] += 1
                                    else:
                                        stats['no_least'] += 1
                                    if not verify_analysis(x, cert):
                                        stats['production_certificate_failures'] += 1
                                        raise AssertionError('production certificate rejected')
                                    if not independent_verify_analysis(x, cert):
                                        stats['independent_certificate_failures'] += 1
                                        raise AssertionError('independent certificate rejected')
                                    if effective:
                                        fast = synthesize_effective(x)
                                        if not oracle_least or sum(1 << e for e in fast['drain']) != meet or not verify(x, fast):
                                            stats['effective_certificate_failures'] += 1
                                            raise AssertionError('effective weighted certificate mismatch')
                                    all_least &= oracle_least
                                    capacity_count += 1
                                    stats['capacity_instances'] += 1
                                if all_least != effective:
                                    raise AssertionError('weighted capacity-universal criterion mismatch')
                                obstruction = obstruction_capacity(full)
                                if effective:
                                    stats['robust_contracts'] += 1
                                    if obstruction is not None:
                                        raise AssertionError('robust weighted contract has obstruction')
                                    ob = (-1, -1)
                                else:
                                    stats['obstruction_contracts'] += 1
                                    if obstruction is None or any(obstruction[l] > loads[l] for l in range(2)):
                                        raise AssertionError('non-robust weighted contract lacks in-domain obstruction')
                                    y = Instance(p, q, lane, weight, obstruction, unsupported)
                                    witness = analyze(y)
                                    if witness['kind'] != 'no_least' or not independent_verify_analysis(y, witness):
                                        raise AssertionError('weighted obstruction certificate failure')
                                    ob = obstruction
                                stats['fixed_weighted_contracts'] += 1
                                writer.writerow([
                                    n, pi, qi, lane_bits, unsupported,
                                    ''.join(str(v) for v in weight), capacity_count,
                                    int(all_least), int(effective), *ob
                                ])
            if stats['fixed_weighted_contracts'] != stats['robust_contracts'] + stats['obstruction_contracts']:
                raise AssertionError('weighted group accounting mismatch')
            if stats['capacity_instances'] != stats['least'] + stats['no_least']:
                raise AssertionError('weighted instance accounting mismatch')
            by_n.append(stats)
    total_keys = [k for k in by_n[0] if k != 'n']
    totals = {k: sum(row[k] for row in by_n) for k in total_keys}
    return {
        'suite': 'weighted-exhaustive',
        'event_range': [0, 1, 2, 3],
        'event_sizes': [1, 2],
        'lanes': 2,
        'by_n': by_n,
        'totals': totals,
        'scope': 'Complete generated microdomain; finite checking, not a proof over unbounded weights or event counts.',
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (3 * 1024**3, 3 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (40, 40))
    cpu = time.process_time()
    wall = time.perf_counter()
    result = run(args.output)
    result.update(
        cpu_seconds=time.process_time() - cpu,
        wall_seconds=time.perf_counter() - wall,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        workers=1,
    )
    (args.output / 'weighted-exhaustive.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
