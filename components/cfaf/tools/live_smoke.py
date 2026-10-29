"""Paired A/B/C1 development smoke. No gold/IDs are sent to the provider."""
from common import *
import argparse,os,datetime
from component_cfaf.contracts import *
from component_cfaf.pipeline import Pipeline
from component_cfaf.adapters.local import LegacyGovernance
from component_cfaf.adapters.openai_sdk import SDKProvider
from component_cfaf.baseline import guard
from component_cfaf.render import NO_SUPPORT

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--allow-live',action='store_true');parser.add_argument('--concurrent-experiment',action='store_true');args=parser.parse_args();ensure();verify_freeze()
    if args.concurrent_experiment:
        write(ROOT/'results/live_status.json',{'status':'NOT_RUN_CONCURRENT_EXPERIMENT','attempts':0});return
    if not args.allow_live or not os.getenv('OPENAI_API_KEY'):
        write(ROOT/'results/live_status.json',{'status':'NOT_RUN','reason':'Explicit --allow-live and API key required','attempts':0});return
    assert read(ROOT/'results/concurrency_clearance.json')['same_account_other_active_experiment_observed'] is False
    target=ROOT/'results/local/live_results.jsonl';ledger=ROOT/'results/local/api_ledger.jsonl';assert not target.exists() and not ledger.exists(),'Never repeat the pilot'
    state=read(STATE);provider=SDKProvider(ledger=ledger,deadline_epoch=state['start_epoch']+6300,attempt_cap=100)
    for row in rows(ROOT/'results/local/inputs.jsonl'):
        ensure(new_api=True);verify_freeze();start=time.perf_counter();record={'index':row['index'],'dataset':row['dataset'],'status':'COMPLETED'}
        try:
            policies={};sources=[]
            for i,s in enumerate(row['sources']):
                sid='private-'+str(i);sources.append(RawSource(private_id=sid,content=s.get('content',''),metadata=s.get('metadata') or {},public_metadata={},private_markers=s.get('protected_markers') or []))
                policies[sid]=AccessDecision(access=s.get('access_mode','DENY'),existence_public=s.get('existence_visibility','PUBLIC')=='PUBLIC',metadata_fields=s.get('allowed_metadata_fields',[]),aggregate_view=s.get('aggregate_view'),compatible=s.get('purpose_compatibility','compatible')=='compatible' and s.get('retrieved',True),clean=s.get('security_status','clean')=='clean')
            governance=LegacyGovernance(lambda s,a:policies[s.private_id]);pipeline=Pipeline(governance,provider)
            authority=Authority(principal='development-smoke',purpose='bounded-research',policy_version='component-v1-fixture-ingestion',revocation_version='0',request_id='smoke-'+str(row['index']))
            request,evidence,private=pipeline.prepare(row['query'],sources,authority,row.get('as_of'))
            if not evidence.views or not request.requirements:a=StandardAnswer(mode='CFAF',answer=NO_SUPPORT);au={'attempts':0,'input_tokens':0,'output_tokens':0,'provider_ms':0};astatus='SUCCESS'
            else:a,au,astatus=provider.standard(request,evidence)
            before=time.perf_counter();b,bstatus=guard(a,private.get('blocked_values',[]));b_ms=(time.perf_counter()-before)*1000
            if astatus!='SUCCESS':bstatus=astatus
            result=pipeline.complete(request,evidence,private)
            record.update(A=a.model_dump(mode='json') if a else None,A_status=astatus,A_usage=au,B=b.model_dump(mode='json'),B_status=bstatus,B_postprocess_ms=b_ms,C1=result.model_dump(mode='json'),evidence_sha256=hashlib.sha256(json.dumps([v.model_dump(mode='json') for v in evidence.views],sort_keys=True).encode()).hexdigest(),context_units=len(evidence.views),context_truncated=False)
        except Exception as exc:record.update(status='ERROR',error_type=type(exc).__name__)
        record['elapsed_ms']=(time.perf_counter()-start)*1000;append(target,record)
        print(row['index']+1,row['dataset'],record['status'],record.get('A_status'),record.get('C1',{}).get('decision',{}).get('execution_status'),flush=True)
        if record.get('A_status') in {'PROVIDER_HTTP_401','PROVIDER_HTTP_403','PROVIDER_HTTP_429','CONNECTION_ERROR'}:break
    verify_freeze();write(ROOT/'results/live_status.json',{'status':'COMPLETED' if len(rows(target))==30 else 'PARTIAL','selected':30,'recorded':len(rows(target)),'actual_attempts':provider.attempts,'no_resampling':True,'no_retries':True,'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
if __name__=='__main__':main()
