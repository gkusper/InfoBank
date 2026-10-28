"""Run historical suites in exact-blob disposable checkout, without API credentials."""
import os,shutil,subprocess,sys,time
from pathlib import Path
from .artifacts import *
from .deadline import ensure

def run():
 remaining=ensure('isolated regression suite',120);scratch=REPO.parents[1]/'work/target-claim-regression-exact';scratch.mkdir(exist_ok=False)
 paths=subprocess.check_output(['git','ls-files'],cwd=REPO,text=True).splitlines()
 query=''.join('HEAD:'+p+'\n' for p in paths).encode();blob=subprocess.check_output(['git','cat-file','--batch'],input=query,cwd=REPO);offset=0
 for path in paths:
  end=blob.index(b'\n',offset);header=blob[offset:end].split();size=int(header[-1]);start=end+1;target=scratch/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(blob[start:start+size]);offset=start+size+1
 assert offset==len(blob)
 shutil.copytree(REPO/'.git',scratch/'.git');shutil.copytree(ROOT,scratch/'evaluation/cfaf_target_claim_alignment_v1')
 env=os.environ.copy();env.pop('OPENAI_API_KEY',None);temp=REPO.parents[1]/'work/target-claim-regression-temp';temp.mkdir(exist_ok=True);env['TEMP']=env['TMP']=str(temp)
 historical=[str(p.relative_to(scratch)) for p in (scratch/'evaluation/tests').glob('test_wolala*.py')]
 advanced=['evaluation/cfaf_target_claim_alignment_v1/test_target_claim.py','evaluation/cfaf_requirement_alignment_v1/test_rda.py','evaluation/cfaf_request_evidence_verification_v1/test_verification.py','evaluation/refusalbench_iterative_dev_v1/versions/v02/test_version.py','evaluation/refusalbench_iterative_dev_v1/versions/v01/test_version.py','evaluation/refusalbench_iterative_dev_v1/test_framework.py','evaluation/refusalbench_iterative_dev_v1/test_budget_deadline.py','evaluation/infobank_semantic_integration_v2/test_integration.py','evaluation/infobank_semantic_regression_v1/test_governed.py','evaluation/refusalbench_noncontradiction_v1/test_pilot.py','evaluation/refusalbench_span_fix_v1/test_span_fix.py','evaluation/refusalbench_semantic_dev/test_semantic.py','evaluation/refusalbench_semantic_dev/test_experiment.py','evaluation/refusalbench_pilot/test_refusalbench.py']
 results=[]
 for name,targets in [('current_and_prior',advanced),('historical_cfaf',historical)]:
  ensure(name,90);command=[sys.executable,'-m','pytest',*targets,'-q','--basetemp',str(temp/name),'--junitxml='+str(ROOT/(name+'_tests.xml'))];before=time.monotonic();proc=subprocess.run(command,cwd=scratch,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=min(180,remaining-5));(ROOT/(name+'_tests.log')).write_text(proc.stdout,encoding='utf-8');results.append({'suite':name,'returncode':proc.returncode,'elapsed_seconds':time.monotonic()-before,'targets':targets,'xml':name+'_tests.xml'});print(name,proc.returncode,proc.stdout[-1700:],flush=True)
 write(ROOT/'regression_runs.json',{'exact_git_blobs':len(paths),'disposable_checkout':str(scratch),'api_key_removed':True,'runs':results})
if __name__=='__main__':run()
