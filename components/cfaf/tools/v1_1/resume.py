"""Continue the same interrupted experiment; never repeat an attempted model request."""
from common import *
import os,sys,datetime,collections

def main():
 ensure(api=True);verify_freeze();ledger=OUT/'local/api_ledger.jsonl';target=OUT/'local/paired_raw.jsonl';old=rows(target);done={r['index'] for r in old};inputs=rows(ROOT/'results/local/inputs.jsonl');events=rows(ledger);attempts=[e for e in events if e['event']=='ATTEMPT'];results=[e for e in events if e['event']=='RESULT'];assert {e['attempt'] for e in attempts}=={e['attempt'] for e in results},'An unsettled request must not be retried'
 remaining=[i for i in range(30) if i not in done];assert len({inputs[i]['query'] for i in remaining})==len(remaining),'Tail questions must be unique for recovery assignment'
 write(OUT/'recovery_audit.json',{'reason':'Original controller subprocess timeout interrupted assembly after a completed C1 connection-error result. No model/config change.','restart_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'attempts_before_recovery':len(attempts),'settled_before_recovery':len(results),'completed_pairs_preserved':len(done),'remaining_indices':remaining,'existing_partial_result_hashes':{p.name:sha(p) for i in remaining for p in (OUT/'local').glob(f'{i:02d}_*.json')},'recovery_scheduler_sha256':sha(Path(__file__)),'frozen_worker_unchanged':True,'retry_attempted_requests':False,'original_clock_and_100_attempt_cap_preserved':True,'process_wall_for_recovered_files':'Unknown; worker internal end-to-end timing remains measured'})
 consecutive_connection_failures=0
 for index in remaining:
  ensure(api=True);selected={};order=['A',*(['C1','C2'] if index%2==0 else ['C2','C1'])]
  for system in order:
   verify_freeze();file=OUT/f'local/{index:02d}_{system}.json'
   if file.exists():selected[system]=read(file);selected[system]['recovered_existing_result']=True;continue
   started=[e for e in rows(ledger) if e['event']=='ATTEMPT' and e['kind']==system and json.loads(e['payload']['messages'][1]['content'])['query']==inputs[index]['query']]
   if started:selected[system]={'index':index,'system':system,'execution_status':'ALREADY_ATTEMPTED_RESULT_UNAVAILABLE','usage':{'attempts':len(started)}};continue
   ensure(api=True);assert sum(e['event']=='ATTEMPT' for e in rows(ledger))<100;env=os.environ.copy();env['TEMP']=env['TMP']=str(WORK/'tmp');env['PYTHONIOENCODING']='utf-8';start=time.perf_counter()
   try:p=subprocess.run([sys.executable,str(Path(__file__).with_name('worker.py')),system,str(index)],cwd=REPO,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding='utf-8',errors='replace',timeout=120);out=p.stdout
   except subprocess.TimeoutExpired:out='Worker process deadline; result retained if available; no retry'
   if file.exists():result=read(file);result['process_wall_ms']=(time.perf_counter()-start)*1000;selected[system]=result
   else:selected[system]={'index':index,'system':system,'execution_status':'WORKER_ERROR_OR_TIMEOUT','usage':{'attempts':1},'private_error':out[-2000:]}
   print(out.strip()[-250:],flush=True)
   status=selected[system]['execution_status'];consecutive_connection_failures=consecutive_connection_failures+1 if status=='CONNECTION_ERROR' else 0
  append(target,{'index':index,'dataset':inputs[index]['dataset'],'order':order,'systems':selected,'recovered_controller':True})
  if consecutive_connection_failures>=3 or any(v.get('execution_status') in {'PROVIDER_HTTP_401','PROVIDER_HTTP_403','PROVIDER_HTTP_429'} for v in selected.values()):break
 verify_freeze();write(OUT/'execution_status.json',{'selected':30,'recorded':len(rows(target)),'attempts':sum(e['event']=='ATTEMPT' for e in rows(ledger)),'all_outputs_fresh':True,'B_calls':0,'SDK_retries':0,'counterbalanced_C1_C2_order':True,'recovered_same_experiment_no_retakes':True,'elapsed_seconds':ensure()})
if __name__=='__main__':main()
