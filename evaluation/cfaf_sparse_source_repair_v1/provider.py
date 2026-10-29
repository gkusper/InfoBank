"""No gold enters runtime. Bounded provider uses the unchanged T3 prompts/schema."""
import hashlib,json,time
from types import SimpleNamespace
from evaluation.wolala2026.real_api import OpenAIProvider
from evaluation.refusalbench_noncontradiction_v1.public_adapter import FORBIDDEN_FIELDS,all_keys
from evaluation.refusalbench_span_fix_v1.api_budget import redact
from . import integration as impl
from .artifacts import *
from .deadline import ensure
from evaluation.cfaf_dataset3_garage_pilot_v1.adapter import GOLD_KEYS,INPUT_BUDGET,byte_upper_bound
FORBIDDEN_FIELDS=FORBIDDEN_FIELDS|{"sample_id"}
class BoundedProvider(OpenAIProvider):
 def __init__(self):
  super().__init__(generator_model='gpt-4o-mini',timeout_seconds=45);self.index=None;self.system='SPARSE_T3';self.case_calls=[];self.kind=None;self.request=None;self.query_context={}
 def call(self,request,kind,prompt,payload,limit):
  impl.assert_safe_payload(request,payload)
  if set(all_keys(payload))&(FORBIDDEN_FIELDS|GOLD_KEYS):raise ValueError('FORBIDDEN_BENCHMARK_FIELD')
  if kind=='shared_control' and set(payload)&{'response_contract','selected_mode','can_fulfil_request','fulfilment_flag','verification'}:raise ValueError('CONTROL_GATE_CONTAMINATION')
  payload=json.loads(json.dumps(payload))
  if kind!='query_profile':payload['query_context']=self.query_context
  self.kind=kind;self.request=request
  result=self.generate_json(mode_name=kind,system_prompt=prompt,user_payload=payload,max_output_tokens=512 if kind in {'semantic_cfaf','shared_control'} else limit)
  self.case_calls.append({'kind':kind,'content':result.content,'model':result.model,'input_tokens':result.input_tokens,'output_tokens':result.output_tokens,'latency_ms':result.latency_ms,'response_id':result.response_id});return result
 def _post_json(self,path,payload):
  ledger=ROOT/'api_requests.jsonl';n=len(rows(ledger)) if ledger.exists() else 0
  if n>=75:raise RuntimeError('75 API attempt cap exhausted')
  ensure('external API attempt',45,new_api=True)
  if path!='/chat/completions':raise ValueError('OTHER_ENDPOINTS_DISABLED')
  limits={'semantic_analysis':1500,'query_profile':500,'semantic_cfaf':512,'shared_control':512}
  if self.kind not in limits or payload['model']!='gpt-4o-mini' or payload['temperature']!=0 or payload['max_tokens']!=limits[self.kind]:raise ValueError('FROZEN_MODEL_SETTINGS_VIOLATED')
  user=json.loads(payload['messages'][1]['content']);impl.assert_safe_payload(self.request,user)
  if set(all_keys(user))&(FORBIDDEN_FIELDS|GOLD_KEYS):raise ValueError('GOLD_IN_REQUEST')
  schema=impl.PROFILE_SCHEMA if self.kind=='query_profile' else impl.ANALYSIS_SCHEMA if self.kind=='semantic_analysis' else impl.GENERATION_SCHEMA
  payload['response_format']={'type':'json_schema','json_schema':{'name':'structured_response','strict':True,'schema':schema}}
  bound=byte_upper_bound(payload)
  if bound>INPUT_BUDGET:raise ValueError('DECLARED_INPUT_BUDGET_EXCEEDED')
  attempt=n+1;append(ledger,{'attempt':attempt,'runtime_index':self.index,'system':self.system,'kind':self.kind,'started_at_epoch':time.time(),'input_token_upper_bound':bound,'request_signature':self.request.signature(),'pre_call_policy_validation':'PASS','payload':payload,'payload_sha256':hashlib.sha256(canonical(payload).encode()).hexdigest()});start=time.perf_counter()
  try:response=super()._post_json(path,payload)
  except Exception as exc:
   append(ROOT/'api_events.jsonl',{'attempt':attempt,'runtime_index':self.index,'kind':self.kind,'status':'ERROR','error':redact(str(exc)),'latency_ms':(time.perf_counter()-start)*1000});raise
  choice=response['choices'][0];append(ROOT/'api_events.jsonl',{'attempt':attempt,'runtime_index':self.index,'kind':self.kind,'status':'SUCCESS','model':response.get('model'),'response_id':response.get('id'),'usage':response.get('usage'),'finish_reason':choice.get('finish_reason'),'message':choice['message'],'latency_ms':(time.perf_counter()-start)*1000});return response
