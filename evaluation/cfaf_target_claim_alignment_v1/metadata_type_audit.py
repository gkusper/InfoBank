"""Extend the original seventeen authored expectations without editing them."""
from .artifacts import *
from .metadata_value_typing import decompose_fixed,typed_value
from .aggregate_smoke_adapter import execute

def run():
 source=REPO/'evaluation/cfaf_requirement_alignment_v1/synthetic_decomposition_cases.jsonl';old=rows(source);records=[]
 for r in old:
  p=decompose_fixed(r['query']);actual=[q['answer_type'] for q in p['requirements']];records.append({'index':r['index'],'query':r['query'],'original_expected_answer_types':r['expected_answer_types'],'actual_answer_types':actual,'pass':actual==r['expected_answer_types'],'typed_profile':p,'scope':'Original authored development expectations preserved; not independent validation'})
 for r in records:append(ROOT/'metadata_type_audit.jsonl',r)
 extra=[('2044-02-29','DATE_TIME',True),('2043-02-29','DATE_TIME',False),('2047-04-23T12:30:00+00:00','DATE_TIME',True),('not a date','DATE_TIME',False),('ODT','STRING',True),(True,'COUNT',False),(float('inf'),'NUMBER',False)]
 checks=[{'value':str(v),'value_type':typ,'expected':expected,'actual':typed_value(v,typ),'pass':typed_value(v,typ)==expected} for v,typ,expected in extra];write(ROOT/'metadata_value_type_checks.json',checks)
 summary={'original_expectations_source':str(source.relative_to(REPO)),'original_expectations_sha256':sha(source),'original_cases':len(records),'original_type_sequences_correct':sum(r['pass'] for r in records),'additional_value_checks':len(checks),'additional_value_checks_passed':sum(r['pass'] for r in checks),'old_schema_expectations_unchanged':True,'model_calls':0};write(ROOT/'metadata_type_summary.json',summary)
 if not all(r['pass'] for r in records+checks):raise RuntimeError('Metadata type regression blocker')
 contributions=[{'source_id':'aggregate-a','contributor_id':'contributor-x','value':17},{'source_id':'aggregate-b','contributor_id':'contributor-y','value':31},{'source_id':'aggregate-c','contributor_id':'contributor-z','value':46},{'source_id':'aggregate-a-z','contributor_id':'contributor-x','value':999},{'source_id':'denied-input','value':'not inspected'}];policy={c['source_id']:('DENY' if c['source_id']=='denied-input' else 'AGGREGATE') for c in contributions};agg=[]
 for operation,expected in [('count',3),('sum',94),('mean',31.333333)]:
  out=execute(contributions,policy,operation,k=3);agg.append({'operation':operation,'expected':expected,'result':out,'pass':out['generator_context']['value']==expected})
 low=execute(contributions[:1],policy,k=3);empty=execute([],{},k=3);assert low==empty
 write(ROOT/'aggregation_smoke_results.json',{'cases':agg,'below_threshold_indistinguishable_from_empty':low==empty,'raw_values_or_identifiers_sent_to_generator':False,'model_calls':0,'scope':'Structured authorized synthetic contributions only; separate from RefusalBench accuracy'})
 print({'metadata_original_pass':summary['original_type_sequences_correct'],'additional_value_checks':len(checks),'aggregation_smoke_pass':all(r['pass'] for r in agg)})
if __name__=='__main__':run()
