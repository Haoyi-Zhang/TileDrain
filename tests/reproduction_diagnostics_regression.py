"""Portable, finite diagnostics tests: no subprocess, resource shim or timing."""
from __future__ import annotations

import contextlib
import io
import itertools
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from child_diagnostics import failure_record, failure_message
from experiment import exact
from oracle import all_forward_posets


def reference_posets(n: int) -> list[tuple[int, ...]]:
    """Graph reachability from edge sets, independent of scalar Floyd-Warshall."""
    edges = [(i, j) for j in range(n) for i in range(j)]
    result = []
    for selection in itertools.product((False, True), repeat=len(edges)):
        # Enumerate the masks in the artifact's specified least-significant-edge order.
        selection = tuple(reversed(selection))
        chosen = {edge for edge, take in zip(edges, selection) if take}
        reached = set()
        for origin in range(n):
            pending = [origin]
            visited = set()
            while pending:
                vertex = pending.pop()
                for earlier, later in chosen:
                    if earlier == vertex and later not in visited:
                        visited.add(later)
                        pending.append(later)
            reached.update((origin, later) for later in visited)
        relation = tuple(sum(1 << earlier for earlier in range(n)
                             if (earlier, later) in reached) for later in range(n))
        if relation not in result:
            result.append(relation)
    return result


class ReproductionDiagnosticsRegression(unittest.TestCase):
    def test_nonzero_status_preserves_output_and_command(self):
        args = ['src/experiment.py', '--suite', 'exact']
        row = failure_record(args, 2, 'partial stdout\n', 'traceback\n')
        args.append('changed')
        self.assertEqual(row['command'], args[:-1])
        self.assertEqual(row['returncode'], 2)
        self.assertFalse(row['controller_wall_timeout'])
        self.assertIsNone(row['termination_signal_number'])
        self.assertEqual(row['stdout'], 'partial stdout\n')
        self.assertEqual(row['stderr'], 'traceback\n')
        self.assertEqual(json.loads(failure_message(row).split('\n', 1)[1]), row)
        self.assertEqual(row['status'], 'failed')

    def test_signal_number_is_reported_without_cause_claim(self):
        row = failure_record(['child'], -9, '', '')
        self.assertEqual(row['returncode'], -9)
        self.assertEqual(row['termination_signal_number'], 9)
        self.assertFalse(row['controller_wall_timeout'])
        self.assertIn('does not establish its cause', row['scope'])
        self.assertNotIn('cause', row)
        unknown = failure_record(['child'], -987654, None, None)
        self.assertEqual(unknown['termination_signal_number'], 987654)
        self.assertIsNone(unknown['termination_signal_name'])

    def test_wall_timeout_keeps_partial_bytes(self):
        row = failure_record(['child'], None, b'partial\xff', b'progress p=7\n')
        self.assertTrue(row['controller_wall_timeout'])
        self.assertIsNone(row['returncode'])
        self.assertIsNone(row['termination_signal_number'])
        self.assertEqual(row['stdout'], 'partial\ufffd')
        self.assertEqual(row['stderr'], 'progress p=7\n')
        self.assertEqual(json.loads(json.dumps(row)), row)

    def test_success_cannot_be_recorded_as_failure(self):
        with self.assertRaisesRegex(ValueError, 'successful child'):
            failure_record(['child'], 0, '', '')

    def test_exact_case_growth_from_independent_domain(self):
        ps = reference_posets(4)
        self.assertEqual(ps, list(all_forward_posets(4)))
        self.assertEqual(len(ps), 40)
        capacities = sum((lane.count(0) + 1) * (lane.count(1) + 1)
                         for lane in itertools.product((0, 1), repeat=4))
        def count(start, stop):
            compatible = sum(all(not (a & ~b) for a, b in zip(p, q))
                             for p in ps[start:stop] for q in ps)
            return compatible * capacities * 16
        self.assertEqual(count(0, 5), 202752)
        self.assertEqual(count(5, 15), 221184)
        self.assertEqual(count(0, 40), 729088)

    def test_progress_does_not_change_one_event_scientific_output(self):
        raw = io.StringIO()
        @contextlib.contextmanager
        def capture(*args, **kwargs):
            yield raw
        errors = io.StringIO()
        with patch('experiment.gzip.open', capture), contextlib.redirect_stderr(errors):
            result = exact(1, 0, 1, Path('unused-output'))
        # Direct enumeration: two lane placements, two capacity choices, two support masks.
        self.assertEqual(result['instances'], 8)
        self.assertEqual(result['structures'], 2)
        self.assertEqual(result['destination_traces_examined'], 4)
        self.assertEqual(result['least'], 8)
        self.assertEqual(result['no_least'], 0)
        self.assertEqual(result['feasible_cuts'], 10)
        self.assertEqual(result['least_drained_events'], 6)
        self.assertEqual(result['least_drain_histogram'], [2, 6])
        self.assertEqual(result['capability_only_unsafe'], 2)
        self.assertEqual(result['capability_order_unsafe'], 2)
        self.assertEqual(len(raw.getvalue().splitlines()), 9)
        self.assertEqual(errors.getvalue().splitlines(), [
            'Exact progress: start n=1 p=0 stop=1 completed_instances=0',
            'Exact progress: complete n=1 p=0 completed_instances=8',
        ])


if __name__ == '__main__':
    unittest.main(verbosity=2)
