"""Separately invoked finite regression; no timing, external input or POSIX runner.

The test-local reference enumerates source prefixes and destination FIFO
interleavings, not the production safety formula. Its per-lane scalar sums
remain independent of the optimized one-pass aggregation.
"""
from copy import deepcopy
from itertools import permutations, product
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from contracts import Instance, MAX_INTEGER, _safe_admitted, safe
from general import analyze, verify_analysis
from independent import independent_safe, independent_verify_analysis
from inputs import instance_from_dict
from mutations import run_controls


def legal(trace, relation):
    positions = {e: i for i, e in enumerate(trace)}
    return all(positions[i] < positions[j]
               for j in trace for i in trace if relation[j] >> i & 1)


def reference_family(x):
    """Enumerate permitted source prefixes and every retained FIFO interleaving."""
    if x.n > 6:
        raise ValueError('permutation reference is bounded to six events')
    prefixes = set()
    for trace in permutations(range(x.n)):
        if legal(trace, x.q):
            for length in range(x.n + 1):
                prefixes.add(sum(1 << e for e in trace[:length]))
    family = []
    for drain in sorted(prefixes):
        retained = tuple(e for e in range(x.n) if not (drain >> e & 1))
        if any(x.unsupported >> e & 1 for e in retained):
            continue
        if any(sum(x.weight[e] for e in retained if x.lane[e] == lane) > cap
               for lane, cap in enumerate(x.capacity)):
            continue
        good = True
        for trace in permutations(retained):
            fifo = all(tuple(e for e in trace if x.lane[e] == lane) ==
                       tuple(e for e in retained if x.lane[e] == lane)
                       for lane in set(x.lane))
            if fifo and not legal(trace, x.p):
                good = False
                break
        if good:
            family.append(drain)
    return family


def microdomain():
    """Complete n=0..2, two lanes, sizes {1,2}, every full-load-bounded capacity."""
    for n in range(3):
        orders = ((0, 0), (0, 1)) if n == 2 else ((0,) * n,)
        for p, q in product(orders, repeat=2):
            if any(a & ~b for a, b in zip(p, q)):
                continue
            for lane in product(range(2), repeat=n):
                for unsupported in range(1 << n):
                    for weight in product((1, 2), repeat=n):
                        full = tuple(sum(weight[e] for e in range(n) if lane[e] == l)
                                     for l in range(2))
                        for capacity in product(*(range(load + 1) for load in full)):
                            yield Instance(p, q, lane, weight, capacity, unsupported)


def boundary_instances():
    m = MAX_INTEGER
    examples = [
        Instance((), (), (), (), (0,) * 512),
        Instance((0,), (0,), (511,), (m,), (0,) * 511 + (m,)),
        Instance((0, 0), (0, 1), (0, 0), (m, m), (m,)),
        Instance((0, 0, 0), (0, 0, 3), (0, 0, 0), (m, m, m), (m,)),
        Instance((0, 1), (0, 1), (0, 1), (1, 2), (0, 0), 2),
        Instance((0, 0, 0), (0, 1, 3), (0, 1, 0), (1, 2, 3), (4, 2)),
    ]
    for name in ('example.json', 'fork.json'):
        examples.append(instance_from_dict(json.loads((ROOT / 'inputs' / name).read_text())))
    return examples


def frozen_instances():
    rows = json.loads((ROOT / 'inputs' / 'weighted.json').read_text())[:16]
    if [r['case'] for r in rows] != [f'weighted-{i:04d}' for i in range(16)]:
        raise AssertionError('expected the first sixteen frozen cases')
    return [instance_from_dict(row['instance']) for row in rows]


def check_instance(test, x):
    x.validate(False)
    family = reference_family(x)
    test.assertTrue(family)
    for drain in range(1 << x.n):
        expected = drain in family
        test.assertEqual(_safe_admitted(x, drain), expected)
        test.assertEqual(safe(x, drain), expected)
        test.assertEqual(independent_safe(x, drain), expected)
    cert = analyze(x)
    test.assertTrue(verify_analysis(x, cert))
    test.assertTrue(independent_verify_analysis(x, cert))
    meet = (1 << x.n) - 1
    for drain in family:
        meet &= drain
    test.assertEqual(cert['kind'] == 'least', meet in family)
    if cert['kind'] == 'least':
        test.assertEqual(sum(1 << e for e in cert['cut']['drain']), meet)
        if cert['cut']['drain']:
            bad = deepcopy(cert)
            bad['cut']['necessity'] = []
            test.assertFalse(verify_analysis(x, bad))
            test.assertFalse(independent_verify_analysis(x, bad))
    else:
        a = sum(1 << e for e in cert['left'])
        b = sum(1 << e for e in cert['right'])
        test.assertIn(a, family)
        test.assertIn(b, family)
        test.assertNotIn(a & b, family)
        bad = deepcopy(cert)
        bad['right'] = bad['left'][:]
        test.assertFalse(verify_analysis(x, bad))
        test.assertFalse(independent_verify_analysis(x, bad))


class LaneLoadRegression(unittest.TestCase):
    def test_complete_weighted_microdomain(self):
        count = masks = 0
        for x in microdomain():
            check_instance(self, x)
            count += 1
            masks += 1 << x.n
        self.assertEqual((count, masks), (1005, 3977))

    def test_eight_boundaries_and_paper_examples(self):
        examples = boundary_instances()
        self.assertEqual(len(examples), 8)
        for x in examples:
            check_instance(self, x)

    def test_first_sixteen_frozen_five_event_cases(self):
        for x in frozen_instances():
            self.assertEqual(x.n, 5)
            check_instance(self, x)

    def test_maximum_events_lanes_and_nonwrapping_loads(self):
        n = 512
        full = (1 << n) - 1
        spread = Instance((0,) * n, (0,) * n, tuple(range(n)),
                          (MAX_INTEGER,) * n, (MAX_INTEGER,) * n)
        packed = Instance((0,) * n, (0,) * n, (0,) * n,
                          (MAX_INTEGER,) * n, (MAX_INTEGER,))
        for x, drain, expected in ((spread, 0, True), (spread, full, True),
                                  (packed, 0, False), (packed, full ^ (1 << 511), True),
                                  (packed, full, True)):
            self.assertEqual(safe(x, drain), expected)
            self.assertEqual(independent_safe(x, drain), expected)

    def test_guard_priority_and_mask_grammar(self):
        x = boundary_instances()[4]
        for bad in (-1, True, False, 4, None, '0', 0.0):
            self.assertFalse(_safe_admitted(x, bad))
            self.assertFalse(safe(x, bad))
            self.assertFalse(independent_safe(x, bad))
        self.assertEqual(analyze(x), {'kind': 'least', 'cut': {
            'drain': [0, 1], 'necessity': [
                {'event': 0, 'root': 1, 'kind': 'unsupported'},
                {'event': 1, 'root': 1, 'kind': 'unsupported'},
            ]}})

    def test_declared_controls_remain_thirty_one(self):
        rows = run_controls()
        self.assertEqual(len(rows), 31)
        self.assertTrue(all(row['expected'] == row['actual'] for row in rows))


if __name__ == '__main__':
    unittest.main(verbosity=2)
