"""Run independently: python -m unittest discover -s tests/data -v"""
import importlib.util
from pathlib import Path
import tempfile
import unittest
try:
    import pandas as pd
    import pyarrow
    import sklearn
    DATA_DEPS = True
except ImportError:
    DATA_DEPS = False

ROOT = Path(__file__).resolve().parents[2]

def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'scripts'/f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

if DATA_DEPS:
    benchmark = load('benchmark_cfm')
    audit = load('audit_cfm')

@unittest.skipUnless(DATA_DEPS, 'Install requirements-data.txt to run optional data checks')
class DatasetChecks(unittest.TestCase):
    def frame(self):
        return pd.DataFrame({'srgid': ['Tambaram']*12,
            'date': pd.date_range('2010-01-01', periods=12).strftime('%Y-%m-%dZ'),
            'rainfall': list(range(12))})

    def test_features_precede_target(self):
        out = benchmark.examples(self.frame())
        self.assertEqual(len(out), 5)
        self.assertTrue((out.target_date > out.date).all())
        self.assertEqual(out.iloc[0].reading_lag_0, 6)
        self.assertEqual(out.iloc[0].reading_lag_6, 0)
        self.assertEqual(out.iloc[0].target, 7)

    def test_missing_day_is_not_dry_day(self):
        frame = self.frame().drop(index=6)
        self.assertTrue(benchmark.examples(frame).empty)

    def test_missing_and_negative_readings_not_used(self):
        for value in [None, -999]:
            frame = self.frame()
            frame.loc[6, 'rainfall'] = value
            self.assertTrue(benchmark.examples(frame).empty)

    def test_duplicate_date_is_rejected(self):
        frame = self.frame()
        with self.assertRaises(ValueError):
            benchmark.examples(pd.concat([frame, frame.iloc[[0]]]))

    def test_audit_detects_timestamp_disagreement_and_unknown(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'awlr_waterlevel.parquet'
            pd.DataFrame({'awlrid':['x','x'], 'date':['2025-01-01Z']*2,
                'time_of_measurementtemp':['12:00']*2, 'waterlevel':[None,0.0],
                'combined_datetime':['2025-01-02T06:30:00Z']*2}).to_parquet(path)
            result = audit.profile(path)
            self.assertEqual(result['combined_vs_date_day_offsets']['1'],2)
            self.assertEqual(result['duplicate_station_date_time'],1)
            self.assertEqual(result['columns']['waterlevel']['missing'],1)
            self.assertEqual(result['numeric_summary']['waterlevel']['zero'],1)

if __name__ == '__main__':
    unittest.main()
