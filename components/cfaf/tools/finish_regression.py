from common import *
import os,sys

def main():
 ensure();scratch=WORK/'legacy-regression-exact';python=WORK/'legacy-venv/Scripts/python.exe';env=os.environ.copy();env.pop('OPENAI_API_KEY',None);env['PYTHONPATH']=str(scratch);env['TEMP']=env['TMP']=str(WORK/'tmp');audit=read(ROOT/'results/regression_audit.json')
 targets=['evaluation/refusalbench_iterative_dev_v1/test_framework.py::test_metadata_filter_and_authorized_pool','evaluation/refusalbench_noncontradiction_v1/test_pilot.py::test_seed_group_and_holdout_constraints','evaluation/refusalbench_noncontradiction_v1/test_pilot.py::test_filtered_records_cannot_be_selected']
 p=subprocess.run([str(python),'-m','pytest',*targets,'-q','--basetemp',str(WORK/'legacy-metadata-temp'),'--junitxml',str(ROOT/'results/legacy_metadata_tests.xml')],cwd=scratch,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding='utf-8',timeout=180);(ROOT/'results/legacy_metadata_tests.log').write_text(p.stdout,encoding='utf-8');audit['metadata_dependency_repair']={'returncode':p.returncode,'pytest':'9.0.2','pyarrow':'26.0.0','separate_venv':str(python),'component_runtime_environment_changed':False};print(p.stdout,flush=True)
 paths=subprocess.check_output(['git','ls-tree','-r','--name-only',read(STATE)['base']],cwd=REPO,text=True).splitlines();blob=subprocess.check_output(['git','cat-file','--batch'],input=''.join(read(STATE)['base']+':'+path+'\n' for path in paths).encode(),cwd=REPO);offset=0
 for path in paths:
  end=blob.index(b'\n',offset);size=int(blob[offset:end].split()[-1]);start=end+1;(scratch/path).write_bytes(blob[start:start+size]);offset=start+size+1
 assert offset==len(blob)
 original=[str(p.relative_to(scratch)) for p in (scratch/'evaluation/tests').glob('test_wolala*.py')]
 p=subprocess.run([str(python),'-m','pytest',*original,'-q','--basetemp',str(WORK/'original-lf-test-temp'),'--junitxml',str(ROOT/'results/original_lf_tests.xml')],cwd=scratch,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding='utf-8',timeout=180);(ROOT/'results/original_lf_tests.log').write_text(p.stdout,encoding='utf-8');audit['original_exact_blob_retry']={'returncode':p.returncode,'reason':'Original protocol checksum tests require exact Git LF bytes; primary checkout CRLF formatting is irrelevant to these assertions. Reset only disposable copied working-file bytes, preserving all repository originals.'};audit['final_advanced_outcome']='691 passed initially; three missing-pyarrow metadata tests rerun separately';write(ROOT/'results/regression_audit.json',audit);print(p.stdout[-1700:],flush=True)
if __name__=='__main__':main()
