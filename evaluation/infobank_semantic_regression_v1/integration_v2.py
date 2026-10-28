"""Governed eight-stage semantic entry point. Historical modules are unchanged."""
from __future__ import annotations
import copy,json,time
from evaluation.wolala2026.labels import *
from evaluation.wolala2026.pipeline import TopLevelModeSelectionStage,RunContext,assert_pipeline_invariants
from evaluation.wolala2026.semantic_evidence import fulfilment_issues,_schema_errors,unknown_assessment
from evaluation.refusalbench_span_fix_v1.span_references import (REFERENCE_SCHEMA,ANALYSIS_PROMPT,build_catalogue,catalogue_payload,resolve_span,parse_reference_assessment)
from evaluation.refusalbench_span_fix_v1.contracts import GENERATION_SCHEMA,COMMON_INSTRUCTIONS,validate_response
from .policy_projection import *

ANALYSIS_SCHEMA=copy.deepcopy(REFERENCE_SCHEMA)
ANALYSIS_SCHEMA['properties'].update({
 'request_scope':{'type':'string','enum':['AGGREGATE','METADATA','INDIVIDUAL','CONTENT','ACTION','UNKNOWN']},
 'source_assessments':{'type':'array','items':{'type':'object','properties':{
  'source_id':{'type':'string'},'role':{'type':'string','enum':['PRIMARY','CONTEXTUAL','CONTRASTIVE','IRRELEVANT','UNKNOWN']},
  'relation_label':{'type':'string','enum':['SUPPORTS','REFUTES','NONE']},
  'grounding_span_ids':{'type':'array','items':{'type':'string'}},'rationale':{'type':'string'}},
  'required':['source_id','role','relation_label','grounding_span_ids','rationale'],'additionalProperties':False}}})
ANALYSIS_SCHEMA['required']+=['request_scope','source_assessments']
GOVERNED_PROMPT=ANALYSIS_PROMPT+'''
Infer request_scope from the actual question and each source role from permitted text and provenance. No fixture labels or prepared answers are provided. PRIMARY means direct evidence for the requested fact, not merely relevance or retrieval. Cite grounding_span_ids for each source role. Browser history, an opened page or past coordination alone cannot establish a recorded obligation or next action. An explicit current task note can establish a recorded next action. An authorized aggregate can fully answer a count/aggregate question; an authorized metadata view can fully answer a metadata question. Neither establishes individual records or body text. Determine sufficiency relative to the actual requested scope. Do not treat restricted access alone as missing evidence when the requested scope is satisfied. Generate answer_candidate from the permitted views. Keep rationales brief. Do not infer hidden sources. This task does not require general contradiction detection beyond supplied evidence.'''
CONTROL_PROMPT='''Answer the actual question using only permitted documents and the shared semantic assessment. Independently choose FULL if the requested information is completely supported at the requested scope, otherwise CFAF with an explanation. Do not claim unavailable individual details, body text, obligations or hidden sources. Copy a grounded candidate if appropriate. Return the common public response JSON.'''+COMMON_INSTRUCTIONS
CFAF_PROMPT='''Realize response_contract exactly. Copy answer_candidate verbatim for FULL. For CFAF write the nonempty public_reason_text, never a null answer. Use the contract mode and fulfilment_status, empty next_step_codes. Do not add facts or source-existence claims. Return the common public response JSON.'''+COMMON_INSTRUCTIONS


def public_trace(response):
 return {k:response[k] for k in ['answer','top_level_mode','fulfilment_status','realization','public_reason_class','next_step_codes']}


def deterministic_response():
 return {'answer':CANONICAL_NO_SUPPORT,'top_level_mode':'CFAF','fulfilment_status':'NONE','realization':'ABSTAIN','public_reason_class':'EVIDENTIAL','next_step_codes':[]}


def parse_analysis(raw,request):
 docs={d['source_id']:d['context'] for d in request.documents};cat=build_catalogue(docs)
 try:data=json.loads(raw)
 except (ValueError,TypeError):return unknown_assessment(['INVALID_JSON'],'gpt-4o-mini'),{}, {'valid':False,'errors':['INVALID_JSON']}
 errors=_schema_errors(data,ANALYSIS_SCHEMA)
 if errors:return unknown_assessment(errors,'gpt-4o-mini'),data,{'valid':False,'errors':errors}
 seen=[]
 for role in data['source_assessments']:
  sid=role['source_id'];seen.append(sid)
  if sid not in docs:errors.append('ROLE_UNKNOWN_SOURCE')
  # Inconsistent inferred roles are semantic errors, not schema/security failures.
  for reference in role['grounding_span_ids']:
   try:
    span=resolve_span(reference,docs,cat)
    if span['source_id']!=sid:errors.append('ROLE_REFERENCE_SOURCE_MISMATCH')
   except ValueError as exc:errors.append(str(exc))
 if sorted(seen)!=sorted(docs):errors.append('SOURCE_ROLE_COVERAGE_INVALID')
 base={k:v for k,v in data.items() if k in REFERENCE_SCHEMA['properties']}
 assessment,audit=parse_reference_assessment(json.dumps(base),docs,cat,'gpt-4o-mini')
 if errors:assessment=unknown_assessment(errors,'gpt-4o-mini');audit.update(valid=False,errors=errors)
 return assessment,data,audit


def analyze(request,provider):
 docs={d['source_id']:d['context'] for d in request.documents}
 payload={**request.public(),'span_catalogue':catalogue_payload(docs,build_catalogue(docs))}
 call=provider.call(request,'semantic_analysis',GOVERNED_PROMPT,payload,1500)
 assessment,data,audit=parse_analysis(call.content,request)
 return assessment,data,audit


def support_issues(assessment,data,request):
 issues=fulfilment_issues(assessment)
 if not assessment.valid:return issues
 roles={r['source_id']:r for r in data.get('source_assessments',[])}
 documents={d['source_id']:d for d in request.documents}
 for span in assessment.data['supporting_spans']:
  role=roles.get(span['source_id'],{})
  if role.get('role')!='PRIMARY' or role.get('relation_label')!='SUPPORTS':issues.append('SUPPORT_NOT_PRIMARY')
  kind=documents[span['source_id']]['view_kind'];scope=data.get('request_scope')
  if kind=='aggregate' and scope!='AGGREGATE' or kind=='metadata' and scope!='METADATA':issues.append('REQUEST_EXCEEDS_PERMITTED_VIEW')
 return sorted(set(issues))


def run_governed(case,provider):
 request=project_case(case)
 state=PipelineState(case_id='local-request',query_id='query',query=request.query)
 context=RunContext(case={'query':request.query},trace_id='internal-only')
 assessment=None;data={};audit={};issues=[];responses={};contracts={};raw={};start=time.perf_counter()
 for stage in StageName:
  before=time.perf_counter()
  if stage==StageName.QUERY_PROFILING:
   state.query_profile={'query':request.query};state.required_claims=[{'claim_id':'claim-1','requested_content':request.query}]
  elif stage==StageName.CANDIDATE_RETRIEVAL:
   for i,doc in enumerate(request.documents):
    access={'content':AccessMode.FULL,'aggregate':AccessMode.AGGREGATE,'metadata':AccessMode.METADATA}[doc['view_kind']]
    state.candidates.append(EvidenceCandidate(doc['source_id'],doc['source_id'],doc['source_type'],i+1,None,'permitted_projection','policy_authorized','',doc['context'] if access==AccessMode.FULL else '[RESTRICTED_RAW_NOT_LOADED]',metadata=json.loads(doc['context']) if access==AccessMode.METADATA else {},access_mode=access,aggregate_view=doc['context'] if access==AccessMode.AGGREGATE else None,purpose_compatibility='compatible'))
  elif stage==StageName.ACCESS_AND_SAFETY_RESOLUTION:
   assert_safe_payload(request,request.public())
   for candidate in state.candidates:
    candidate.disposition={AccessMode.FULL:Disposition.DIRECT_USE,AccessMode.AGGREGATE:Disposition.AGGREGATE_ONLY,AccessMode.METADATA:Disposition.METADATA_ONLY}[candidate.access_mode]
  elif stage==StageName.EVIDENCE_LABELLING:
   if request.documents:
    assessment,data,audit=analyze(request,provider)
    for candidate in state.candidates:
     role=next((r for r in data.get('source_assessments',[]) if r['source_id']==candidate.source_id),{})
     if assessment.valid:
      candidate.evidential_role=EvidentialRole(role.get('role','UNKNOWN'));candidate.relation=RelationLabel(role.get('relation_label','NONE'))
    state.query_profile.update({k:data.get(k) for k in ['requested_information','request_scope','query_status']})
  elif stage==StageName.SUFFICIENCY_AND_PERMITTED_OUTPUT:
   issues=support_issues(assessment,data,request) if assessment else ['NO_PERMITTED_EVIDENCE']
   full=not issues
   state.claim_assessments=[ClaimAssessment('claim-1',assessment.data['support_status'] if assessment else 'MISSING',list({s['source_id'] for s in assessment.data['supporting_spans']}) if assessment else [],[],full,'REQUESTED_OUTPUT' if full else 'NONE',data.get('available_granularity','none'),data.get('requested_granularity','unknown'),full,assessment.data['answer_candidate'] if full else None,None if full else ReasonClass.EVIDENTIAL,None if full else issues[0],None if full else CFAFRealization.ABSTAIN)]
  elif stage==StageName.TOP_LEVEL_MODE_SELECTION:
   state=TopLevelModeSelectionStage().run(state,context)
  elif stage==StageName.RESPONSE_REALIZATION:
   if not request.documents:
    # Both systems independently use the identical public zero-evidence rule.
    responses={name:deterministic_response() for name in ['semantic_cfaf','shared_control']}
   else:
    shared={**request.public(),'semantic_assessment':data}
    decision=state.mode_decision;full=decision.mode==TopLevelMode.FULL
    contract={'mode':decision.mode.value,'fulfilment_status':decision.fulfilment_status.value,'realization':None if full else 'ABSTAIN','public_reason_class':None if full else 'EVIDENTIAL','public_reason_text':'' if full else CANONICAL_NO_SUPPORT,'answer_candidate':state.claim_assessments[0].answer}
    state.response_contract=ResponseContract(decision.mode,decision.fulfilment_status,None if full else CFAFRealization.ABSTAIN,[],request.documents,[],None if full else ReasonClass.EVIDENTIAL,contract['public_reason_text'],[])
    contracts['semantic_cfaf']=contract
    for name,prompt,payload in [('semantic_cfaf',CFAF_PROMPT,{**shared,'response_contract':contract}),('shared_control',CONTROL_PROMPT,shared)]:
     call=provider.call(request,name,prompt,payload,160);raw[name]=call.content
     errors=validate_response(call.content)
     if errors:raise RuntimeError('GENERATION_SCHEMA_FAILURE:'+name+':'+','.join(errors))
     response=json.loads(call.content)
     assert_safe_payload(request,{**request.public(),'response':response})
     if name=='semantic_cfaf':
      if response['top_level_mode']!=decision.mode.value or response['fulfilment_status']!=decision.fulfilment_status.value:raise RuntimeError('MODE_OR_FULFILMENT_INVARIANT_FAILURE')
      if full and response['answer']!=contract['answer_candidate']:raise RuntimeError('FULL_ANSWER_COPY_INVARIANT_FAILURE')
     responses[name]=response
    state.generator_context=request.documents
  elif stage==StageName.VALIDATION_TRACE_AND_FEEDBACK:
   for response in responses.values():
    errors=validate_response(json.dumps(response))
    if errors:raise RuntimeError('PUBLIC_SCHEMA_INVALID')
    if response['top_level_mode']=='FULL' and response['fulfilment_status']!='FULL':raise RuntimeError('FULL_STATUS_INCONSISTENT')
   state.final_response=json.dumps(responses['semantic_cfaf']);state.validation=ValidationResult(ValidationStatus.PASS,[],False)
  state.stage_timings[stage.value.lower()+'_ms']=(time.perf_counter()-before)*1000
 state.stage_timings['end_to_end_ms']=(time.perf_counter()-start)*1000
 assert_pipeline_invariants(state)
 return {'case_id':case['case_id'],'pair_id':case['pair_id'],'family':case['family'],'variant':case['variant'],'request_signature':request.signature(),'permitted_request':request.public(),'semantic_assessment':data if request.documents else None,'reference_audit':audit,'semantic_valid':assessment.valid if assessment else None,'fulfilment_issues':issues,'selected_mode':state.mode_decision.mode.value,'responses':responses,'public_traces':{n:public_trace(r) for n,r in responses.items()},'internal_trace':{'policy':request.internal_policy,'stage_sequence':[s.value for s in StageName],'stage_timings':state.stage_timings,'invariant_validation':'PASS'},'raw_generations':raw,'deterministic_no_view':not request.documents}

