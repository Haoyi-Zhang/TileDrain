import sys
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from contracts import Instance, MAX_INTEGER, closure, synthesize, verify
from general import analyze, verify_analysis
from independent import independent_safe, independent_verify_analysis, independent_verify_cut
from robust import effectively_aligned, obstruction_capacity, synthesize_effective


class GrammarTests(unittest.TestCase):
    def test_closure_rejects_backward_and_self_edges(self):
        for edge in ((1, 0), (0, 0)):
            with self.assertRaises(ValueError):
                closure(2, [edge])

    def test_closure_builds_transitive_predecessors(self):
        self.assertEqual(closure(4, [(0, 1), (1, 2), (2, 3)]), (0, 1, 3, 7))

    def test_instance_rejects_nontransitive_order(self):
        x = Instance((0, 0, 0), (0, 1, 2), (0, 0, 0), (1, 1, 1), (3,), 0)
        with self.assertRaises(ValueError):
            x.validate(False)
        self.assertFalse(independent_safe(x, 7))

    def test_instance_rejects_virtual_edge_missing_from_source(self):
        x = Instance((0, 1), (0, 0), (0, 1), (1, 1), (1, 1), 0)
        with self.assertRaises(ValueError):
            x.validate(False)
        self.assertFalse(independent_safe(x, 3))

    def test_scalar_and_capacity_boundaries(self):
        ok = Instance((0,), (0,), (0,), (MAX_INTEGER,), (MAX_INTEGER,), 0)
        ok.validate(False)
        with self.assertRaises(ValueError):
            Instance((0,), (0,), (0,), (MAX_INTEGER + 1,), (MAX_INTEGER,), 0).validate(False)
        with self.assertRaises(ValueError):
            Instance((0,), (0,), (0,), (1,), (), 0).validate(False)


class IndependentCertificateTests(unittest.TestCase):
    def test_independent_accepts_aligned_certificate(self):
        q = closure(4, [(0, 1), (2, 3)])
        x = Instance((0, 0, 0, 0), q, (0, 0, 1, 1), (1, 2, 2, 1), (2, 1), 0)
        cert = synthesize(x)
        self.assertTrue(verify(x, cert))
        self.assertTrue(independent_verify_cut(x, cert))

    def test_independent_accepts_general_least_certificate(self):
        x = Instance((0, 0), (0, 0), (0, 0), (2, 1), (1,), 0)
        cert = analyze(x)
        self.assertEqual(cert['kind'], 'least')
        self.assertTrue(verify_analysis(x, cert))
        self.assertTrue(independent_verify_analysis(x, cert))

    def test_independent_accepts_no_least_witness(self):
        x = Instance((0, 0), (0, 0), (0, 0), (1, 2), (2,), 0)
        cert = analyze(x)
        self.assertEqual(cert['kind'], 'no_least')
        self.assertTrue(verify_analysis(x, cert))
        self.assertTrue(independent_verify_analysis(x, cert))

    def test_independent_accepts_one_event_least_certificate(self):
        x = Instance((0,), (0,), (0,), (1,), (0,), 0)
        cert = analyze(x)
        self.assertEqual(cert['kind'], 'least')
        self.assertTrue(verify_analysis(x, cert))
        self.assertTrue(independent_verify_analysis(x, cert))

    def test_malformed_event_lists_are_rejected_without_exception(self):
        least_x = Instance((0, 1), (0, 1), (0, 0), (1, 1), (1,), 0)
        least_cert = analyze(least_x)
        self.assertEqual(least_cert['kind'], 'least')
        self.assertTrue(verify_analysis(least_x, least_cert))
        self.assertTrue(independent_verify_analysis(least_x, least_cert))

        no_least_x = Instance((0, 0), (0, 0), (0, 0), (1, 2), (2,), 0)
        no_least_cert = analyze(no_least_x)
        self.assertEqual(no_least_cert['kind'], 'no_least')
        self.assertTrue(verify_analysis(no_least_x, no_least_cert))
        self.assertTrue(independent_verify_analysis(no_least_x, no_least_cert))

        malformed = ([{}], [[]], [0, None], [True], [0, 0], [-1], [2])
        for payload in malformed:
            with self.subTest(kind='least', payload=repr(payload)):
                bad = deepcopy(least_cert)
                bad['cut']['drain'] = deepcopy(payload)
                self.assertFalse(verify_analysis(least_x, bad))
                self.assertFalse(independent_verify_analysis(least_x, bad))
            for field in ('left', 'right'):
                with self.subTest(kind='no_least', field=field, payload=repr(payload)):
                    bad = deepcopy(no_least_cert)
                    bad[field] = deepcopy(payload)
                    self.assertFalse(verify_analysis(no_least_x, bad))
                    self.assertFalse(independent_verify_analysis(no_least_x, bad))

    def test_forged_cone_capacity_lane_is_rejected(self):
        x = Instance((0, 0), (0, 0), (0, 1), (2, 1), (1, 1), 0)
        cert = analyze(x)
        self.assertEqual(cert['kind'], 'least')
        bad = deepcopy(cert)
        bad['cut']['necessity'][0]['lane'] = 1
        self.assertFalse(verify_analysis(x, bad))
        self.assertFalse(independent_verify_analysis(x, bad))

    def test_missing_reason_is_rejected(self):
        x = Instance((0,), (0,), (0,), (1,), (0,), 0)
        cert = analyze(x)
        bad = deepcopy(cert)
        bad['cut']['necessity'] = []
        self.assertFalse(verify_analysis(x, bad))
        self.assertFalse(independent_verify_analysis(x, bad))

    def test_extra_metadata_is_rejected(self):
        x = Instance((0,), (0,), (0,), (1,), (0,), 0)
        cert = analyze(x)
        cert['unexpected'] = True
        self.assertFalse(verify_analysis(x, cert))
        self.assertFalse(independent_verify_analysis(x, cert))

    def test_infeasible_no_least_side_is_rejected(self):
        x = Instance((0, 0), (0, 0), (0, 0), (1, 1), (1,), 0)
        cert = {'kind': 'no_least', 'left': [], 'right': [1]}
        self.assertFalse(verify_analysis(x, cert))
        self.assertFalse(independent_verify_analysis(x, cert))


class RobustContractTests(unittest.TestCase):
    def test_effective_certificate_independent_check(self):
        q = closure(4, [(0, 2), (1, 2), (2, 3)])
        x = Instance((0, 0, 0, 0), q, (0, 0, 0, 0), (1, 2, 1, 2), (3,), 1)
        self.assertTrue(effectively_aligned(x))
        cert = synthesize_effective(x)
        self.assertTrue(independent_verify_cut(x, cert))

    def test_nonrobust_obstruction_is_in_domain(self):
        q = closure(3, [(0, 2), (1, 2)])
        x = Instance((0, 0, 0), q, (0, 0, 0), (1, 2, 2), (5,), 0)
        cap = obstruction_capacity(x)
        self.assertEqual(cap, (4,))
        y = Instance(x.p, x.q, x.lane, x.weight, cap, x.unsupported)
        cert = analyze(y)
        self.assertEqual(cert['kind'], 'no_least')
        self.assertTrue(independent_verify_analysis(y, cert))

    def test_robust_chain_has_no_obstruction(self):
        q = closure(3, [(0, 1), (1, 2)])
        x = Instance((0, 0, 0), q, (0, 0, 0), (2, 1, 2), (0,), 0)
        self.assertTrue(effectively_aligned(x))
        self.assertIsNone(obstruction_capacity(x))


if __name__ == '__main__':
    unittest.main()
