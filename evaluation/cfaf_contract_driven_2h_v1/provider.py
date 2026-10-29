"""Single ledger, no embeddings/judges/retries, three-call paired study provider."""
import json,time,hashlib
from evaluation.wolala2026.real_api import OpenAIProvider
from evaluation.refusalbench_span_fix_v1.api_budget import redact
from evaluation.cfaf_sparse_source_repair_v1.provider import FORBIDDEN_FIELDS,GOLD_KEYS,all_keys
from evaluation.cfaf_dataset3_garage_pilot_v1.adapter import INPUT_BUDGET,byte_upper_bound
from . import measured_c as impl
from .artifacts import *
from .deadline import ensure
class StudyProvider(OpenAIProvider):
 def __init__(self):
  super().__init__(generator_model='gpt-4o-mini',timeout_seconds=45);self.dataset=None;self.index=None;self.kind=None;self.request=None;self.query_context={};self.private_mapping=[];self.case_calls=[]
 def call(self,request,kind,prompt,payload,limit):
  impl.assert_safe_payload(request,payload)
  if set(all_keys(payload))&(FORBIDDEN_FIELDS|GOLD_KEYS):raise ValueError('BENCHMARK_FIELD_IN_MODEL_INPUT')
  if kind=='shared_control':raise ValueError('UNMEASURED_FOURTH_CALL_DISABLED')
  if kind=='standard_rag' and set(payload)&{'semantic_assessment','response_contract','selected_mode','verification','inventory_states'}:raise ValueError('STANDARD_RAG_CONTAMINATION')
  payload=json.loads(json.dumps(payload))
  if kind!='query_profile':payload['query_context']=self.query_context
  self.kind=kind;self.request=request;limit=1500 if kind=='semantic_analysis' else 500 if kind=='query_profile' else 512
  result=self.generate_json(mode_name=kind,system_prompt=prompt,user_payload=payload,max_output_tokens=limit)
  self.case_calls.append({'kind':kind,'content':result.content,'model':result.model,'input_tokens':result.input_tokens,'output_tokens':result.output_tokens,'latency_ms':result.latency_ms,'response_id':result.response_id});return result
 def _post_json(self,path,payload):
  ledger=ROOT/'api_requests.jsonl';n=len(rows(ledger)) if ledger.exists() else 0
  if n>=480:raise RuntimeError('480_API_ATTEMPT_CAP_EXHAUSTED')
  ensure('external model attempt',45,new_api=True)
  if path!='/chat/completions':raise ValueError('OTHER_ENDPOINTS_DISABLED')
  limits={'standard_rag':512,'semantic_analysis':1500,'semantic_cfaf':512,'query_profile':500}
  if self.kind not in limits or payload['model']!='gpt-4o-mini' or payload['temperature']!=0 or payload['max_tokens']!=limits[self.kind]:raise ValueError('FROZEN_MODEL_SETTINGS_VIOLATION')
  user=json.loads(payload['messages'][1]['content']);impl.assert_safe_payload(self.request,user)
  if set(all_keys(user))&(FORBIDDEN_FIELDS|GOLD_KEYS):raise ValueError('FORBIDDEN_GOLD_FIELD')
  schema=impl.PROFILE_SCHEMA if self.kind=='query_profile' else impl.ANALYSIS_SCHEMA if self.kind=='semantic_analysis' else impl.GENERATION_SCHEMA
  payload['response_format']={'type':'json_schema','json_schema':{'name':'structured_response','strict':True,'schema':schema}};bound=byte_upper_bound(payload)
  if bound>INPUT_BUDGET:raise ValueError('PREDECLARED_INPUT_BUDGET_EXCEEDED')
  attempt=n+1;append(ledger,{'attempt':attempt,'dataset':self.dataset,'runtime_index':self.index,'kind':self.kind,'started_at_epoch':time.time(),'request_signature':self.request.signature(),'input_token_upper_bound':bound,'pre_call_policy_validation':'PASS','payload_sha256':hashlib.sha256(canonical(payload).encode()).hexdigest(),'payload':payload});start=time.perf_counter()
  try:response=super()._post_json(path,payload)
  except Exception as exc:
   append(ROOT/'api_events.jsonl',{'attempt':attempt,'dataset':self.dataset,'runtime_index':self.index,'kind':self.kind,'status':'ERROR','error':redact(str(exc)),'latency_ms':(time.perf_counter()-start)*1000});raise
  choice=response['choices'][0];append(ROOT/'api_events.jsonl',{'attempt':attempt,'dataset':self.dataset,'runtime_index':self.index,'kind':self.kind,'status':'SUCCESS','usage':response.get('usage'),'finish_reason':choice.get('finish_reason'),'model':response.get('model'),'response_id':response.get('id'),'message':choice['message'],'latency_ms':(time.perf_counter()-start)*1000});return response
