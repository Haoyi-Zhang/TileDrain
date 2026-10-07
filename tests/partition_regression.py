"""Finite partition/consumer controls; no campaign, subprocess or clock calls."""
from __future__ import annotations
import ast
import contextlib
import fnmatch
import importlib.util
import io
import itertools
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))
import aggregate
import capacity_audit
import experiment
from reproduction_diagnostics_regression import reference_posets

NATIVE_CONTROLLER = importlib.util.find_spec('resource') is not None
if NATIVE_CONTROLLER:
    import reproduce


def plan():
    # Inspect the actual controller's literal, without executing/shimming its imports.
    tree = ast.parse((ROOT / 'reproduce.py').read_bytes())
    return next(ast.literal_eval(node.value) for node in tree.body
                if isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == 'CHUNKS' for t in node.targets))


class MemoryPath:
    """In-memory I/O boundary for unchanged actual CSV/JSON consumer functions."""
    def __init__(self, files, key=''):
        self.files, self.key = files, key

    def __truediv__(self, name):
        return MemoryPath(self.files, str(Path(self.key) / name))

    @property
    def name(self):
        return Path(self.key).name

    def glob(self, pattern):
        return [MemoryPath(self.files, key) for key in sorted(self.files)
                if fnmatch.fnmatchcase(key, pattern)]

    def read_text(self, *args, **kwargs):
        return self.files[self.key]

    def with_suffix(self, suffix):
        return MemoryPath(self.files, str(Path(self.key).with_suffix(suffix)))

    def exists(self):
        return self.key in self.files

    def is_file(self):
        return self.exists()

    def __str__(self):
        return self.key

    def __lt__(self, other):
        return self.key < other.key


@contextlib.contextmanager
def memory_gzip(path, mode, **kwargs):
    if mode.startswith('w'):
        stream = io.StringIO()
        yield stream
        path.files[path.key] = stream.getvalue()
    else:
        yield io.StringIO(path.files[path.key])


def fixture(n, intervals):
    source = MemoryPath({})
    with patch('gzip.open', memory_gzip), contextlib.redirect_stderr(io.StringIO()):
        for start, stop in intervals:
            summary = experiment.exact(n, start, stop, source)
            source.files[f'exact-{n}-{start:02d}-{stop:02d}.json'] = json.dumps(summary)
    return source


class PartitionRegression(unittest.TestCase):
    def test_literal_plan_covers_each_index_once_in_order(self):
        chunks = plan()
        self.assertEqual(chunks[:4], [(0, 0, 1), (1, 0, 1), (2, 0, 2), (3, 0, 7)])
        self.assertEqual(chunks[4:], [(4, p, p + 1) for p in range(40)])
        self.assertEqual(len(chunks), 44)
        for n in range(5):
            indices = [p for size, start, stop in chunks if size == n
                       for p in range(start, stop)]
            self.assertEqual(indices, list(range(len(reference_posets(n)))))
            self.assertEqual(len(indices), len(set(indices)))

    def test_independent_count_retains_every_lower_dimension(self):
        counts = []
        for n in range(5):
            ps = reference_posets(n)
            capacity_vectors = sum((lane.count(0) + 1) * (lane.count(1) + 1)
                                   for lane in itertools.product((0, 1), repeat=n))
            per_p = [sum(all(not (a & ~b) for a, b in zip(p, q)) for q in ps)
                     * capacity_vectors * (1 << n) for p in ps]
            selected = [p for size, start, stop in plan() if size == n
                        for p in range(start, stop)]
            self.assertEqual(sum(per_p[p] for p in selected), sum(per_p))
            counts.append(sum(per_p[p] for p in selected))
        self.assertEqual(counts, [1, 8, 168, 7744, 729088])
        self.assertEqual(sum(counts), 737009)

    def test_split_raw_rows_and_all_scientific_counters(self):
        whole = fixture(2, [(0, 2)])
        split = fixture(2, [(0, 1), (1, 2)])
        old = json.loads(whole.files['exact-2-00-02.json'])
        new = [json.loads(split.files[f'exact-2-{p:02d}-{p+1:02d}.json'])
               for p in range(2)]
        excluded = {'suite', 'n', 'p_start', 'p_stop', 'posets'}
        for key in old.keys() - excluded:
            if isinstance(old[key], list):
                self.assertEqual(old[key], [sum(s[key][i] for s in new)
                                           for i in range(len(old[key]))], key)
            else:
                self.assertEqual(old[key], sum(s[key] for s in new), key)
        rows = [split.files[f'exact-2-{p:02d}-{p+1:02d}.csv.gz'].splitlines()
                for p in range(2)]
        self.assertEqual(rows[0][0], rows[1][0])
        self.assertEqual(whole.files['exact-2-00-02.csv.gz'].splitlines(),
                         rows[0] + rows[1][1:])
        with patch('gzip.open', memory_gzip):
            out1, out2 = MemoryPath({}), MemoryPath({})
            a = capacity_audit.exact_groups(whole, out1, 2)
            b = capacity_audit.exact_groups(split, out2, 2)
        self.assertEqual(a, b)
        self.assertEqual(a['capacity_instances'], 168)
        self.assertEqual(a['fixed_groups'], 48)
        self.assertEqual(out1.files, out2.files)

    def test_capacity_consumer_rejects_gap_overlap_and_bad_capacity_rows(self):
        original = fixture(2, [(0, 1), (1, 2)])
        variants = []
        gap = dict(original.files)
        gap.pop('exact-2-01-02.json')
        variants.append((gap, 'coverage is incomplete'))
        overlap = dict(original.files)
        overlap['exact-2-duplicate.json'] = overlap['exact-2-00-01.json']
        overlap['exact-2-duplicate.csv.gz'] = overlap['exact-2-00-01.csv.gz']
        variants.append((overlap, 'overlapping exact chunks'))
        duplicate = dict(original.files)
        lines = duplicate['exact-2-00-01.csv.gz'].splitlines()
        duplicate['exact-2-00-01.csv.gz'] += lines[1] + '\n'
        variants.append((duplicate, 'duplicate capacity row'))
        missing = dict(original.files)
        lines = missing['exact-2-01-02.csv.gz'].splitlines()
        missing['exact-2-01-02.csv.gz'] = '\n'.join(lines[:-1]) + '\n'
        variants.append((missing, 'missing capacity within a fixed group'))
        with patch('gzip.open', memory_gzip):
            for files, error in variants:
                with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                    capacity_audit.exact_groups(MemoryPath(files), MemoryPath({}), 2)

    def test_aggregate_still_rejects_missing_overlap_gap_and_raw_disagreement(self):
        original = fixture(0, [(0, 1)])
        variants = [({}, 'missing exact chunks')]
        gap = dict(original.files)
        summary = json.loads(gap['exact-0-00-01.json'])
        summary['p_stop'] = 2
        gap = {'exact-0-00-02.json': json.dumps(summary),
               'exact-0-00-02.csv.gz': original.files['exact-0-00-01.csv.gz']}
        variants.append((gap, 'coverage gap or overlap'))
        overlap = dict(original.files)
        overlap['exact-0-duplicate.json'] = overlap['exact-0-00-01.json']
        variants.append((overlap, 'coverage gap or overlap'))
        mismatch = dict(original.files)
        summary = json.loads(mismatch['exact-0-00-01.json'])
        summary['instances'] += 1
        mismatch['exact-0-00-01.json'] = json.dumps(summary)
        variants.append((mismatch, 'raw/summary disagreement'))
        with patch('gzip.open', memory_gzip):
            for files, error in variants:
                with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                    aggregate.aggregate(MemoryPath(files), MemoryPath({}))

    def test_resource_and_failure_gates_remain_declared(self):
        for path, cpu in (('reproduce.py', 120), ('src/experiment.py', 40)):
            tree = ast.parse((ROOT / path).read_bytes())
            calls = {ast.dump(n, include_attributes=False) for n in ast.walk(tree)
                     if isinstance(n, ast.Call)}
            for statement in (f'resource.setrlimit(resource.RLIMIT_CPU,({cpu},{cpu}))',
                              'resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3))'):
                wanted = ast.parse(statement).body[0].value
                self.assertIn(ast.dump(wanted, include_attributes=False), calls)
        workflow = (ROOT / '.github/workflows/scientific-checks.yml').read_text()
        for line in ('timeout-minutes: 15', 'timeout --signal=TERM --kill-after=10s 720s',
                     'ulimit -v 3145728', 'ulimit -t 600', 'set -euo pipefail',
                     'if: always()', 'python -B tests/partition_regression.py'):
            self.assertIn(line, workflow)

    @unittest.skipUnless(NATIVE_CONTROLLER, 'native POSIX resource unavailable; no shim')
    def test_controller_admission_and_old_partition_overlap(self):
        with patch.object(reproduce, 'job') as job:
            for start, stop in ((-1, 1), (0, 0), (0, 41), (40, 41)):
                with self.subTest(start=start, stop=stop), self.assertRaises(ValueError):
                    reproduce.exact(MemoryPath({}), 4, start, stop)
            old = MemoryPath({'exact-4-00-05.json': json.dumps({'p_start': 0, 'p_stop': 5})})
            with self.assertRaisesRegex(ValueError, 'overlap'):
                reproduce.exact(old, 4, 0, 1)
            job.assert_not_called()
            adjacent = MemoryPath({'exact-4-00-01.json': json.dumps({'p_start': 0, 'p_stop': 1})})
            reproduce.exact(adjacent, 4, 1, 2)
            self.assertEqual(job.call_args.args[1], 'exact-4-01-02')

    @unittest.skipUnless(NATIVE_CONTROLLER, 'native POSIX resource unavailable; no shim')
    def test_controller_completed_summary_requires_raw_product(self):
        name = 'exact-4-00-01'
        output = MemoryPath({name + '.json': '{}'})
        with patch.object(reproduce, 'child') as child:
            with self.assertRaisesRegex(ValueError, 'incomplete existing result'):
                reproduce.job(output, name, [], (name + '.csv.gz',))
            output.files[name + '.csv.gz'] = 'retained raw data'
            with contextlib.redirect_stdout(io.StringIO()):
                reproduce.job(output, name, [], (name + '.csv.gz',))
            child.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
