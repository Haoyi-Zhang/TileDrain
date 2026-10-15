import copy,csv,importlib.util,json,math,shutil,sys,tempfile,unittest
from pathlib import Path
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('p063_scaling_report',ROOT/'src/scaling_report.py')
report=importlib.util.module_from_spec(spec);spec.loader.exec_module(report)


class ScalingReportTests(unittest.TestCase):
    def rows(self):
        with (ROOT/'results/scaling/scaling.csv').open(newline='') as f:return list(csv.DictReader(f))

    def test_selected_batch_has_exact_coverage_and_recorded_medians(self):
        value=report.load_report()
        self.assertEqual((value['rows'],len(value['cells']),value['zero_intervals']),(36,12,23))
        expected={'sparse':(134.970184,107.992499,77.998397),'dense':(185.997527,157.982810,130.973699)}
        for c in value['cells']:
            if c['n']==512:
                for metric,median in zip(report.METRICS,expected[c['density']]):self.assertAlmostEqual(c[metric]['median_ms'],median,places=6)

    def test_incomplete_duplicate_or_mixed_shape_rows_fail(self):
        rows=self.rows()
        for bad in (rows[:-1],rows[:-1]+[rows[0]]):
            with self.assertRaises(ValueError):report.summarize_rows(bad)
        rows[0]['lanes']='8'
        with self.assertRaises(ValueError):report.summarize_rows(rows)

    def test_zero_intervals_retained_and_nonfinite_or_negative_rejected(self):
        rows=self.rows();rows[0]['general_cpu_seconds']='0'
        self.assertTrue(any(c['general_cpu_seconds']['zero_intervals'] for c in report.summarize_rows(rows)))
        for value in ('nan','inf','-0.001'):
            bad=copy.deepcopy(rows);bad[0]['check_cpu_seconds']=value
            with self.assertRaises(ValueError):report.summarize_rows(bad)

    def test_missing_summary_link_and_changed_scientific_source_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            for p in (ROOT/'results/scaling').iterdir():
                if p.is_file():shutil.copy2(p,folder/p.name)
            env=json.loads((folder/'scaling-environment.json').read_text());env['summary_data']='missing.json'
            (folder/'scaling-environment.json').write_text(json.dumps(env))
            provenance=json.loads((folder/'provenance.json').read_text());provenance['files']['scaling-environment.json']=report.file_digest(folder/'scaling-environment.json')
            (folder/'provenance.json').write_text(json.dumps(provenance))
            with self.assertRaisesRegex(ValueError,'links'):report.load_report(folder)
        digest=report.file_digest
        with mock.patch.object(report,'file_digest',side_effect=lambda p:'0'*64 if p==ROOT/'src/contracts.py' else digest(p)):
            with self.assertRaisesRegex(ValueError,'scientific source differs'):report.load_report()


if __name__=='__main__':unittest.main()
