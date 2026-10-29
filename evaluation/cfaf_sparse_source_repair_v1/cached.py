"""Zero-call causal replay of the exact ten previously exposed raw analyses."""
import json,time,collections
from .artifacts import *
from .sparse_source_assessment import parse_sparse
from .source_inventory import build_inventory,resolve_inventory_span
from .gate_controls import assess,reason_details
from .operational_failure_codes import classify
from evaluation.cfaf_target_claim_alignment_v1 import integration as old
from evaluation.cfaf_target_claim_alignment_v1.integration_controls import assess as old_assess,reason_details as old_reason
from evaluation.cfaf_request_evidence_verification_v1.runner import request_for
from evaluation.cfaf_request_evidence_verification_v1.prepare import selector
from evaluation.cfaf_request_evidence_verification_v1.source_capability_rules import trusted_provenance
PREVIOUS=REPO/'evaluation/cfaf_dataset3_garage_pilot_v1'

def cached():
 if (ROOT/'cached_ablation_results.json').exists():raise RuntimeError('Cached comparison already saved')
 runtime=rows(PREVIOUS/'runtime_inputs.jsonl');previous=rows(PREVIOUS/'results.jsonl');events=rows(PREVIOUS/'api_events.jsonl');selection=read(PREVIOUS/'dataset3_selection_manifest.json');results=[];start=time.perf_counter()
 # Copy only ten already-exposed runtime rows; never open the complete dataset.
 (ROOT/'runtime_inputs.jsonl').write_bytes((PREVIOUS/'runtime_inputs.jsonl').read_bytes())
 write(ROOT/'selection_manifest.json',selection)
 for inp,prior,selected in zip(runtime,previous,selection['records']):
  i=inp['runtime_index'];request=request_for(inp['case'],prior['outcome']);inventory=build_inventory(request,inp['mapping']);raw=next(e['message']['content'] for e in events if e['runtime_index']==i and e['kind']=='semantic_analysis');provenance=trusted_provenance(request,False);variants={};phase_raw={}
  for config in ['A0','A1','A2','A3']:
   a,data,audit=old.parse_analysis(raw,request) if config=='A0' else parse_sparse(raw,request,inventory,allow_repair=config!='A1')
   v=old_assess(request,a,data,'T3',provenance) if config=='A0' else assess(request,a,data,'T3',provenance);mode=selector(v,request,data)
   reason=(reason_details if config=='A3' else old_reason)(v,request,data);state=classify(request,a,v['issues'],audit);accepted=[];rejected=[];roles={r['source_id']:r for r in data.get('source_assessments',[])}
   for ref in data.get('supporting_spans',[]):
    try:
     span=resolve_inventory_span(ref,inventory,request);role=roles.get(span['source_id'],{});usable=a.valid and role.get('role')=='PRIMARY' and role.get('relation_label')=='SUPPORTS'
    except ValueError:usable=False
    (accepted if usable else rejected).append(ref)
   variants[config]={'semantic_valid':a.valid,'validation_errors':audit.get('errors',[]),'mode':mode,'verification_outcome':state,'reported_internal_reason_code':None if mode=='FULL' else reason[1],'reported_public_reason_class':None if mode=='FULL' else reason[0].value,'reported_public_wording_kind':'OPERATIONAL_NEUTRAL' if config=='A3' and state['status']=='OPERATIONAL_FAILURE' else 'LEGACY_EVIDENTIAL_OR_REQUEST_RELATIVE' if mode=='CFAF' else 'FULL_CANDIDATE','accepted_support_span_ids':accepted,'rejected_support_span_ids':rejected,'not_assessed_count':audit.get('not_assessed_count',15-len(roles)),'reported_role_count':len(roles),'source_count':len(request.documents),'repairs':audit.get('repairs',[]),'fulfilment_issues':v['issues'],'hard_failure_codes':[h['code'] for h in v.get('hard_failures',[])],'sufficiency_checks_passed':v['validated_request_fulfilment'],'benchmark_gold_used':False}
   phase_raw[config]={'audit':audit,'verification':v,'data':data}
  assert variants['A0']['mode']==prior['outcome']['selected_mode'];assert variants['A2']['mode']==variants['A3']['mode'];assert variants['A2']['semantic_valid']==variants['A3']['semantic_valid']
  row={'runtime_index':i,'sample_id':selected['sample_id'],'old_raw_analysis_sha256':__import__('hashlib').sha256(raw.encode()).hexdigest(),'variants':variants};results.append(row);append(ROOT/'cached_ablation_raw.jsonl',{**row,'details':phase_raw,'raw_semantic_response':raw,'inventory':inventory.private()});print('CACHED',i+1,[(k,v['semantic_valid'],v['mode'],v['verification_outcome']['status']) for k,v in variants.items()],flush=True)
 summary={k:{'valid':sum(r['variants'][k]['semantic_valid'] for r in results),'invalid':sum(not r['variants'][k]['semantic_valid'] for r in results),'modes':dict(collections.Counter(r['variants'][k]['mode'] for r in results)),'operational_failures':sum(r['variants'][k]['verification_outcome']['status']=='OPERATIONAL_FAILURE' for r in results),'validated_CFAF':sum(r['variants'][k]['verification_outcome']['status']=='VALIDATED_CFAF' for r in results),'not_assessed_sources':sum(r['variants'][k]['not_assessed_count'] for r in results),'repaired_references':sum(len(r['variants'][k]['repairs']) for r in results)} for k in ['A0','A1','A2','A3']}
 write(ROOT/'cached_ablation_results.json',{'phase':'A cached exposed-development replay','api_calls':0,'raw_outputs_unchanged':True,'source':str(PREVIOUS.relative_to(REPO)),'elapsed_seconds':time.perf_counter()-start,'configurations':{'A0':'Original dense validation with original T3 substantive gate; not the separately named original A0 gate configuration','A1':'Sparse normalization; legacy public reason presentation','A2':'A1 plus exact deterministic reference normalization; legacy reason presentation','A3':'A2 plus distinct operational status and neutral reason presentation'},'summary':summary,'cases':results,'newly_structurally_valid':sum(not r['variants']['A0']['semantic_valid'] and r['variants']['A1']['semantic_valid'] for r in results),'changed_modes_A0_A3':sum(r['variants']['A0']['mode']!=r['variants']['A3']['mode'] for r in results),'cached_mode_promotion_is_not_a_new_generated_answer':True})
 print(json.dumps(summary,indent=2))
if __name__=='__main__':cached()
