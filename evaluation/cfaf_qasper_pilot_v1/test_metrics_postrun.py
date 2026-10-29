"""Post-run scorer checks; inference sources and labels remain frozen."""
from .score import prf

def test_empty_prediction_has_zero_f1_when_gold_exists():
 m=prf(set(),{'P1'});assert m['F1']==0;assert m['recall']==0;assert m['precision'] is None

def test_all_empty_evidence_has_undefined_f1():
 assert prf(set(),set())['F1'] is None
