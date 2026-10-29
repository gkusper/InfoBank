"""Predeclared mechanical test eligibility; original annotations never enter runtime."""
import collections,json
from .artifacts import *
ANSWER_FIELDS={'unanswerable','extractive_spans','yes_no','free_form_answer','evidence','highlighted_evidence'}
def norm(text):return ' '.join(text.split())
def source_integrity(pid,p):
 if not isinstance(pid,str) or not pid.strip() or not isinstance(p,dict):return False
 if any(not isinstance(p.get(k),str) or not p[k].strip() for k in ['title','abstract']):return False
 if not isinstance(p.get('full_text'),list) or not p['full_text']:return False
 for sec in p['full_text']:
  if not isinstance(sec,dict) or not isinstance(sec.get('section_name'),str) or not isinstance(sec.get('paragraphs'),list) or any(not isinstance(t,str) for t in sec['paragraphs']):return False
 if not any(t.strip() for sec in p['full_text'] for t in sec['paragraphs']):return False
 figs=p.get('figures_and_tables')
 return isinstance(figs,list) and all(isinstance(f,dict) and isinstance(f.get('caption'),str) and isinstance(f.get('file'),str) for f in figs)

def valid_annotation(wrapper):
 a=wrapper.get('answer') if isinstance(wrapper,dict) else None
 if not isinstance(a,dict) or set(a)!=ANSWER_FIELDS or type(a.get('unanswerable')) is not bool:return False
 for k in ['extractive_spans','evidence','highlighted_evidence']:
  if not isinstance(a[k],list) or any(not isinstance(t,str) for t in a[k]):return False
 if any(not t.strip() for t in a['extractive_spans']) or not isinstance(a['free_form_answer'],str) or a['yes_no'] is not None and type(a['yes_no']) is not bool:return False
 reps=bool(a['extractive_spans'])+bool(a['free_form_answer'].strip())+(type(a['yes_no']) is bool)
 return reps==(0 if a['unanswerable'] else 1)

def label(pid,p,q):
 reasons=[];aa=q.get('answers') if isinstance(q,dict) else None
 if not source_integrity(pid,p):reasons.append('SOURCE_INTEGRITY_INVALID')
 if not isinstance(q,dict) or not isinstance(q.get('question_id'),str) or not q['question_id'].strip() or not isinstance(q.get('question'),str) or not q['question'].strip():reasons.append('QUESTION_STRUCTURE_INVALID')
 if not isinstance(aa,list) or not aa:reasons.append('MISSING_ANNOTATIONS');aa=[]
 if any(not valid_annotation(a) for a in aa):reasons.append('MALFORMED_OR_CONTRADICTORY_ANSWER_STRUCTURE')
 if reasons:return {'mode':'UNKNOWN','tier':None,'reasons':reasons}
 answers=[w['answer'] for w in aa];flags={a['unanswerable'] for a in answers}
 if len(flags)>1:return {'mode':'UNKNOWN','tier':None,'reasons':['MIXED_UNANSWERABLE_FLAGS']}
 bools={a['yes_no'] for a in answers if type(a['yes_no']) is bool}
 if len(bools)>1:return {'mode':'UNKNOWN','tier':None,'reasons':['CONTRADICTORY_BOOLEAN_ANSWERS']}
 mode='CFAF' if next(iter(flags)) else 'FULL'
 if mode=='FULL':
  texts={norm(p['abstract'])}|{norm(t) for sec in p['full_text'] for t in sec['paragraphs'] if t.strip()}
  for a in answers:
   if not a['evidence']:reasons.append('NO_ORIGINAL_TEXT_EVIDENCE')
   for t in a['evidence']:
    if t.lstrip().startswith('FLOAT SELECTED'):reasons.append('UNAVAILABLE_NONTEXTUAL_EVIDENCE')
    elif not t.strip() or norm(t) not in texts:reasons.append('ORIGINAL_TEXT_EVIDENCE_UNREPRESENTED')
 if reasons:return {'mode':'UNKNOWN','tier':None,'reasons':sorted(set(reasons))}
 return {'mode':mode,'tier':'M' if len(aa)>=2 else 'S','reasons':[]}

def audit():
 ensure();assert not (ROOT/'QASPER_ELIGIBILITY_COUNTS.json').exists();src=read(ROOT/'SOURCE_PROVENANCE.json');assert sha(ROOT/'datasets/qasper-test-v0.3.json')==src['test_member']['sha256'];papers=read(ROOT/'datasets/qasper-test-v0.3.json');counts=collections.Counter();tiers={t:collections.Counter() for t in ['M','S']};distinct={t:{m:set() for m in ['FULL','CFAF']} for t in ['ALL','M','S']};reasons=collections.Counter();ids=set();nontext=0;invalid_papers=0
 for pid,p in papers.items():
  invalid_papers+=not source_integrity(pid,p)
  for q in p['qas']:
   qid=q.get('question_id');assert qid and qid not in ids;ids.add(qid);v=label(pid,p,q);counts[v['mode']]+=1;reasons.update(v['reasons']);hasfloat=any(isinstance(w,dict) and isinstance(w.get('answer'),dict) and any(isinstance(t,str) and t.lstrip().startswith('FLOAT SELECTED') for t in w['answer'].get('evidence',[])) for w in q.get('answers',[]));nontext+=hasfloat
   if v['mode']!='UNKNOWN':tiers[v['tier']][v['mode']]+=1;distinct['ALL'][v['mode']].add(pid);distinct[v['tier']][v['mode']].add(pid)
   append(ROOT/'local/eligibility_metadata.jsonl',{'paper_id':pid,'question_id':qid,'annotation_count':len(q.get('answers',[])),**v,'has_nontextual_evidence_marker':hasfloat})
 out={'total_papers':len(papers),'total_questions':len(ids),'class_counts':dict(counts),'tier_counts':{t:dict(c) for t,c in tiers.items()},'distinct_papers':{t:{m:len(ps) for m,ps in groups.items()} for t,groups in distinct.items()},'UNKNOWN_reason_counts_overlap':dict(reasons),'questions_with_original_nontextual_evidence_marker':nontext,'invalid_reference_paper_records':invalid_papers,'mapping_sha256':sha(ROOT/'QASPER_GOLD_MAPPING.md'),'source_test_sha256':src['test_member']['sha256'],'metadata_sha256':sha(ROOT/'local/eligibility_metadata.jsonl'),'gold_scorer_only':True};write(ROOT/'QASPER_ELIGIBILITY_COUNTS.json',out);print(json.dumps(out,indent=2))
if __name__=='__main__':audit()
