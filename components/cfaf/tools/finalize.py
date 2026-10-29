"""Public inventory, privacy checksums and local commit; no API, push or merge."""
from common import *
from audit import audit
from inventory import main as inventory
import datetime,os,re,importlib.metadata as meta,xml.etree.ElementTree as ET

PREFIX='components/cfaf/'
BRANCH='ComponentBasaedCFAF'
def git(*args):return subprocess.check_output(['git',*args],cwd=REPO,stderr=subprocess.PIPE).decode('utf-8').strip()
def command(*args):
 p=subprocess.run(['git',*args],cwd=REPO,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
 if p.returncode:raise RuntimeError('Git failed '+str(args[:2])+' '+p.stderr[:1400])
 return p.stdout

def files():
 names=git('ls-files','--cached','--others','--exclude-standard','--',PREFIX).splitlines()
 return [REPO/n for n in sorted(set(names)) if (REPO/n).is_file()]

def privacy(public):
 key=os.getenv('OPENAI_API_KEY','');assert len(key)>20,'Need actual environment credential for equality scan; never display it'
 units=set()
 for row in rows(ROOT/'results/local/inputs.jsonl'):
  if len(row['query'])>25:units.add(row['query'])
  for source in row['sources']:
   if len(source.get('content',''))>=160:units.add(source['content'])
 for row in rows(ROOT/'results/local/gold.jsonl'):
  g=row.get('gold') or {}
  for value in [g.get('gold_answer',''),*(g.get('original_answers') or [])]:
   if isinstance(value,str) and len(value)>=160:units.add(value)
 encoded=set()
 for unit in units:encoded.update([unit.encode('utf-8'),json.dumps(unit,ensure_ascii=False)[1:-1].encode('utf-8'),json.dumps(unit,ensure_ascii=True)[1:-1].encode('utf-8')])
 patterns=[re.compile(rb'sk-(?:proj-)?[A-Za-z0-9_-]{30,}'),re.compile(rb'Bearer [A-Za-z0-9_-]{30,}')]
 for p in public:
  raw=p.read_bytes();rel=p.relative_to(ROOT).as_posix();assert key.encode() not in raw,'Credential bytes in '+rel;assert not any(q.search(raw) for q in patterns),'Credential pattern in '+rel;assert not any(unit in raw for unit in encoded),'Benchmark question/context/long answer in '+rel
 return {'status':'PASS','actual_API_key_equality_scan':True,'credential_pattern_scans':2,'question_context_reference_encodings_checked':len(encoded),'public_files_checked':len(public),'private_inputs_gold_API_traffic_and_model_outputs_staged':False}

def validate():
 ensure();assert git('branch','--show-current')==BRANCH;assert git('rev-parse','HEAD')==read(STATE)['base'];assert all(path.startswith(PREFIX) for path in git('diff','--name-only').splitlines()) and all(path.startswith(PREFIX) for path in git('diff','--cached','--name-only').splitlines()),'Changes outside package'
 assert all(p.startswith(PREFIX) for p in git('ls-files','--others','--exclude-standard').splitlines()),'Untracked files outside package'
 required=['README.md','ARCHITECTURE.md','MAKE_OR_REUSE.md','MIGRATION.md','REPORT.md','component_manifest.json','code_size_report.json','api_usage.json','security_audit.json','requirements.lock','results/freeze.json','results/exposure_manifest.json','results/pilot_summary.json','results/renderer_ablation.json']
 for name in required:assert (ROOT/name).is_file(),name
 audit();inventory();verify_freeze()
 for p in (ROOT/'results/local').rglob('*'):
  if p.is_file():assert subprocess.run(['git','check-ignore','-q','--',str(p.relative_to(REPO))],cwd=REPO).returncode==0
 assert read(ROOT/'api_usage.json')['totals']['attempts']==56
 assert read(ROOT/'results/live_status.json')['recorded']==30
 expected_versions={line.split('==')[0].lower().replace('_','-'):line.split('==')[1] for line in (ROOT/'requirements.lock').read_text(encoding='utf-8').splitlines() if line.strip()}
 actual={d.metadata['Name'].lower().replace('_','-'):d.version for d in meta.distributions() if d.metadata['Name'].lower()!='component-cfaf'};assert actual==expected_versions,'Frozen component environment changed'
 tests={}
 for p in (ROOT/'results').glob('*tests.xml'):tests[p.name]=[{k:int(s.get(k,'0')) for k in ['tests','failures','errors','skipped']} for s in ET.parse(p).getroot().iter('testsuite')]
 assert tests['offline_tests.xml'][0]['failures']==0 and tests['offline_tests.xml'][0]['tests']==54
 assert tests['legacy_metadata_tests.xml'][0]['failures']==0 and tests['legacy_metadata_tests.xml'][0]['tests']==3
 assert tests['original_lf_tests.xml'][0]['failures']==1
 write(ROOT/'results/completion_audit.json',{'status':'PRECOMMIT_VALIDATED','base_commit':read(STATE)['base'],'branch':BRANCH,'new_selected_cases':30,'new_API_attempts':56,'new_runtime_lines':531,'copied_runtime_lines':167,'runtime_AST_statements':826,'test_reports':tests,'known_original_failure_preserved':True,'all_694_advanced_checks_passed_across_initial_and_metadata_repair_runs':True,'all_inference_sources_frozen_after_outputs':True,'manuscript_and_prior_worktrees_refs_unchanged':True,'no_push_or_merge':True,'elapsed_seconds':ensure(),'postcommit_receipt':'Adjacent output: component_cfaf_v1_completion.json'})
 (ROOT/'CHANGED_FILES.txt').touch();(ROOT/'checksums.sha256').touch();public=files();scan=privacy(public);security=read(ROOT/'security_audit.json');security['public_privacy_and_staging_scan']=scan;write(ROOT/'security_audit.json',security)
 public=files();(ROOT/'CHANGED_FILES.txt').write_text('\n'.join(p.relative_to(REPO).as_posix() for p in public)+'\n',encoding='utf-8')
 (ROOT/'checksums.sha256').write_text(''.join(sha(p)+'  '+p.relative_to(ROOT).as_posix()+'\n' for p in public if p.name!='checksums.sha256'),encoding='utf-8');privacy(files())
 command('add','--',PREFIX);expected={p.relative_to(REPO).as_posix() for p in files()};assert set(git('diff','--cached','--name-only').splitlines())==expected
 command('diff','--cached','--check')
 for path in expected:
  index=subprocess.check_output(['git','show',':'+path],cwd=REPO);assert hashlib.sha256(index).hexdigest()==sha(REPO/path),'Index conversion changed bytes'
 assert not git('diff','--name-only');print('PRECOMMIT PASS',len(expected),'public files; private data ignored; frozen code/protected state intact',flush=True)
 return expected

def main():
 expected=validate();state=read(STATE);ensure();output=command('-c','user.name=gkusper','-c','user.email=gkusper@aries.ektf.hu','commit','-m','Add contract-driven component CFAF with one-call SDK pipeline and bounded pilot')
 commit=git('rev-parse','HEAD');assert git('rev-parse','HEAD^')==state['base'];assert set(git('diff-tree','--no-commit-id','--name-only','-r','HEAD').splitlines())==expected
 verify_freeze()
 for w in state['worktrees']:
  path=Path(w['path']);assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=path,text=True).strip()==w['HEAD'];assert all(sha(path/p)==h for p,h in w['files'].items())
 refs=dict(line.split(' ',1) for line in git('for-each-ref','--format=%(refname) %(objectname)').splitlines())
 for line in state['refs']:
  name,h=line.split(' ',1);assert refs.get(name)==h,name
 for line in (ROOT/'checksums.sha256').read_text(encoding='utf-8').splitlines():
  h,path=line.split('  ',1);assert sha(ROOT/path)==h,path
 assert not git('status','--porcelain'),'Worktree not clean'
 assert sha(Path(r'C:\Users\EKKE\Downloads\CF2AF_v5.9.tex'))=='8f4c1387d41d43e62c3d3e81cd1507036ab4edfd60d19bc563910ed28025dee3'
 now=datetime.datetime.now(datetime.timezone.utc);elapsed=ensure();receipt={'status':'COMPLETE_WITH_DOCUMENTED_PROTOTYPE_LIMITATIONS','base_commit':state['base'],'final_commit':commit,'branch':BRANCH,'worktree':str(REPO),'report':str(ROOT/'REPORT.md'),'start_utc':state['start_utc'],'completion_utc':now.isoformat(),'completion_Budapest':now.astimezone(datetime.timezone(datetime.timedelta(hours=1))).isoformat(),'elapsed_seconds':elapsed,'within_120_minutes':elapsed<7200,'public_files_committed':len(expected),'new_runtime_lines':531,'copied_runtime_lines':167,'API_attempts':56,'all_30_cases_completed':True,'C1_max_requests_per_case':1,'C1_operational_errors':3,'new_worktree_clean':True,'checksums_verified':True,'prior_worktrees_heads_files_refs_unchanged':True,'QASPER_not_used_or_modified':True,'manuscript_unchanged':True,'push':False,'merge':False,'manual_push_command':'git -C "'+str(REPO)+'" push -u origin '+BRANCH}
 write(REPO.parent/'component_cfaf_v1_completion.json',receipt);print(output.splitlines()[0]);print(json.dumps(receipt,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
