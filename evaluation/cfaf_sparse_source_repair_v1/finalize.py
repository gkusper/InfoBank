"""Safe-only local commit after frozen-source, privacy, index and history checks."""
import os,subprocess,json,datetime,hashlib
from .artifacts import *
from .deadline import ensure,elapsed
from .runner import verify_frozen
from .cached import PREVIOUS
PREFIX=ROOT.relative_to(REPO).as_posix()
def git(*args):return subprocess.check_output(['git',*args],cwd=REPO,text=True).strip()
def main():
 ensure('safe commit and receipt',60);verify_frozen();state=read(ROOT/'task_state.json');assert all(sha(REPO/p)==h for p,h in state['protected_files'].items());assert git('branch','--show-current')=='experiment/cfaf-sparse-source-repair-v1';assert git('rev-parse','HEAD')==state['baseline_commit'];assert git('rev-parse','experiment/cfaf-garage-pilot-v1')==state['baseline_commit'];assert git('rev-parse','wolala2026')=='5f377de38312fb39c088551f9c74f8b6d4bd5080'
 required=['REPORT.md','README.md','SPARSE_SOURCE_CONTRACT_SPEC.md','OPERATIONAL_FAILURE_SEMANTICS.md','PUBLIC_GROUNDING_TRACE_SPEC.md','source_inventory.py','sparse_source_assessment.py','reference_validation.py','operational_failure_codes.py','public_grounding_trace.py','cached_ablation_results.json','live_paired_results.jsonl','mode_transition_matrix.csv','source_coverage_diagnostics.jsonl','citation_diagnostics.jsonl','reason_audit.jsonl','api_usage.json','regression_audit.json','security_audit.json','experiment_manifest.json']
 for name in required:assert (ROOT/name).is_file(),name
 ignored=['runtime_inputs.jsonl','live_paired_results.jsonl','api_requests.jsonl','api_events.jsonl','cached_ablation_raw.jsonl','reference_alias_ablation_raw.jsonl','local/REPORT_FULL.md','local/per_case_diagnostics.jsonl']
 for p in ignored:assert subprocess.run(['git','check-ignore','-q',PREFIX+'/'+p],cwd=REPO).returncode==0,p
 security=read(ROOT/'security_audit.json');security.update(raw_artifacts_ignored=True,actual_credential_value_scan='PASS',exact_original_questions_full_passages_reference_answers_excluded_from_commit=True,precommit_elapsed_seconds=elapsed(),commit_scope=PREFIX+' only');write(ROOT/'security_audit.json',security)
 inventory=sorted(set(git('ls-files','--cached','--others','--exclude-standard','--',PREFIX).splitlines())|{PREFIX+'/CHANGED_FILES.txt',PREFIX+'/checksums.sha256'});(ROOT/'CHANGED_FILES.txt').write_text('\n'.join(inventory)+'\n',encoding='utf-8')
 raw=rows(PREVIOUS/'selected_records.jsonl');credential=os.environ.get('OPENAI_API_KEY','').encode();violations=[]
 for path in inventory:
  if path.endswith('/checksums.sha256'):continue
  data=(REPO/path).read_bytes();assert not credential or credential not in data,'Credential in safe artifact';text=data.decode('utf-8-sig')
  for record in raw:
   if record['question'] in text:violations.append((path,'original_question'))
   if record['answer_generate'] and record['answer_generate'] in text:violations.append((path,'original_reference_answer'))
   for passage in record['grounding']:
    value=next(v for k,v in passage.items() if k.startswith('cite_'))
    if value and value in text:violations.append((path,'full_original_passage'))
 assert not violations,violations
 (ROOT/'checksums.sha256').write_text('\n'.join(sha(REPO/p)+'  '+p for p in inventory if not p.endswith('/checksums.sha256'))+'\n',encoding='utf-8')
 subprocess.run(['git','add','--',PREFIX],cwd=REPO,check=True);staged=git('diff','--cached','--name-only').splitlines();assert sorted(staged)==inventory;assert all(p.startswith(PREFIX+'/') for p in staged)
 check=subprocess.run(['git','diff','--cached','--check'],cwd=REPO,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);assert check.returncode==0,check.stdout[:4000]
 for p in staged:assert subprocess.check_output(['git','show',':'+p],cwd=REPO)==(REPO/p).read_bytes(),p
 verify_frozen();subprocess.run(['git','-c','user.name=gkusper','-c','user.email=gkusper@aries.ektf.hu','commit','-m','Repair sparse source contract and distinguish operational verification failures'],cwd=REPO,check=True)
 commit=git('rev-parse','HEAD');assert git('rev-parse','HEAD^')==state['baseline_commit'];assert not git('status','--porcelain');assert git('rev-parse','experiment/cfaf-garage-pilot-v1')==state['baseline_commit'];assert git('rev-parse','wolala2026')=='5f377de38312fb39c088551f9c74f8b6d4bd5080';assert all(sha(REPO/p)==h for p,h in state['protected_files'].items());verify_frozen()
 for line in (ROOT/'checksums.sha256').read_text(encoding='utf-8').splitlines():
  h,path=line.split('  ',1);assert sha(REPO/path)==h,path
 summary=read(ROOT/'evaluation_summary.json');cost=read(ROOT/'api_usage.json');cached=read(ROOT/'cached_ablation_results.json');alias=read(ROOT/'reference_alias_ablation.json')
 receipt={'branch':git('branch','--show-current'),'commit':commit,'parent':state['baseline_commit'],'safe_files_committed':len(staged),'protected_files_unchanged':len(state['protected_files']),'elapsed_seconds':elapsed(),'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'working_tree_clean':True,'pushed':False,'merged':False,'completed_cases':10,'cached_old_valid':cached['summary']['A0']['valid'],'cached_new_valid':cached['summary']['A3']['valid'],'live_valid':summary['structural']['new_valid'],'live_gate_modes':summary['modes']['new_gate'],'control_raw_modes':summary['modes']['shared_control_raw'],'control_served_modes':summary['modes']['shared_control_served'],'gate_outcomes':summary['verification_outcomes'],'per_system_operational_response_failures':summary['per_system_operational_response_failures'],'R1_separate_valid':alias['valid'],'R1_primary_unchanged':True,'actual_public_citations':0,'mechanically_valid_unverified_associations':{k:v['mechanically_valid_unverified_associations'] for k,v in summary['public_citations'].items()},'API_attempts':cost['attempts'],'input_tokens':cost['input_tokens'],'output_tokens':cost['output_tokens'],'report':str(ROOT/'REPORT.md'),'detailed_report':str(ROOT/'local/REPORT_FULL.md'),'independent_validation':False}
 write(REPO.parent/'cfaf_sparse_source_repair_v1_completion.json',receipt);print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
