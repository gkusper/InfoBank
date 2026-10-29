"""Fresh per-system worker; C1 loads only the completed v1 snapshot."""
from common import *
import os,sys,argparse,functools

def main():
 parser=argparse.ArgumentParser();parser.add_argument('system',choices=['A','C1','C2']);parser.add_argument('index',type=int);args=parser.parse_args();ensure(api=True);verify_freeze();state=read(STATE)
 package=Path(state['snapshot'])/'src' if args.system in {'A','C1'} else ROOT/'src';sys.path.insert(0,str(package))
 import component_cfaf.pipeline as core
 assert Path(core.__file__).resolve().is_relative_to(package.resolve())
 from component_cfaf.contracts import Authority,RawSource,AccessDecision,StandardAnswer
 from component_cfaf.pipeline import Pipeline
 from component_cfaf.adapters.local import LegacyGovernance
 from component_cfaf.adapters.openai_sdk import SDKProvider
 from component_cfaf.baseline import guard
 from component_cfaf.render import NO_SUPPORT
 if args.system=='C2':
  from component_cfaf.compact import CompactSDKProvider
  provider=CompactSDKProvider(ledger=OUT/'local/api_ledger.jsonl',deadline_epoch=state['start_epoch']+6300,attempt_cap=100)
 else:provider=SDKProvider(ledger=OUT/'local/api_ledger.jsonl',deadline_epoch=state['start_epoch']+6300,attempt_cap=100)
 timing={'gate_ms':0,'render_ms':0,'public_validation_ms':0}
 def timed(name,fn):
  @functools.wraps(fn)
  def call(*a,**kw):
   start=time.perf_counter()
   try:return fn(*a,**kw)
   finally:timing[name]+=(time.perf_counter()-start)*1000
  return call
 core.decide=timed('gate_ms',core.decide);core.DeterministicRenderer.render=timed('render_ms',core.DeterministicRenderer.render);Pipeline._validate_public=staticmethod(timed('public_validation_ms',Pipeline._validate_public))
 row=rows(ROOT/'results/local/inputs.jsonl')[args.index];policies={};sources=[]
 for i,s in enumerate(row['sources']):
  sid='private-'+str(i);extra={'catalogue_title':s.get('title')} if args.system=='C2' else {}
  sources.append(RawSource(private_id=sid,content=s.get('content',''),metadata=s.get('metadata') or {},public_metadata={},private_markers=s.get('protected_markers') or [],**extra));policies[sid]=AccessDecision(access=s.get('access_mode','DENY'),existence_public=s.get('existence_visibility','PUBLIC')=='PUBLIC',metadata_fields=s.get('allowed_metadata_fields',[]),aggregate_view=s.get('aggregate_view'),compatible=s.get('purpose_compatibility','compatible')=='compatible' and s.get('retrieved',True),clean=s.get('security_status','clean')=='clean')
 pipeline=Pipeline(LegacyGovernance(lambda s,a:policies[s.private_id]),provider);authority=Authority(principal='development-smoke',purpose='bounded-research',policy_version='component-v1-fixture-ingestion',revocation_version='0',request_id='smoke-'+str(row['index']));start=time.perf_counter();request,evidence,private=pipeline.prepare(row['query'],sources,authority,row.get('as_of'));record={'index':row['index'],'dataset':row['dataset'],'system':args.system,'context_identity_sha256':hashlib.sha256(json.dumps([(v.source_id,v.view_kind,v.text) for v in evidence.views],sort_keys=True).encode()).hexdigest(),'loaded_package':str(package),'prepare_ms':(time.perf_counter()-start)*1000}
 if args.system=='A':
  if not evidence.views or not request.requirements:a=StandardAnswer(mode='CFAF',answer=NO_SUPPORT);usage={'attempts':0,'input_tokens':0,'output_tokens':0,'provider_ms':0};status='SUCCESS'
  else:a,usage,status=provider.standard(request,evidence)
  before=time.perf_counter();b,bs=guard(a,private.get('blocked_values',[]));post_ms=(time.perf_counter()-before)*1000
  record.update(response=a.model_dump(mode='json') if a else None,execution_status=status,usage=usage,B={'response':b.model_dump(mode='json'),'execution_status':status if status!='SUCCESS' else bs,'postprocess_ms':post_ms})
 else:
  result=pipeline.complete(request,evidence,private);record.update(result=result.model_dump(mode='json'),response=result.response.model_dump(mode='json'),execution_status=result.decision.execution_status,usage=result.usage)
 record.update(timing=timing,system_end_to_end_ms=(time.perf_counter()-start)*1000)
 events=[e for e in provider.events if e['event']=='RESULT'];raw=(events[-1].get('response') or {}) if events else {};choices=raw.get('choices') or [];content=(choices[0].get('message') or {}).get('content') if choices else '';record['proposal_bytes']=len((content or '').encode('utf-8'));record['provider_finish_reason']=choices[0].get('finish_reason') if choices else None
 write(OUT/f'local/{args.index:02d}_{args.system}.json',record);print(args.index+1,args.system,record['execution_status'],record['response'].get('mode') if record.get('response') else None,flush=True)
if __name__=='__main__':main()
