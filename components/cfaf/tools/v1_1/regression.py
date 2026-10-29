"""Isolated historical compatibility; no unused dataset records are opened."""
from common import *
import os,sys,shutil

def main():
 ensure();state=snapshot_check();scratch=WORK/'historical-regression';scratch.mkdir(exist_ok=False);paths=subprocess.check_output(['git','ls-tree','-r','--name-only',state['v1_commit']],cwd=REPO,text=True).splitlines();blob=subprocess.check_output(['git','cat-file','--batch'],input=''.join(state['v1_commit']+':'+p+'\n' for p in paths).encode(),cwd=REPO);offset=0
 for path in paths:
  end=blob.index(b'\n',offset);size=int(blob[offset:end].split()[-1]);start=end+1;p=scratch/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(blob[start:start+size]);offset=start+size+1
 assert offset==len(blob)
 common=Path(subprocess.check_output(['git','rev-parse','--git-common-dir'],cwd=REPO,text=True).strip());common=common if common.is_absolute() else REPO/common;shutil.copytree(common,scratch/'.git');(scratch/'.git/HEAD').write_text(state['v1_commit']+'\n');subprocess.run(['git','-C',str(scratch),'config','core.autocrlf','false'],check=True);subprocess.run(['git','-C',str(scratch),'read-tree',state['v1_commit']],check=True)
 primary=Path(state['other_worktrees'][0]['path']);restored=[]
 for path in paths:
  if (primary/path).is_file():
   expected=(scratch/path).read_bytes();raw=(primary/path).read_bytes()
   if raw!=expected and raw.replace(b'\r\n',b'\n')==expected.replace(b'\r\n',b'\n'):(scratch/path).write_bytes(raw);restored.append(path)
 # Adapter regression fixtures are exactly the original ten exposed GaRAGe cases.
 for name in ['runtime_inputs.jsonl','gold_annotations.jsonl']:shutil.copy2(primary/'evaluation/cfaf_dataset3_garage_pilot_v1'/name,scratch/'evaluation/cfaf_dataset3_garage_pilot_v1'/name)
 targets=read(ROOT/'results/regression_audit.json')['advanced_targets'];env=os.environ.copy();env.pop('OPENAI_API_KEY',None);env['TEMP']=env['TMP']=str(WORK/'tmp');env['HYPOTHESIS_STORAGE_DIRECTORY']=str(WORK/'legacy-hypothesis');env['PYTHONPATH']=str(scratch)
 omit='not test_metadata_filter_and_authorized_pool and not test_seed_group_and_holdout_constraints and not test_filtered_records_cannot_be_selected'
 command='import time,pytest\nfrom evaluation.refusalbench_iterative_dev_v1 import deadline\nold=deadline.limits();anchor=time.monotonic();deadline.limits=lambda:{**old,"monotonic_start":anchor}\nraise SystemExit(pytest.main('+repr(targets+['-q','-k',omit,'--basetemp',str(WORK/'legacy-test-temp'),'--junitxml',str(OUT/'historical_tests.xml')])+'))'
 python=REPO.parents[1]/'work/component-cfaf-v1/legacy-venv/Scripts/python.exe';p=subprocess.run([str(python),'-c',command],cwd=scratch,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding='utf-8',timeout=180);(OUT/'historical_tests.log').write_text(p.stdout,encoding='utf-8');advanced_code=p.returncode;print(p.stdout[-1200:],flush=True)
 # The original freeze checks require exact committed LF representation, unlike archived working-byte checks.
 offset=0
 for path in paths:
  end=blob.index(b'\n',offset);size=int(blob[offset:end].split()[-1]);start=end+1;(scratch/path).write_bytes(blob[start:start+size]);offset=start+size+1
 original=[str(p.relative_to(scratch)) for p in (scratch/'evaluation/tests').glob('test_wolala*.py')]
 p=subprocess.run([str(python),'-m','pytest',*original,'-q','--basetemp',str(WORK/'original-test-temp'),'--junitxml',str(OUT/'original_tests.xml')],cwd=scratch,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding='utf-8',timeout=180);(OUT/'original_tests.log').write_text(p.stdout,encoding='utf-8');print(p.stdout[-1300:],flush=True)
 # Verify the complete v1 test suite in its immutable source snapshot, with unchanged shared dependencies.
 env['PYTHONPATH']=str(Path(state['snapshot'])/'src')+os.pathsep+str(REPO);env['HYPOTHESIS_STORAGE_DIRECTORY']=str(WORK/'baseline-hypothesis');p2=subprocess.run([sys.executable,'-m','pytest',str(Path(state['snapshot'])/'tests'),'-q','--basetemp',str(WORK/'v1-baseline-tests'),'--junitxml',str(OUT/'baseline_tests.xml')],cwd=WORK,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding='utf-8',timeout=120);(OUT/'baseline_tests.log').write_text(p2.stdout,encoding='utf-8');print(p2.stdout[-800:],flush=True)
 write(OUT/'regression_audit.json',{'advanced_returncode':advanced_code,'original_returncode':p.returncode,'v1_baseline_returncode':p2.returncode,'v1_commit':state['v1_commit'],'exact_committed_source_files':len(paths),'scratch_only_newline_representation_restorations':len(restored),'API_key_removed':True,'runtime_environments_upgraded':False,'archived_timer_rebased_only_in_test_process':True,'known_original_failure':'test_preheldout_attempt1_plan_artifacts_are_plan_only: committed HELDOUT_RUN_AUTHORIZATION.json is preserved','three_dataset_metadata_tests_not_run':{'reason':'These tests load the complete cached RefusalBench JSONL for metadata projection. This task forbids access to unused/protected records; they were explicitly deselected rather than opening that file. No test was altered.','names':['test_metadata_filter_and_authorized_pool','test_seed_group_and_holdout_constraints','test_filtered_records_cannot_be_selected']},'no_QASPER_or_holdout_or_unused_source_text_opened':True})
if __name__=='__main__':main()
