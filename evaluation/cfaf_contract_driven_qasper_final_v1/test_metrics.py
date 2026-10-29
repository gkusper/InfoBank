"""Scorer-only safeguards for missing/operational and tier denominators."""
from .metrics import mode_metrics,prf

def row(gold,mode,op=False,status='VALID'):
 return {'gold_mode':gold,'systems':{'C':{'mode':mode,'status':status,'operational_failure':op,'policy_violation':False}}}
def test_operational_cfaf_gets_zero_gold_cfaf_credit():
 m=mode_metrics([row('FULL','FULL'),row('CFAF','CFAF',True)],'C');assert m['accuracy']==0.5;assert m['CFAF_recall']==0;assert m['operational_failure_count']==1;assert m['observed_mode_agreement_including_operational_NOT_primary']==1

def test_unexecuted_stays_in_denominator():
 m=mode_metrics([row('FULL','FULL'),row('CFAF',None,True,'NOT_EXECUTED')],'C');assert m['N_planned']==2;assert m['accuracy']==0.5;assert m['not_executed_count']==1

def test_absent_tier_is_undefined_not_zero_accuracy():
 m=mode_metrics([],'C');assert m['N_planned']==0;assert m['accuracy'] is None;assert m['balanced_accuracy'] is None

def test_empty_selection_has_zero_f1_against_nonempty_gold():
 assert prf(set(),{'one'})['F1']==0;assert prf(set(),set())['F1'] is None
