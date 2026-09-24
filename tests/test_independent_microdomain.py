import itertools
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from contracts import Instance
from general import analyze
from independent import independent_verify_analysis
from oracle import all_forward_posets, structural_cuts, feasible_from_structure


class IndependentMicrodomainTests(unittest.TestCase):
    def test_all_weighted_instances_through_two_events(self):
        for n in range(3):
            ps = list(all_forward_posets(n))
            for p in ps:
                for q in ps:
                    if any(a & ~b for a, b in zip(p, q)):
                        continue
                    for lane in itertools.product(range(2), repeat=n):
                        structural, _ = structural_cuts(p, q, lane)
                        for unsupported in range(1 << n):
                            for weight in itertools.product((1, 2), repeat=n):
                                loads = [sum(weight[e] for e in range(n) if lane[e] == l) for l in range(2)]
                                for cap in itertools.product(*(range(v + 1) for v in loads)):
                                    x = Instance(p, q, lane, weight, cap, unsupported)
                                    feasible = feasible_from_structure(x, structural)
                                    meet = (1 << n) - 1
                                    for d in feasible:
                                        meet &= d
                                    cert = analyze(x)
                                    self.assertEqual(cert['kind'] == 'least', meet in feasible)
                                    self.assertTrue(independent_verify_analysis(x, cert))


if __name__ == '__main__':
    unittest.main()
