"""Controlled semantic test double; not an empirical model-accuracy measure."""
import copy,json
from evaluation.wolala2026.semantic_evidence import unknown_assessment
from evaluation.refusalbench_span_fix_v1.span_references import build_catalogue
class FunctionalProvider:
 """Functional test double; not a semantic model or benchmark accuracy measure."""
 def __init__(self,scenario,implementation):self.scenario=scenario;self.impl=implementation;self.calls=[]
 def call(self,request,kind,prompt,payload,limit):
  assert_safe_payload=self.impl.assert_safe_payload
  from types import SimpleNamespace
  assert_safe_payload(request,payload);self.calls.append((kind,copy.deepcopy(payload)))
  if kind=='query_profile':
   p=self.impl.profile_query(request.query)
   data={key:p[key] for key in ['resolution','query_target','requirements']}
   return SimpleNamespace(content=json.dumps(data),model='controlled-query-only')
  if kind=='semantic_analysis':
   good=self.scenario.get('controlled_semantic_supported',True);a=copy.deepcopy(unknown_assessment([],'controlled').data)
   docs={d['source_id']:d['context'] for d in request.documents};refs=list(build_catalogue(docs).spans)
   a.update(requested_information=request.query,query_status='SPECIFIED',premise_status='SUPPORTED' if good else 'UNESTABLISHED',support_status='SUFFICIENT' if good else 'MISSING',granularity_matches=good,confidence=1,answer_candidate=self.scenario['expected']['answer'] if good else None,supporting_spans=refs if good else [],contradicting_spans=[],uncertainty_causes=[] if good else ['evidence_missing'],rationale='Construction-controlled semantic input, not model inference.')
   a['source_assessments']=[{'source_id':d['source_id'],'role':'PRIMARY' if good else 'CONTEXTUAL','relation_label':'SUPPORTS' if good else 'NONE','grounding_span_ids':[r for r in refs if r.startswith(d['source_id']+':')],'rationale':'Controlled permitted evidence.'} for d in request.documents]
   a['requirement_support']=[{'requirement_id':r['requirement_id'],'support_status':'SUFFICIENT' if good else 'MISSING','supporting_span_ids':refs if good else [],'rationale':'Controlled support.'} for r in request.query_profile['requirements']]
   if 'analysis_refusal_cause' in self.impl.ANALYSIS_SCHEMA['properties']:
    a['analysis_refusal_cause']='NONE' if good else 'MISSING_EVIDENCE'
    for req in a['requirement_support']:
     required=next(x for x in request.query_profile['requirements'] if x['requirement_id']==req['requirement_id'])
     req.update(answer_form='NAMED_ENTITY' if required.get('answer_kind')=='NAMED_IDENTITY' else 'INSTANCE' if required.get('answer_kind')=='INSTANCE' else 'OTHER',identity_identified=good,relation_and_qualifiers_supported=good,complete_answer=good,referent_resolved=True)
   return SimpleNamespace(content=json.dumps(a),model='controlled')
  if kind=='shared_control':
   # Control independence is inspected separately; mock is used only for CFAF functional assertions.
   result={'answer':'Controlled independent response.','top_level_mode':'CFAF','fulfilment_status':'NONE','realization':'ABSTAIN','public_reason_class':'EVIDENTIAL','next_step_codes':[]}
  else:
   c=payload['response_contract'];result={'answer':c['answer_candidate'] if c['mode']=='FULL' else c['public_reason_text'],'top_level_mode':c['mode'],'fulfilment_status':c['fulfilment_status'],'realization':c['realization'],'public_reason_class':c['public_reason_class'],'next_step_codes':[]}
  return SimpleNamespace(content=json.dumps(result),model='controlled')
