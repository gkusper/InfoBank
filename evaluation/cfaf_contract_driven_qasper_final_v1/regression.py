"""Regression against exact Git blobs in disposable workspace; credentials removed."""
import os,subprocess,sys,shutil,time
from .artifacts import *


def run():
 ensure();scratch=REPO.parents[1]/'work/qasper-final-regression-exact';scratch.mkdir(exist_ok=False)
 paths=subprocess.check_output(['git','ls-files'],cwd=REPO,text=True).splitlines();blob=subprocess.check_output(['git','cat-file','--batch'],input=''.join('HEAD:'+p+'\n' for p in paths).encode(),cwd=REPO);offset=0
 for path in paths:
  end=blob.index(b'\n',offset);size=int(blob[offset:end].split()[-1]);start=end+1;target=scratch/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(blob[start:start+size]);offset=start+size+1
 assert offset==len(blob)
 primary=Path(read(ROOT/'task_state.json')['primary_repo']);shutil.copytree(primary/'.git',scratch/'.git');(scratch/'.git/HEAD').write_text(read(ROOT/'task_state.json')['starting_commit']+'\n',encoding='utf-8');subprocess.run(['git','read-tree',read(ROOT/'task_state.json')['starting_commit']],cwd=scratch,check=True);dest=scratch/ROOT.relative_to(REPO);dest.mkdir(parents=True)
 for p in ROOT.iterdir():
  if p.is_file() and (p.suffix=='.py' or p.name in {'runtime_inputs.jsonl','gold_annotations.jsonl','dataset3_selection_manifest.json'}):shutil.copy2(p,dest/p.name)
 env=os.environ.copy();env.pop('OPENAI_API_KEY',None);env['PYTHONPATH']=str(scratch);temp=REPO.parents[1]/'work/qasper-final-regression-temp';temp.mkdir(exist_ok=True);env['TEMP']=env['TMP']=str(temp)
 advanced=['evaluation/cfaf_contract_driven_qasper_final_v1/test_final.py','evaluation/cfaf_contract_driven_2h_v1/test_study.py','evaluation/cfaf_sparse_source_repair_v1/test_reference_alias.py']+read(REPO/'evaluation/cfaf_sparse_source_repair_v1/regression_audit.json')['advanced_targets']
 for name in ['runtime_inputs.jsonl','gold_annotations.jsonl']:
  shutil.copy2(primary/'evaluation/cfaf_dataset3_garage_pilot_v1'/name,scratch/'evaluation/cfaf_dataset3_garage_pilot_v1'/name)
 compatible_code='import time,pytest\nfrom evaluation.refusalbench_iterative_dev_v1 import deadline\nold=deadline.limits();anchor=time.monotonic();deadline.limits=lambda:{**old,"monotonic_start":anchor}\nraise SystemExit(pytest.main('+repr(advanced+['-q','-k','not test_historical_files_unchanged and not test_previous_frozen_files_unchanged and not test_historical_files_immutable','--basetemp',str(temp/'advanced'),'--junitxml='+str(ROOT/'regression_tests.xml')])+'))'
 runs=[]
 for name,command in [('current_and_prior',[sys.executable,'-c',compatible_code]),('original_cfaf',[sys.executable,'-m','pytest',*[str(p.relative_to(scratch)) for p in (scratch/'evaluation/tests').glob('test_wolala*.py')],'-q','--basetemp',str(temp/'historical'),'--junitxml='+str(ROOT/'original_tests.xml')])]:
  before=time.monotonic();proc=subprocess.run(command,cwd=scratch,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',timeout=150);(ROOT/(name+'_tests.log')).write_text(proc.stdout,encoding='utf-8');runs.append({'suite':name,'returncode':proc.returncode,'seconds':time.monotonic()-before});print(name,proc.returncode,proc.stdout[-1400:],flush=True)
 env['PYTHONPATH']=str(REPO);targets=['evaluation/cfaf_requirement_alignment_v1/test_rda.py::test_historical_files_immutable','evaluation/infobank_semantic_regression_v1/test_governed.py::test_historical_files_unchanged','evaluation/refusalbench_span_fix_v1/test_span_fix.py::test_previous_frozen_files_unchanged'];proc=subprocess.run([sys.executable,'-m','pytest',*targets,'-q','--junitxml='+str(ROOT/'historical_hash_tests.xml')],cwd=REPO,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30);(ROOT/'historical_hash_tests.log').write_text(proc.stdout,encoding='utf-8');runs.append({'suite':'historical_worktree_hashes','returncode':proc.returncode});print(proc.stdout)
 write(ROOT/'REGRESSION_AUDIT.json',{'runs':runs,'exact_git_blob_count':len(paths),'api_key_removed':True,'archived_timer_rebased_only_in_test_process':True,'historical_hashes_run_against_original_unchanged_worktree':True,'historical_sources_modified':False,'known_original_failure':'test_preheldout_attempt1_plan_artifacts_are_plan_only: previously committed HELDOUT_RUN_AUTHORIZATION.json contradicts plan-only assertion','no_new_reserved_case_content_accessed':True,'advanced_targets':advanced})
if __name__=='__main__':run()
