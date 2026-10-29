"""Scope-limited public artifact validation, checksums and local commit; never pushes."""
import os,json,subprocess,time,datetime,hashlib
from .artifacts import *
from .runner import verify_frozen

def git(*args):return subprocess.check_output(['git',*args],cwd=REPO)
def public_paths():return [p for p in git('ls-files','--cached','--others','--exclude-standard','--',ROOT.relative_to(REPO).as_posix()).decode().splitlines() if p]
def finalize():
 elapsed=ensure();state=read(ROOT/'task_state.json');base=state['starting_commit'];prefix=ROOT.relative_to(REPO).as_posix()+'/'
 assert git('rev-parse','HEAD').decode().strip()==base
 assert git('branch','--show-current').decode().strip()=='experiment/cfaf-qasper-pilot-v1'
 verify_frozen();assert all(sha(REPO/p)==h for p,h in state['protected_files'].items())
 assert git('rev-parse','experiment/cfaf-contract-driven-v1').decode().strip()==base
 assert git('rev-parse','wolala2026').decode().strip()=='5f377de38312fb39c088551f9c74f8b6d4bd5080'
 assert git('rev-parse','cfaf-wolala2026-freeze-2026-10-29^{}').decode().strip()=='5f377de38312fb39c088551f9c74f8b6d4bd5080'
 required=['REPORT.md','QASPER_SOURCE_AUDIT.md','QASPER_LABEL_MAPPING.md','DATASET3_SELECTION_MANIFEST.json','DATASET3_EXPOSURE_LEDGER.json','EXPERIMENT_MANIFEST.json','RUNTIME_INPUTS.jsonl','RESULTS.jsonl','MODE_CONFUSION.json','EVIDENCE_METRICS.json','API_USAGE.json','REGRESSION_AUDIT.json','SECURITY_AUDIT.json']
 assert all((ROOT/p).is_file() for p in required);assert (ROOT/'local/CASE_REPORT.md').is_file();assert len(rows(ROOT/'RESULTS.jsonl'))==10
 private=['local/CASE_REPORT.md','local/runtime_inputs.jsonl','local/selected_originals.jsonl','local/api_requests.jsonl','local/api_events.jsonl','datasets/qasper-dev-v0.3.json','datasets/qasper-train-dev-v0.3.tgz','task_state.json']
 for p in private:subprocess.run(['git','check-ignore','--quiet',str(ROOT.relative_to(REPO)/p)],cwd=REPO,check=True)
 paths=public_paths();assert all(p.startswith(prefix) and '/local/' not in p and '/datasets/' not in p for p in paths)
 key=(os.environ.get('OPENAI_API_KEY') or '').encode();assert key
 original=rows(ROOT/'local/selected_originals.jsonl');probes=[]
 for r in original:
  p=r['paper']
  probes.extend(text for sec in p['full_text'] for text in sec['paragraphs'] if len(text)>=160)
  for a in r['question']['answers']:
   aa=a['answer'];probes.extend(t for t in [aa['free_form_answer'],*aa['extractive_spans']] if len(t)>=100)
 def scan(paths):
  violations=[]
  for path in paths:
   blob=(REPO/path).read_bytes();assert key not in blob,'CREDENTIAL_BYTES_IN_PUBLIC_ARTIFACT'
   text=blob.decode('utf-8-sig')
   for probe in probes:
    if probe in text:violations.append(path);break
  assert not violations,sorted(set(violations))
 scan(paths)
 security=read(ROOT/'SECURITY_AUDIT.json');security.update(privacy_precommit_scan='PASS',credential_bytes_in_public_files=0,whole_original_paragraph_or_long_reference_answer_leaks=0,ignored_private_artifacts_verified=True,scoped_public_inventory_only=True,prior_git_branch_and_freeze_tag_unchanged=True,finalized_at_epoch=time.time());write(ROOT/'SECURITY_AUDIT.json',security)
 manifest=read(ROOT/'EXPERIMENT_MANIFEST.json');calls=rows(ROOT/'local/api_requests.jsonl');write(ROOT/'FINAL_AUDIT.json',{'starting_commit':base,'branch':'experiment/cfaf-qasper-pilot-v1','planned_cases':10,'completed_cases':10,'API_attempts':len(calls),'first_API_start_UTC':datetime.datetime.fromtimestamp(min(r['started_at_epoch'] for r in calls),datetime.timezone.utc).isoformat(),'last_API_start_UTC':datetime.datetime.fromtimestamp(max(r['started_at_epoch'] for r in calls),datetime.timezone.utc).isoformat(),'selection_before_API':read(ROOT/'DATASET3_SELECTION_MANIFEST.json')['selected_at_epoch']<min(r['started_at_epoch'] for r in calls),'code_freeze_before_API':manifest['frozen_at_epoch']<min(r['started_at_epoch'] for r in calls),'elapsed_at_precommit_seconds':ensure(),'hard_limit_seconds':3600,'new_API_stop_seconds':3000,'earlier_files_protected':len(state['protected_files']),'prior_files_changed':0,'no_push_or_merge':True,'postcommit_receipt':'outputs/cfaf_qasper_pilot_v1_completion.json outside repository; contains final commit, total elapsed and clean-state verification'})
 paths=set(public_paths())|{prefix+'CHANGED_FILES.txt',prefix+'checksums.sha256'}
 (ROOT/'CHANGED_FILES.txt').write_text('\n'.join(sorted(paths))+'\n',encoding='utf-8')
 (ROOT/'checksums.sha256').write_text(''.join(sha(REPO/p)+'  '+p[len(prefix):]+'\n' for p in sorted(paths) if p!=prefix+'checksums.sha256'),encoding='utf-8')
 paths=public_paths();scan(paths);staged=git('diff','--cached','--name-only').decode().splitlines();assert all(p.startswith(prefix) for p in staged)
 subprocess.run(['git','add','--',prefix],cwd=REPO,check=True)
 staged=git('diff','--cached','--name-only').decode().splitlines();assert set(staged)==set(paths)
 subprocess.run(['git','diff','--cached','--check'],cwd=REPO,check=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 for p in staged:assert git('show',':'+p)==(REPO/p).read_bytes(),'INDEX_WORKTREE_MISMATCH:'+p
 ensure();subprocess.run(['git','-c','user.name=gkusper','-c','user.email=gkusper@aries.ektf.hu','commit','-m','Add reproducible QASPER ten-case CFAF candidate pilot'],cwd=REPO,check=True)
 commit=git('rev-parse','HEAD').decode().strip();assert git('rev-parse','HEAD^').decode().strip()==base;assert not git('status','--porcelain').strip()
 assert all(sha(REPO/p)==h for p,h in state['protected_files'].items());verify_frozen()
 for line in (ROOT/'checksums.sha256').read_text(encoding='utf-8').splitlines():
  h,p=line.split('  ',1);assert sha(ROOT/p)==h,p
 final_elapsed=ensure();receipt={'commit':commit,'branch':'experiment/cfaf-qasper-pilot-v1','parent_commit':base,'completed_at_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'completed_at_Budapest':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=1))).isoformat(),'start_UTC':state['start_utc'],'elapsed_seconds':final_elapsed,'hard_limit_seconds':3600,'within_time_limit':final_elapsed<3600,'public_files_committed':len(paths),'earlier_files_unchanged':len(state['protected_files']),'checksums_verified':len(paths)-1,'worktree_clean':True,'frozen_inference_unchanged':True,'cases_completed':10,'API_attempts':len(calls),'mode_accuracy':{k:v['accuracy'] for k,v in read(ROOT/'MODE_CONFUSION.json').items()},'report':str(ROOT/'REPORT.md'),'detailed_case_report_private':str(ROOT/'local/CASE_REPORT.md'),'pushed':False,'merged':False,'manual_push_command':f'git -C "{REPO}" push -u origin experiment/cfaf-qasper-pilot-v1'}
 write(REPO.parent/'cfaf_qasper_pilot_v1_completion.json',receipt);print(json.dumps(receipt,indent=2))
if __name__=='__main__':finalize()
