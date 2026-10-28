"""Finalize only safe artifacts after validating frozen data, index and old branches."""
import os,subprocess,json,hashlib,time,datetime
from .artifacts import *
from .deadline import ensure,elapsed
from .runner import verify_frozen
PREFIX=ROOT.relative_to(REPO).as_posix()
def git(*args):return subprocess.check_output(['git',*args],cwd=REPO,text=True).strip()
def main():
 ensure('safe local commit',60);verify_frozen();state=read(ROOT/'task_state.json');assert all(sha(REPO/p)==h for p,h in state['protected_files'].items());assert git('branch','--show-current')=='experiment/cfaf-garage-pilot-v1';assert git('rev-parse','HEAD')==state['baseline_commit'];assert git('rev-parse','experiment/cfaf-target-claim-alignment-v1')==state['baseline_commit']
 original_branch=git('rev-parse','wolala2026');assert original_branch=='5f377de38312fb39c088551f9c74f8b6d4bd5080'
 selection=read(ROOT/'dataset3_selection_manifest.json');raw=rows(ROOT/'selected_records.jsonl');audit=read(ROOT/'security_audit.json');audit['raw_artifacts_ignored']=True
 ignored=['datasets/GaRAGe_benchmark.jsonl','local/REPORT_FULL.md','selected_records.jsonl','runtime_inputs.jsonl','gold_annotations.jsonl','results.jsonl','per_case_diagnostics.jsonl','api_requests.jsonl','api_events.jsonl']
 for p in ignored:assert subprocess.run(['git','check-ignore','-q',PREFIX+'/'+p],cwd=REPO).returncode==0,p
 # Add non-independent review codes to local diagnostics without changing original labels or runtime.
 summary=read(ROOT/'qualitative_review_summary.json');diagnostics=rows(ROOT/'per_case_diagnostics.jsonl')
 for d,review in zip(diagnostics,summary['cases']):d['non_independent_agent_review']=review
 (ROOT/'per_case_diagnostics.jsonl').write_text(''.join(json.dumps(d,ensure_ascii=False)+'\n' for d in diagnostics),encoding='utf-8')
 for required in ['REPORT.md','README.md','DATASET_REGISTRY.md','GARAGE_SOURCE_AUDIT.md','GARAGE_ADAPTER_SPEC.md','dataset3_selection_manifest.json','dataset3_exposure_ledger.json','experiment_manifest.json','runtime_inputs.jsonl','gold_annotations.jsonl','results.jsonl','per_case_diagnostics.jsonl','grounding_metrics.json','mode_comparison.json','api_usage.json','security_audit.json','regression_audit.json','HUMAN_REVIEW_TEMPLATE.csv']:
  assert (ROOT/required).is_file(),required
 audit['selected_full_questions_references_passages_excluded_from_commit']=True;audit['credential_value_scan']='PASS';audit['commit_scope']=PREFIX+' only';audit['original_wolala2026_branch_unchanged']=original_branch;audit['precommit_elapsed_seconds']=elapsed();write(ROOT/'security_audit.json',audit)
 inventory=sorted(set(git('ls-files','--cached','--others','--exclude-standard','--',PREFIX).splitlines())|{PREFIX+'/CHANGED_FILES.txt',PREFIX+'/checksums.sha256'})
 (ROOT/'CHANGED_FILES.txt').write_text('\n'.join(inventory)+'\n',encoding='utf-8')
 credential=os.environ.get('OPENAI_API_KEY','').encode();privacy=[]
 for p in inventory:
  if p.endswith('/checksums.sha256'):continue
  b=(REPO/p).read_bytes();assert not credential or credential not in b,'Credential value detected'
  text=b.decode('utf-8-sig')
  for r in raw:
   if r['question'] in text:privacy.append((p,'original_question'))
   if r['answer_generate'] and r['answer_generate'] in text:privacy.append((p,'original_reference_answer'))
   for ground in r['grounding']:
    value=next(v for k,v in ground.items() if k.startswith('cite_'))
    if value and value in text:privacy.append((p,'full_original_passage'))
 assert not privacy,privacy
 (ROOT/'checksums.sha256').write_text('\n'.join(sha(REPO/p)+'  '+p for p in inventory if not p.endswith('/checksums.sha256'))+'\n',encoding='utf-8')
 subprocess.run(['git','add','--',PREFIX],cwd=REPO,check=True)
 staged=git('diff','--cached','--name-only').splitlines();assert sorted(staged)==inventory,(len(staged),len(inventory));assert all(p.startswith(PREFIX+'/') for p in staged)
 check=subprocess.run(['git','diff','--cached','--check'],cwd=REPO,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);assert check.returncode==0,check.stdout[:3000]
 for p in staged:assert subprocess.check_output(['git','show',':'+p],cwd=REPO)==(REPO/p).read_bytes(),p
 assert sha(ROOT/'runtime_inputs.jsonl')==read(ROOT/'experiment_manifest.json')['runtime_sha256'];verify_frozen()
 subprocess.run(['git','-c','user.name=gkusper','-c','user.email=gkusper@aries.ektf.hu','commit','-m','Add frozen original GaRAGe ten-case CFAF pilot and grounding audit'],cwd=REPO,check=True)
 commit=git('rev-parse','HEAD');assert git('rev-parse','HEAD^')==state['baseline_commit'];assert not git('status','--porcelain');assert git('rev-parse','wolala2026')==original_branch;assert git('rev-parse','experiment/cfaf-target-claim-alignment-v1')==state['baseline_commit'];assert all(sha(REPO/p)==h for p,h in state['protected_files'].items());verify_frozen()
 for line in (ROOT/'checksums.sha256').read_text(encoding='utf-8').splitlines():
  h,p=line.split('  ',1);assert sha(REPO/p)==h,p
 usage=read(ROOT/'api_usage.json');modes=read(ROOT/'mode_comparison.json');source=read(ROOT/'source_audit.json')
 receipt={'commit':commit,'branch':git('branch','--show-current'),'parent':state['baseline_commit'],'source_commit':source['commit'],'source_sha256':source['sha256'],'sample_ids':[r['sample_id'] for r in selection['records']],'completed_cases':10,'semantic_valid_cases':1,'semantic_invalid_cases':9,'mode_distributions':modes['distributions'],'api_attempts':usage['attempts'],'input_tokens':usage['input_tokens'],'output_tokens':usage['output_tokens'],'elapsed_seconds':elapsed(),'completion_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'working_tree_clean':True,'safe_files_committed':len(staged),'protected_files_unchanged':985,'pushed':False,'merged':False,'report':str(ROOT/'REPORT.md'),'detailed_local_report':str(ROOT/'local/REPORT_FULL.md'),'raw_artifacts_ignored':True,'independent_validation':False}
 write(REPO.parent/'cfaf_dataset3_garage_pilot_v1_completion.json',receipt);print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
