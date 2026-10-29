"""Scope, privacy, checksum and local-commit finalizer; never makes API/remote calls."""
from .artifacts import *
from .audit import audit
from .runner import verify_frozen
import datetime,os,re,subprocess,xml.etree.ElementTree as ET

PREFIX='evaluation/cfaf_contract_driven_qasper_final_v1/'
BRANCH='experiment/cfaf-final-qasper-replacement-v1'
REQUIRED='REPORT.md QASPER_TEST_SOURCE_AUDIT.md QASPER_GOLD_MAPPING.md QASPER_ELIGIBILITY_COUNTS.json PREREGISTRATION.md SAMPLE_MANIFEST.json EXPOSURE_LEDGER.json QASPER_MODE_RESULTS.jsonl QASPER_CONFUSION_MATRICES.json PAIRED_COMPARISON.json ANNOTATION_TIER_ANALYSIS.json EVIDENCE_RETRIEVAL_AUDIT.json OPERATIONAL_FAILURES.json API_USAGE.json SECURITY_AUDIT.json REGRESSION_AUDIT.json REVISED_THREE_DATASET_SUMMARY.md RESULTS_FOR_PAPER_QASPER.tex PAPER_REPLACEMENT_NOTES.md'.split()

def git(*args):return subprocess.check_output(['git',*args],cwd=REPO,stderr=subprocess.PIPE).decode('utf-8').strip()
def command(*args):
 p=subprocess.run(['git',*args],cwd=REPO,capture_output=True,text=True,encoding='utf-8')
 if p.returncode:raise RuntimeError('Git command failed: '+str(args[:3])+' '+p.stderr[:1000])
 return p.stdout

def public_files():
 return sorted(p for p in ROOT.rglob('*') if p.is_file() and p.relative_to(ROOT).parts[0] not in {'local','datasets','__pycache__'} and p.name!='task_state.json')

def privacy(files):
 key=os.getenv('OPENAI_API_KEY','');assert len(key)>20,'Actual credential required for equality scan; never print it'
 source_units=set()
 for r in rows(ROOT/'local/selected_originals.jsonl'):
  paper=r['paper'];source_units.add(paper.get('abstract',''))
  for section in paper['full_text']:source_units.update(section['paragraphs'])
 for r in rows(ROOT/'local/review_packet.jsonl'):source_units.update(r['human_evidence']);source_units.update(v for v in r['references'] if isinstance(v,str) and len(v)>=100)
 units=set()
 for s in source_units:
  if len(s)>=160:
   units.update((s.encode('utf-8'),json.dumps(s,ensure_ascii=False)[1:-1].encode('utf-8'),json.dumps(s,ensure_ascii=True)[1:-1].encode('utf-8')))
 patterns=[re.compile(rb'sk-(?:proj-)?[A-Za-z0-9_-]{30,}'),re.compile(rb'Bearer [A-Za-z0-9_-]{30,}')]
 for p in files:
  b=p.read_bytes();rel=p.relative_to(ROOT).as_posix()
  assert key.encode() not in b,'Credential bytes in '+rel
  assert not any(pattern.search(b) for pattern in patterns),'Possible credential in '+rel
  assert not any(unit in b for unit in units),'Original long paper/reference text in '+rel
 return {'status':'PASS','actual_environment_API_key_equality_scan':True,'credential_patterns_checked':len(patterns),'long_source_string_representations_checked':len(units),'public_files_scanned':len(files),'full_papers_human_answers_and_raw_payloads_staged':False,'scope':'All new public files against selected-paper paragraphs/abstracts and long human references, including JSON escaping variants'}

def validate():
 ensure();audit();state=read(ROOT/'task_state.json')
 assert git('branch','--show-current')==BRANCH
 assert git('rev-parse','HEAD')==state['starting_commit']
 assert not git('diff','--name-only') and not git('diff','--cached','--name-only')
 for name in REQUIRED:assert (ROOT/name).is_file(),name
 safe=rows(ROOT/'QASPER_MODE_RESULTS.jsonl');assert len(safe)==80 and all(r['execution_status']=='COMPLETED' for r in safe)
 assert len({r['paper_id'] for r in safe})==80 and {r['annotation_tier'] for r in safe}=={'M'}
 assert len(rows(ROOT/'local/api_requests.jsonl'))==241
 assert read(ROOT/'API_USAGE.json')['new_QASPER_attempts']==241
 assert [sum(r['systems'][s]['mode_correct'] for r in safe) for s in 'ABC']==[63,63,54]
 assert sum(r['systems']['C']['operational_failure'] for r in safe)==8
 assert read(ROOT/'LATEX_COMPILE_AUDIT.json')['status']=='SUCCESS'
 helper=REPO.parents[1]/'work/cfaf-final-qasper-paper-check/results.tex';assert sha(helper)==sha(ROOT/'RESULTS_FOR_PAPER_QASPER.tex')
 source=read(ROOT/'MANUSCRIPT_SOURCE.json');assert sha(Path(source['path']))==source['sha256']
 for p in ROOT.rglob('*'):
  if p.is_file() and (p.relative_to(ROOT).parts[0] in {'local','datasets','__pycache__'} or p.name=='task_state.json'):
   x=subprocess.run(['git','check-ignore','-q','--',p.relative_to(REPO).as_posix()],cwd=REPO)
   assert x.returncode==0,'Private path not ignored'
 tests={}
 for p in ROOT.glob('*tests.xml'):
  suites=ET.parse(p).getroot().iter('testsuite');tests[p.name]=[{k:int(s.get(k,'0')) for k in ['tests','failures','errors','skipped']} for s in suites]
 assert tests['regression_tests.xml'][0]['tests']==713 and tests['regression_tests.xml'][0]['failures']==0
 assert tests['original_tests.xml'][0]['failures']==1
 completion={'status':'PRECOMMIT_VALIDATED','branch':BRANCH,'base_commit':state['starting_commit'],'new_QASPER_selected_completed':80,'new_attempts':241,'mode_correct':{'A':63,'B':63,'C':54},'C_operational_errors':8,'historical_datasets_rerun':False,'test_reports':tests,'known_original_failure':read(ROOT/'REGRESSION_AUDIT.json')['known_original_failure'],'primary_worktree_unchanged':True,'historical_worktree_files_unchanged':True,'original_manuscript_unchanged':True,'compiled_fragment':True,'no_push_or_merge':True,'elapsed_seconds_at_precommit':ensure(),'postcommit_receipt':'Adjacent output: cfaf_contract_driven_qasper_final_v1_completion.json'}
 write(ROOT/'COMPLETION_AUDIT.json',completion)
 files=public_files();privacy_result=privacy(files);security=read(ROOT/'SECURITY_AUDIT.json');security['scoped_precommit_privacy_scan']=privacy_result;security['prior_index_blob_identity_after_newline_stat_refresh']=True;write(ROOT/'SECURITY_AUDIT.json',security)
 files=public_files();names=sorted({p.relative_to(ROOT).as_posix() for p in files}|{'CHANGED_FILES.txt','checksums.sha256'})
 (ROOT/'CHANGED_FILES.txt').write_text('\n'.join(PREFIX+n for n in names)+'\n',encoding='utf-8')
 files=public_files();(ROOT/'checksums.sha256').write_text(''.join(sha(p)+'  '+p.relative_to(ROOT).as_posix()+'\n' for p in files if p.name!='checksums.sha256'),encoding='utf-8')
 files=public_files();privacy_result=privacy(files)
 expected={PREFIX+p.relative_to(ROOT).as_posix() for p in files}
 command('add','--',PREFIX)
 staged=set(git('diff','--cached','--name-only').splitlines());assert staged==expected,'Staged inventory differs'
 command('diff','--cached','--check')
 for p in files:
  b=subprocess.check_output(['git','show',':'+p.relative_to(REPO).as_posix()],cwd=REPO);assert hashlib.sha256(b).hexdigest()==sha(p),'Index bytes changed'
 assert not git('diff','--name-only'),'Unstaged content changed'
 print('PRECOMMIT PASS',len(files),'public files; 80 cases; 241 attempts; private data ignored; protected files/refs unchanged',flush=True)
 return state,expected

def finish():
 state,expected=validate();ensure()
 output=command('-c','user.name=gkusper','-c','user.email=gkusper@aries.ektf.hu','commit','-m','Replace Dataset3 with preregistered QASPER test comparison')
 commit=git('rev-parse','HEAD');assert git('rev-parse','HEAD^')==state['starting_commit'];assert set(git('diff-tree','--no-commit-id','--name-only','-r','HEAD').splitlines())==expected
 verify_frozen()
 primary=Path(state['primary_repo']);assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=primary,text=True).strip()==state['primary_HEAD']
 assert all(sha(primary/p)==h for p,h in state['primary_protected'].items());assert all(sha(REPO/p)==h for p,h in state['protected_files'].items())
 refs=dict(line.split(' ',1) for line in git('for-each-ref','--format=%(refname) %(objectname)').splitlines())
 for item in state['prior_refs']:
  name,h=item.split(' ',1);assert refs.get(name)==h,name
 for line in (ROOT/'checksums.sha256').read_text(encoding='utf-8').splitlines():
  h,p=line.split('  ',1);assert sha(ROOT/p)==h,p
 assert not git('status','--porcelain'),'Worktree not clean'
 source=read(ROOT/'MANUSCRIPT_SOURCE.json');assert sha(Path(source['path']))==source['sha256']
 now=datetime.datetime.now(datetime.timezone.utc);elapsed=ensure();receipt={'status':'COMPLETE','commit':commit,'parent_commit':state['starting_commit'],'branch':BRANCH,'worktree':str(REPO),'report':str(ROOT/'REPORT.md'),'private_complete_case_report':str(ROOT/'local/CASE_REPORT.md'),'completion_utc':now.isoformat(),'completion_Budapest':now.astimezone(datetime.timezone(datetime.timedelta(hours=1))).isoformat(),'start_utc':state['start_utc'],'elapsed_seconds':elapsed,'within_two_hour_limit':elapsed<7200,'new_QASPER_completed':80,'new_QASPER_API_attempts':241,'mode_accuracy':{'A':0.7875,'B':0.7875,'C':0.675},'C_operational_errors':8,'public_files_committed':len(expected),'checksums_verified':True,'new_worktree_clean':True,'primary_HEAD_and_files_unchanged':True,'all_prior_refs_unchanged':True,'manuscript_unchanged':True,'push':False,'merge':False,'manual_push_command':'git -C "'+str(REPO)+'" push -u origin '+BRANCH}
 target=REPO.parent/'cfaf_contract_driven_qasper_final_v1_completion.json';write(target,receipt);print(output.splitlines()[0]);print(json.dumps(receipt,ensure_ascii=False,indent=2))

if __name__=='__main__':finish()
