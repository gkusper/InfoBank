"""Preregistered mode and evidence diagnostics; no inference calls."""
import collections
MODES=['FULL','CFAF']
COLUMNS=['FULL','CFAF','OPERATIONAL','POLICY','NOT_EXECUTED']
def mode_metrics(records,system):
 c={g:{p:0 for p in COLUMNS} for g in MODES};observed=0
 for r in records:
  s=r['systems'][system];gold=r['gold_mode'];observed+=s['mode']==gold;p='NOT_EXECUTED' if s['status']=='NOT_EXECUTED' else 'OPERATIONAL' if s['operational_failure'] else 'POLICY' if s.get('policy_violation') else s['mode'];c[gold][p]+=1
 fn=sum(c['FULL'].values());cn=sum(c['CFAF'].values());N=fn+cn;correct=c['FULL']['FULL']+c['CFAF']['CFAF'];pf=c['FULL']['FULL']+c['CFAF']['FULL'];pc=c['FULL']['CFAF']+c['CFAF']['CFAF'];fr=c['FULL']['FULL']/fn if fn else None;cr=c['CFAF']['CFAF']/cn if cn else None
 return {'N_planned':N,'correct_nonoperational':correct,'accuracy':correct/N if N else None,'balanced_accuracy':(fr+cr)/2 if fr is not None and cr is not None else None,'FULL_precision':c['FULL']['FULL']/pf if pf else None,'FULL_recall':fr,'CFAF_precision':c['CFAF']['CFAF']/pc if pc else None,'CFAF_recall':cr,'unnecessary_refusals':c['FULL']['CFAF'],'failures_to_restrict':c['CFAF']['FULL'],'operational_failure_count':sum(c[g]['OPERATIONAL'] for g in MODES),'policy_violation_count':sum(c[g]['POLICY'] for g in MODES),'not_executed_count':sum(c[g]['NOT_EXECUTED'] for g in MODES),'confusion_gold_rows_prediction_columns':c,'observed_mode_agreement_including_operational_NOT_primary':observed/N if N else None,'precision_scope':'Nonoperational policy-valid predictions; missing/operational cases remain in accuracy/recall denominators','answer_correctness':'Not established by mode agreement'}

def prf(selected,gold):
 tp=len(selected&gold);p=tp/len(selected) if selected else None;r=tp/len(gold) if gold else None;f=2*tp/(len(selected)+len(gold)) if selected or gold else None
 return {'selected_count':len(selected),'gold_count':len(gold),'intersection_count':tp,'precision':p,'recall':r,'F1':f}
def norm(s):return ' '.join(s.split())
def original_reference(a):
 if a['unanswerable']:return None
 if a['extractive_spans']:return '; '.join(a['extractive_spans'])
 if a['free_form_answer'].strip():return a['free_form_answer']
 return 'Yes' if a['yes_no'] else 'No'
