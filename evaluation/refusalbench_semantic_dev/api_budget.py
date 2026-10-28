"""Audited no-retry provider with a durable 225-attempt experiment-wide cap."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.error
from evaluation.wolala2026.real_api import OpenAIProvider
from evaluation.wolala2026.semantic_evidence import ASSESSMENT_SCHEMA

HARD_CAP=225


def canonical(value):return json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(',',':'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def utc():return dt.datetime.now(dt.timezone.utc).isoformat()
def write_json(path,obj):Path(path).write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
def read_jsonl(path):return [json.loads(x) for x in Path(path).read_text(encoding='utf-8').splitlines() if x]
def append_jsonl(path,obj):
    with Path(path).open('a',encoding='utf-8',newline='\n') as handle:
        handle.write(canonical(obj)+'\n');handle.flush();os.fsync(handle.fileno())
def redact(text):
    key=os.getenv('OPENAI_API_KEY')
    return text.replace(key,'<OPENAI_API_KEY>') if key else text


class BudgetProvider(OpenAIProvider):
    def __init__(self,out):
        super().__init__(generator_model='gpt-4o-mini',timeout_seconds=60)
        self.out=Path(out);self.index=None;self.kind=None;self.last_event=None;self.last_http_status=None
        ledger=self.out/'api_requests.jsonl'
        self.attempts=len(read_jsonl(ledger)) if ledger.exists() else 0
        self.blocker=None

    def generate_json(self,**kwargs):
        if self.blocker:raise RuntimeError('API circuit stopped: '+self.blocker)
        self.kind=kwargs['mode_name']
        return super().generate_json(**kwargs)

    def _post_json(self,path,payload):
        if path!='/chat/completions':raise RuntimeError('Only chat generation/analysis is permitted; embeddings disabled.')
        if self.attempts>=HARD_CAP:raise RuntimeError('Hard experiment budget of 225 API attempts exhausted.')
        if self.kind=='semantic_analysis':
            payload['response_format']={'type':'json_schema','json_schema':{'name':'semantic_evidence','strict':True,'schema':ASSESSMENT_SCHEMA}}
        if payload['model']!='gpt-4o-mini' or payload['temperature']!=0:raise RuntimeError('Frozen model/settings violated.')
        expected_limit=1500 if self.kind=='semantic_analysis' else 160
        if payload['max_tokens']!=expected_limit:raise RuntimeError('Frozen output limit violated.')
        self.attempts+=1;attempt=self.attempts;self.last_http_status=None
        append_jsonl(self.out/'api_requests.jsonl',{'attempt':attempt,'runtime_index':self.index,
            'kind':self.kind,'started_at_utc':utc(),'endpoint':path,'payload':payload,
            'payload_sha256':hashlib.sha256(canonical(payload).encode()).hexdigest()})
        start=time.perf_counter()
        try:response=super()._post_json(path,payload)
        except Exception as exc:
            cause=exc.__cause__;self.last_http_status=cause.code if isinstance(cause,urllib.error.HTTPError) else None
            message=redact(str(exc))
            if self.last_http_status in {401,403,429} or isinstance(cause,urllib.error.URLError):self.blocker=message
            event={'attempt':attempt,'runtime_index':self.index,'kind':self.kind,'status':'ERROR',
                'http_status':self.last_http_status,'error':message,'latency_ms':(time.perf_counter()-start)*1000}
            append_jsonl(self.out/'api_events.jsonl',event);self.last_event=event;raise
        choice=(response.get('choices') or [{}])[0]
        event={'attempt':attempt,'runtime_index':self.index,'kind':self.kind,'status':'SUCCESS',
            'latency_ms':(time.perf_counter()-start)*1000,'model':response.get('model'),
            'response_id':response.get('id'),'usage':response.get('usage'),
            'finish_reason':choice.get('finish_reason'),'message':choice.get('message'),
            'system_fingerprint':response.get('system_fingerprint')}
        append_jsonl(self.out/'api_events.jsonl',event);self.last_event=event
        return response
