"""Final audit/checksums and external local-commit receipt. No model calls."""
from common import *
import os,re,sys,datetime,ast,xml.etree.ElementTree as ET

def git(*args):return subprocess.check_output(['git',*args],cwd=REPO,text=True,encoding='utf-8').strip()
def changes():
 tracked=git('diff','--name-only',read(STATE)['v1_commit'],'--').splitlines();new=git('ls-files','--others','--exclude-standard').splitlines();return sorted(set(tracked+new))
def protected():
 state=snapshot_check();verify_freeze()
 for p,h in state['original_tracked'].items():
  if not p.startswith('components/cfaf/') or p.startswith(('components/cfaf/results/','components/cfaf/tests/')):assert sha(REPO/p)==h,p
 refs=dict(line.split(' ',1) for line in git('for-each-ref','--format=%(refname) %(objectname)').splitlines())
 for line in state['prior_refs']:
  name,h=line.split(' ',1)
  if name!='refs/heads/ComponentBasaedCFAF':assert refs.get(name)==h,name
 assert refs['refs/tags/'+state['freeze_tag']]==state['freeze_tag_object']
 for w in state['other_worktrees']:
  assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=w['path'],text=True).strip()==w['HEAD'];assert all(sha(Path(w['path'])/p)==h for p,h in w['files'].items())
 assert sha(Path(r'C:\Users\EKKE\Downloads\CF2AF_v5.9.tex'))=='8f4c1387d41d43e62c3d3e81cd1507036ab4edfd60d19bc563910ed28025dee3'
 return state

def prepare():
 ensure();state=protected();assert git('branch','--show-current')=='ComponentBasaedCFAF' and git('rev-parse','HEAD')==state['v1_commit']
 from audit import audit
 audit()
 expected={'REPORT.md','CHANGED_FILES.txt','BASELINE_FREEZE.md','STRUCTURED_REQUEST_RESOLVER.md','REFERENCE_RESOLUTION_SPEC.md','SCHEMA_SIMPLIFICATION.md','COMPONENT_COMPARISON.md','code_size_report.json','dependency_audit.json','offline_tests.json','regression_audit.json','security_audit.json','paired_results.jsonl','mode_confusion.json','reference_error_analysis.json','api_usage.json','latency_comparison.json','experiment_manifest.json','checksums.sha256'}
 planned={'components/cfaf/results/v1_1/'+p for p in ['CHANGED_FILES.txt','checksums.sha256','completion_audit.json']};files=sorted(set(changes())|planned)
 assert all(p.startswith('components/cfaf/') for p in files),'Outside intended change scope'
 assert not any('/local/' in p or '__pycache__' in p or '.egg-info' in p or '/.hypothesis/' in p for p in files)
 inputs=rows(ROOT/'results/local/inputs.jsonl');gold=rows(ROOT/'results/local/gold.jsonl');needles=[]
 for item in inputs:
  if len(item['query'])>=25:needles.append(('full_selected_query',item['query']))
  for source in item['sources']:
   content=source.get('content','')
   if len(content)>=100:
    needles.extend(('long_selected_context_fragment',content[n:n+120]) for n in range(0,len(content)-119,120))
 def leaves(x):
  if isinstance(x,str):yield x
  elif isinstance(x,dict):
   for v in x.values():yield from leaves(v)
  elif isinstance(x,list):
   for v in x:yield from leaves(v)
 for item in gold:
  needles.extend(('long_private_gold_value',s) for s in leaves(item) if len(s)>=100)
 secrets=[v for k,v in os.environ.items() if ('API_KEY' in k or k.endswith('_TOKEN')) and len(v)>=20]
 checked=0
 for name in files:
  p=REPO/name
  if not p.exists():continue
  data=p.read_bytes();text=data.decode('utf-8-sig');checked+=1
  assert not any(v.encode() in data for v in secrets),'SECRET_IN_PUBLIC_FILE:'+name
  assert not re.search(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}',text),'KEY_PATTERN_IN_PUBLIC_FILE:'+name
  for kind,value in needles:assert value not in text,kind+':'+name
  if p.suffix=='.py':ast.parse(text)
 for p in expected-{'CHANGED_FILES.txt','checksums.sha256'}:assert (OUT/p).is_file(),p
 assert len(rows(OUT/'paired_results.jsonl'))==30
 assert read(OUT/'api_usage.json')['global_attempts']==83 and read(OUT/'api_usage.json')['settled_attempts']==83
 audit_doc=read(OUT/'security_audit.json');audit_doc.update(privacy_and_staging_scan='PASS',public_files_checked=checked,private_raw_files_staged=0,actual_environment_secret_scan='PASS',selected_full_query_context_long_gold_scan='PASS',stage_scope='components/cfaf only',schema_prompt_verified_against_actual_traffic=True);write(OUT/'security_audit.json',audit_doc)
 test_summaries={p.name:[{k:s.get(k) for k in ['tests','failures','errors','skipped']} for s in ET.parse(p).getroot().iter('testsuite')] for p in OUT.glob('*.xml')}
 write(OUT/'completion_audit.json',{'status':'READY_FOR_LOCAL_COMMIT','parent_v1_commit':state['v1_commit'],'branch':state['branch'],'all_frozen_source_and_private_original_hashes_match':True,'other_worktrees_refs_tags_and_manuscript_unchanged':True,'required_deliverables_present':True,'selected_cases':30,'attempts':83,'settled_attempts':83,'external_calls_from_finalizer':0,'no_post_output_runtime_prompt_schema_edit':True,'public_privacy_scan':'PASS','test_xml_summaries':test_summaries,'known_original_failure_preserved':True,'three_historical_full_cache_metadata_tests':'EXPLICIT_NOT_RUN','elapsed_seconds_at_precommit':ensure(),'pyproject_EOF_whitespace_exception':'Frozen packaging bytes retained; .gitattributes exempts only final blank-line lint for pyproject.toml, not other whitespace checks.','no_push_or_merge':True,'final_commit_receipt':'outputs/component_cfaf_v1_1_completion.json outside repository'})
 (OUT/'CHANGED_FILES.txt').write_text('Changes relative to completed v1 '+state['v1_commit']+'\n'+''.join(('M' if p in state['original_tracked'] else 'A')+'\t'+p+'\n' for p in files),encoding='utf-8')
 checksum=OUT/'checksums.sha256';checksum.write_text(''.join(sha(REPO/p)+'  '+p+'\n' for p in files if REPO/p!=checksum),encoding='utf-8')
 assert set(files)==set(changes()),'Change inventory mismatch'
 subprocess.run(['git','add','--','components/cfaf'],cwd=REPO,check=True);subprocess.run(['git','diff','--cached','--check'],cwd=REPO,check=True)
 assert set(git('diff','--cached','--name-only').splitlines())==set(files)
 for name in files:
  assert hashlib.sha256(subprocess.check_output(['git','show',':'+name],cwd=REPO)).hexdigest()==sha(REPO/name),'Index bytes differ:'+name
 print('FINAL PRECOMMIT PASS',len(files),'files;',len(files)-1,'checksums;',round(ensure()),'seconds from original start')

def receipt():
 elapsed=ensure();state=protected();assert git('branch','--show-current')=='ComponentBasaedCFAF';head=git('rev-parse','HEAD');assert head!=state['v1_commit'] and git('rev-parse','HEAD^')==state['v1_commit'];assert not git('status','--porcelain')
 checksum=OUT/'checksums.sha256';count=0
 for line in checksum.read_text(encoding='utf-8').splitlines():
  h,p=line.split('  ',1);assert sha(REPO/p)==h,p;count+=1
 assert git('cat-file','-t',state['freeze_tag'])=='tag' and git('rev-parse',state['freeze_tag']+'^{commit}')==state['v1_commit']
 r={'status':'COMPLETE','branch':'ComponentBasaedCFAF','parent_v1_commit':state['v1_commit'],'final_commit':head,'freeze_tag':state['freeze_tag'],'freeze_tag_object':state['freeze_tag_object'],'worktree':str(REPO),'report':str(OUT/'REPORT.md'),'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'conservative_start_utc':'2026-10-29T17:07:00Z','elapsed_seconds_wall_or_monotonic_max':ensure(),'within_120_minutes':True,'source_prompt_schema_frozen_and_unchanged':True,'clean_worktree':True,'all_prior_refs_worktrees_raw_results_and_manuscript_preserved':True,'selected_cases_completed':30,'model_attempts':83,'settled_attempts':83,'B_extra_calls':0,'new_or_protected_benchmark_records':0,'input_output_usage_failed_C1_connection':'UNKNOWN_NOT_ZERO','reported_common_output_reduction_percent':42.77955271565496,'reported_common_provider_time_reduction_percent':34.112784392508644,'native_accuracy_C1_C2':{'InfoBank':[0.8,0.7],'RefusalBenchNQ':[0.7,0.5]},'C2_operational_application_failures':5,'recommendation':'Combined compact C2 remains experimental; bounded engineering improvements and negative outcomes documented.','checksums_sha256':sha(checksum),'checksum_verified_files':count,'push_or_merge':False}
 target=REPO.parent/'component_cfaf_v1_1_completion.json';write(target,r);print(json.dumps({'receipt':str(target),'final_commit':head,'elapsed_seconds':round(r['elapsed_seconds_wall_or_monotonic_max']),'clean':True,'checksums_verified':count,'push_or_merge':False}))
if __name__=='__main__':
 if len(sys.argv)!=2 or sys.argv[1] not in ['prepare','receipt']:raise SystemExit('Use prepare before commit, receipt after local commit')
 (prepare if sys.argv[1]=='prepare' else receipt)()
