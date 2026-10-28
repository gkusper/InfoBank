"""No-retry, pre-call guarded provider with durable per-run attempt caps."""
import hashlib,json,time
from pathlib import Path
from evaluation.wolala2026.real_api import OpenAIProvider
from evaluation.refusalbench_span_fix_v1.api_budget import append_jsonl,read_jsonl,utc,redact
from evaluation.refusalbench_span_fix_v1.contracts import GENERATION_SCHEMA
from .integration import ANALYSIS_SCHEMA
from .metadata_binding import assert_safe_payload,canonical

class GovernedProvider(OpenAIProvider):
 def __init__(self,out,cap):
  super().__init__(generator_model='gpt-4o-mini',timeout_seconds=60)
  self.out=Path(out);self.out.mkdir(parents=True,exist_ok=True);self.cap=cap;self.kind=None;self.index=None
  ledger=self.out/'api_requests.jsonl';self.attempts=len(read_jsonl(ledger)) if ledger.exists() else 0
 def call(self,request,kind,prompt,payload,limit):
  assert_safe_payload(request,payload)
  if kind=='shared_control':
   if any(k in payload for k in ['response_contract','selected_mode','can_fulfil_request','fulfilment_flag']):raise ValueError('CONTROL_CONTAMINATED')
  self.kind=kind;self.request=request
  return self.generate_json(mode_name=kind,system_prompt=prompt,user_payload=payload,max_output_tokens=limit)
 def _post_json(self,path,payload):
  if path!='/chat/completions' or self.attempts>=self.cap:raise RuntimeError('ENDPOINT_OR_BUDGET_VIOLATION')
  assert_safe_payload(self.request,json.loads(payload['messages'][1]['content']))
  if payload['model']!='gpt-4o-mini' or payload['temperature']!=0 or payload['max_tokens']!=(1500 if self.kind=='semantic_analysis' else 160):raise RuntimeError('FROZEN_SETTINGS_VIOLATION')
  schema=ANALYSIS_SCHEMA if self.kind=='semantic_analysis' else GENERATION_SCHEMA
  payload['response_format']={'type':'json_schema','json_schema':{'name':'assessment' if self.kind=='semantic_analysis' else 'public_response','strict':True,'schema':schema}}
  self.attempts+=1;start=time.perf_counter()
  append_jsonl(self.out/'api_requests.jsonl',{'attempt':self.attempts,'runtime_index':self.index,'kind':self.kind,'payload':payload,'started_at_utc':utc(),'pre_call_policy_validation':'PASS','request_signature':self.request.signature(),'payload_sha256':hashlib.sha256(canonical(payload).encode()).hexdigest()})
  try:
   response=super()._post_json(path,payload)
  except Exception as exc:
   append_jsonl(self.out/'api_events.jsonl',{'attempt':self.attempts,'kind':self.kind,'status':'ERROR','error':redact(str(exc)),'latency_ms':(time.perf_counter()-start)*1000});raise
  choice=response['choices'][0]
  append_jsonl(self.out/'api_events.jsonl',{'attempt':self.attempts,'kind':self.kind,'status':'SUCCESS','usage':response.get('usage'),'finish_reason':choice.get('finish_reason'),'message':choice['message'],'model':response.get('model'),'response_id':response.get('id'),'latency_ms':(time.perf_counter()-start)*1000})
  return response

