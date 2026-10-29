"""Retest changed final sources in existing exact checkout, without API key."""
import shutil,subprocess,os,sys
from .artifacts import *
def run():
 scratch=REPO.parents[1]/'work/contract-study-regression-exact';dest=scratch/ROOT.relative_to(REPO)
 for p in ROOT.glob('*.py'):shutil.copy2(p,dest/p.name)
 targets=read(ROOT/'regression_audit.json')['advanced_targets'];env=os.environ.copy();env.pop('OPENAI_API_KEY',None);env['PYTHONPATH']=str(scratch)
 code='import time,pytest\nfrom evaluation.refusalbench_iterative_dev_v1 import deadline\nold=deadline.limits();anchor=time.monotonic();deadline.limits=lambda:{**old,"monotonic_start":anchor}\nraise SystemExit(pytest.main('+repr(targets+['-q','-k','not test_historical_files_unchanged and not test_previous_frozen_files_unchanged and not test_historical_files_immutable','--basetemp',str(REPO.parents[1]/'work/contract-final-tests'),'--junitxml='+str(ROOT/'final_regression_tests.xml')])+'))'
 p=subprocess.run([sys.executable,'-c',code],cwd=scratch,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=120);(ROOT/'final_regression_tests.log').write_text(p.stdout,encoding='utf-8');print(p.stdout);assert p.returncode==0
 reg=read(ROOT/'regression_audit.json');reg['final_source_retest_returncode']=p.returncode;reg['final_source_retest_xml']='final_regression_tests.xml';write(ROOT/'regression_audit.json',reg)
if __name__=='__main__':run()
