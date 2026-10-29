"""Historical regressions in disposable clone; no credential or production environment."""
from common import *
import os,sys,shutil

def main():
    ensure();state=read(STATE);source=Path(state['worktrees'][0]['path']);scratch=WORK/'legacy-regression-exact';assert not scratch.exists();scratch.mkdir()
    paths0=subprocess.check_output(['git','ls-tree','-r','--name-only',state['base']],cwd=REPO,text=True).splitlines()
    blob=subprocess.check_output(['git','cat-file','--batch'],input=''.join(state['base']+':'+p+'\n' for p in paths0).encode(),cwd=REPO);offset=0
    for path in paths0:
        end=blob.index(b'\n',offset);size=int(blob[offset:end].split()[-1]);start=end+1;dest=scratch/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(blob[start:start+size]);offset=start+size+1
    assert offset==len(blob)
    common=Path(subprocess.check_output(['git','rev-parse','--git-common-dir'],cwd=REPO,text=True).strip())
    if not common.is_absolute():common=REPO/common
    shutil.copytree(common,scratch/'.git');(scratch/'.git/HEAD').write_text(state['base']+'\n')
    subprocess.run(['git','-C',str(scratch),'config','core.autocrlf','false'],check=True)
    subprocess.run(['git','-C',str(scratch),'read-tree',state['base']],check=True)
    paths=subprocess.check_output(['git','ls-files','-z'],cwd=scratch).decode().split('\0');restored=[]
    for path in [p for p in paths if p]:
        expected=(scratch/path).read_bytes();old=(source/path).read_bytes()
        if old!=expected and old.replace(b'\r\n',b'\n')==expected.replace(b'\r\n',b'\n'):
            (scratch/path).write_bytes(old);restored.append(path)
    # Only the original, already-exposed ten-case GaRAGe fixture is needed by adapter tests.
    for name in ['runtime_inputs.jsonl','gold_annotations.jsonl']:
        shutil.copy2(source/'evaluation/cfaf_dataset3_garage_pilot_v1'/name,scratch/'evaluation/cfaf_dataset3_garage_pilot_v1'/name)
    targets=['evaluation/cfaf_contract_driven_2h_v1/test_study.py','evaluation/cfaf_sparse_source_repair_v1/test_reference_alias.py']+git_json('evaluation/cfaf_sparse_source_repair_v1/regression_audit.json')['advanced_targets']
    env=os.environ.copy();env.pop('OPENAI_API_KEY',None);env['PYTHONPATH']=str(scratch);env['TEMP']=env['TMP']=str(WORK/'tmp');runs=[]
    compatible='import time,pytest\nfrom evaluation.refusalbench_iterative_dev_v1 import deadline\nold=deadline.limits();anchor=time.monotonic();deadline.limits=lambda:{**old,"monotonic_start":anchor}\nraise SystemExit(pytest.main('+repr(targets+['-q','--basetemp',str(WORK/'legacy-test-temp'),'--junitxml',str(ROOT/'results/legacy_tests.xml')])+'))'
    original=[str(p.relative_to(scratch)) for p in (scratch/'evaluation/tests').glob('test_wolala*.py')]
    for name,cmd in [('advanced',[sys.executable,'-c',compatible]),('original',[sys.executable,'-m','pytest',*original,'-q','--basetemp',str(WORK/'original-test-temp'),'--junitxml',str(ROOT/'results/original_tests.xml')])]:
        start=time.perf_counter();p=subprocess.run(cmd,cwd=scratch,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',timeout=180);(ROOT/f'results/{name}_tests.log').write_text(p.stdout,encoding='utf-8');runs.append({'suite':name,'returncode':p.returncode,'seconds':time.perf_counter()-start});print(name,p.returncode,p.stdout[-1700:],flush=True)
    write(ROOT/'results/regression_audit.json',{'runs':runs,'base_commit':state['base'],'disposable_clone':str(scratch),'tracked_blob_count':len([p for p in paths if p]),'historical_working_byte_restorations_from_identical_normalized_committed_content':len(restored),'restoration_is_only_in_disposable_test_clone':True,'API_key_removed':True,'original_environments_worktrees_and_caches_modified':False,'archived_timer_rebased_only_inside_test_process':True,'known_preexisting_failure':'test_preheldout_attempt1_plan_artifacts_are_plan_only: committed HELDOUT_RUN_AUTHORIZATION.json exists; archived file preserved','no_QASPER_or_reserved_content_read':True,'advanced_targets':targets})
if __name__=='__main__':main()
