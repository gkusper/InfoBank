"""Deadline-aware provider with a durable 360-attempt task-wide ledger."""
import hashlib,json,time
from pathlib import Path
from evaluation.wolala2026.real_api import OpenAIProvider
from evaluation.refusalbench_span_fix_v1.api_budget import append_jsonl,read_jsonl,utc,redact
from evaluation.refusalbench_noncontradiction_v1.public_adapter import FORBIDDEN_FIELDS,all_keys
from .deadline import ensure
ROOT=Path(__file__).resolve().parent

def canonical(x):return json.dumps(x,ensure_ascii=True,sort_keys=True,separators=(',',':'))
class BoundedProvider(OpenAIProvider):
 def __init__(self,out,implementation):
  super().__init__(generator_model='gpt-4o-mini',timeout_seconds=45)
  self.out=Path(out);self.impl=implementation;self.index=None;self.kind=None;self.case_calls=[]
  ledger=ROOT/'global_api_requests.jsonl';self.attempts=len(read_jsonl(ledger)) if ledger.exists() else 0
 def call(self,request,kind,prompt,payload,limit):
  self.impl.assert_safe_payload(request,payload)
  if set(all_keys(payload))&FORBIDDEN_FIELDS:raise ValueError('Forbidden benchmark annotation in model input')
  if kind=='shared_control' and any(k in payload for k in ['response_contract','selected_mode','can_fulfil_request','fulfilment_flag']):raise ValueError('Control contaminated by gate')
  self.kind=kind;self.request=request
  result=self.generate_json(mode_name=kind,system_prompt=prompt,user_payload=payload,max_output_tokens=limit)
  self.case_calls.append({'kind':kind,'raw_content':result.content,'model':result.model,'input_tokens':result.input_tokens,'output_tokens':result.output_tokens,'latency_ms':result.latency_ms,'response_id':result.response_id})
  return result
 def _post_json(self,path,payload):
  ensure('API request',expected_seconds=45,new_api=True)
  ledger=ROOT/'global_api_requests.jsonl';actual=len(read_jsonl(ledger)) if ledger.exists() else 0
  if actual>=360:raise RuntimeError('Task-wide 360 attempt budget exhausted')
  if path!='/chat/completions':raise ValueError('Only analysis/generation allowed; embeddings disabled')
  self.impl.assert_safe_payload(self.request,json.loads(payload['messages'][1]['content']))
  if payload['model']!='gpt-4o-mini' or payload['temperature']!=0 or payload['max_tokens']!=({'semantic_analysis':1500,'query_profile':500}.get(self.kind,160)):raise ValueError('Frozen model settings violated')
  schema=self.impl.PROFILE_SCHEMA if self.kind=='query_profile' else self.impl.ANALYSIS_SCHEMA if self.kind=='semantic_analysis' else self.impl.GENERATION_SCHEMA
  payload['response_format']={'type':'json_schema','json_schema':{'name':'request_profile' if self.kind=='query_profile' else 'assessment' if self.kind=='semantic_analysis' else 'public_response','strict':True,'schema':schema}}
  self.attempts=actual+1
  request={'attempt':self.attempts,'round_directory':self.out.name,'runtime_index':self.index,'kind':self.kind,'started_at_utc':utc(),'payload':payload,'request_signature':self.request.signature(),'pre_call_policy_validation':'PASS','payload_sha256':hashlib.sha256(canonical(payload).encode()).hexdigest()}
  append_jsonl(ledger,request);append_jsonl(self.out/'api_requests.jsonl',request);start=time.perf_counter()
  try:response=super()._post_json(path,payload)
  except Exception as exc:
   event={'attempt':self.attempts,'round_directory':self.out.name,'runtime_index':self.index,'kind':self.kind,'status':'ERROR','error':redact(str(exc)),'latency_ms':(time.perf_counter()-start)*1000}
   append_jsonl(ROOT/'global_api_events.jsonl',event);append_jsonl(self.out/'api_events.jsonl',event);raise
  choice=response['choices'][0];event={'attempt':self.attempts,'round_directory':self.out.name,'runtime_index':self.index,'kind':self.kind,'status':'SUCCESS','usage':response.get('usage'),'finish_reason':choice.get('finish_reason'),'message':choice['message'],'model':response.get('model'),'response_id':response.get('id'),'latency_ms':(time.perf_counter()-start)*1000}
  append_jsonl(ROOT/'global_api_events.jsonl',event);append_jsonl(self.out/'api_events.jsonl',event)
  return response
