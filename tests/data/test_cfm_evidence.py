"""Offline evidence integrity checks; optional data dependencies only."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path
try:
    import pandas
    import pyarrow
    HAVE_DATA = True
except ImportError:
    HAVE_DATA = False
ROOT = Path(__file__).resolve().parents[2]
if HAVE_DATA:
    spec = importlib.util.spec_from_file_location('cfm_evidence', ROOT/'scripts/build_cfm_evidence.py')
    evidence = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evidence)

@unittest.skipUnless(HAVE_DATA, 'Install requirements-data.txt')
class EvidenceChecks(unittest.TestCase):
    def setUp(self):
        self.catalogue = json.loads((ROOT/'research/cfm/incidents.json').read_text())

    def test_source_references_and_training_gates(self):
        evidence.validate_cases(self.catalogue)
        self.assertEqual(len(self.catalogue['incidents']),6)
        self.assertEqual(len({e['event_group'] for e in self.catalogue['incidents']}),4)
        self.assertEqual(self.catalogue['negative_examples'],[])

    def test_unknown_citation_rejected(self):
        self.catalogue['incidents'][0]['source_ids']=['invented']
        with self.assertRaises(ValueError): evidence.validate_cases(self.catalogue)

    def test_unreviewed_training_label_rejected(self):
        self.catalogue['incidents'][0]['flood_label']=1
        with self.assertRaises(ValueError): evidence.validate_cases(self.catalogue)

    def test_real_conflict_keeps_both_accounts(self):
        case=next(e for e in self.catalogue['incidents'] if e['id']=='chromepet-2021')
        self.assertEqual(len(case['conflicts'][0]['accounts']),2)
        self.assertIsNone(case['conflicts'][0]['resolution'])
        self.assertFalse(case['training_eligible'])

    def test_geographic_distance(self):
        self.assertEqual(evidence.distance((13,80),(13,80)),0)
        self.assertAlmostEqual(evidence.distance((0,0),(0,1)),111.195,places=2)
        self.assertAlmostEqual(evidence.distance((13,80),(12,81)),evidence.distance((12,81),(13,80)))

    def test_generated_coverage_never_asserts_live_or_catchment(self):
        p=ROOT/'research/cfm/generated/station_coverage.json'
        data=json.loads(p.read_text())
        self.assertFalse(data['coverage_verified'])
        for s in data['map_stations']:
            self.assertEqual(s['live_status'],'not_verified')
            self.assertEqual(s['catchment_link'],'not_verified')
            self.assertLessEqual(min(s['distances_km'].values()),15)
        joins=json.loads((p.parent/'incident_join_audit.json').read_text())
        self.assertTrue(all(not j['predictive_join_allowed'] for j in joins))

if __name__=='__main__': unittest.main()
