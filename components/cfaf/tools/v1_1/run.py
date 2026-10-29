"""One counterbalanced paired experiment; no old outputs are replayed as fresh."""
from common import *
import os,sys

def main():
 ensure();verify_freeze();assert not (OUT/'local/api_ledger.jsonl').exists(),'No repeated experiment';target=OUT/'local/paired_raw.jsonl';assert not target.exists();runs=[]
 for index in range(30):
  ensure(api=True);verify_freeze();selected={};order=['A',*(['C1','C2'] if index%2==0 else ['C2','C1'])]
  for system in order:
   ensure(api=True);assert len([e for e in rows(OUT/'local/api_ledger.jsonl') if e['event']=='ATTEMPT'])<100 if (OUT/'local/api_ledger.jsonl').exists() else True
   env=os.environ.copy();env['TEMP']=env['TMP']=str(WORK/'tmp');env['PYTHONIOENCODING']='utf-8';start=time.perf_counter();p=subprocess.run([sys.executable,str(Path(__file__).with_name('worker.py')),system,str(index)],cwd=REPO,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding='utf-8',errors='replace',timeout=60);file=OUT/f'local/{index:02d}_{system}.json'
   if file.exists():result=read(file);result['process_wall_ms']=(time.perf_counter()-start)*1000;selected[system]=result
   else:selected[system]={'index':index,'system':system,'execution_status':'WORKER_ERROR','usage':{'attempts':0},'private_error':p.stdout[-2000:]}
   print(p.stdout.strip()[-300:],flush=True)
  append(target,{'index':index,'dataset':rows(ROOT/'results/local/inputs.jsonl')[index]['dataset'],'order':order,'systems':selected})
  assert len({v.get('context_identity_sha256') for v in selected.values() if v.get('context_identity_sha256')})==1,'SYSTEM_CONTEXTS_DIFFER'
  if any(v.get('execution_status') in {'PROVIDER_HTTP_401','PROVIDER_HTTP_403','PROVIDER_HTTP_429'} for v in selected.values()):break
 verify_freeze();write(OUT/'execution_status.json',{'selected':30,'recorded':len(rows(target)),'attempts':sum(e['event']=='ATTEMPT' for e in rows(OUT/'local/api_ledger.jsonl')),'all_outputs_fresh':True,'B_calls':0,'SDK_retries':0,'counterbalanced_C1_C2_order':True,'elapsed_seconds':ensure()})
if __name__=='__main__':main()
