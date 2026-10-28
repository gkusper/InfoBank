"""Reproducible regression environment adjustments, without changing old sources."""
import os,shutil,subprocess,sys
from .artifacts import *
from .deadline import ensure

def run():
 ensure('final regression verification',90);scratch=REPO.parents[1]/'work/recv-regression-exact'
 if not (scratch/'.git').exists():raise RuntimeError('Run regression.py first to create exact Git-blob checkout')
 for p in ROOT.glob('*.py'):shutil.copy2(p,scratch/'evaluation/cfaf_request_evidence_verification_v1'/p.name)
 targets=read(ROOT/'regression_runs.json')['runs'][0]['targets']
 code='import time,pytest\nfrom evaluation.refusalbench_iterative_dev_v1 import deadline\nold=deadline.limits();anchor=time.monotonic();deadline.limits=lambda:{**old,"monotonic_start":anchor}\nraise SystemExit(pytest.main('+repr(targets+['-q','-k','not test_historical_files_unchanged and not test_previous_frozen_files_unchanged','--basetemp',str(REPO.parents[1]/'work/recv-final-compatible-temp'),'--junitxml='+str(ROOT/'final_regression_tests.xml')])+'))\n'
 env=os.environ.copy();env.pop('OPENAI_API_KEY',None);env['PYTHONPATH']=str(scratch);env['TEMP']=env['TMP']=str(REPO.parents[1]/'work')
 process=subprocess.run([sys.executable,'-c',code],cwd=scratch,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120);(ROOT/'final_regression_tests.log').write_text(process.stdout);print(process.stdout)
 env['PYTHONPATH']=str(REPO);hash_targets=['evaluation/infobank_semantic_regression_v1/test_governed.py::test_historical_files_unchanged','evaluation/refusalbench_span_fix_v1/test_span_fix.py::test_previous_frozen_files_unchanged'];checks=subprocess.run([sys.executable,'-m','pytest',*hash_targets,'-q','--junitxml='+str(ROOT/'current_worktree_hash_tests.xml')],cwd=REPO,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30);(ROOT/'current_worktree_hash_tests.log').write_text(checks.stdout);print(checks.stdout)
 write(ROOT/'regression_environment.json',{'isolated_suite_returncode':process.returncode,'working_tree_hash_suite_returncode':checks.returncode,'archived_timer_rebased_only_in_test_process':True,'historical_source_modified':False,'hash_test_reason':'Old snapshots record CRLF working bytes. Exact Git blobs use normalized LF for some files; byte-hash-only tests therefore run against the unchanged original working files.','api_key_removed':True,'all_other_historical_tests_run_in_disposable_exact_blob_checkout':True})
 if process.returncode or checks.returncode:raise RuntimeError('Regression failed')
if __name__=='__main__':run()
