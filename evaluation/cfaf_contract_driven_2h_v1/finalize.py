"""Finalize safe study artifacts, preserving every earlier file and branch."""
import os,json,subprocess,hashlib,datetime
from .artifacts import *
from .runner import verify_frozen
from .deadline import ensure,elapsed
PREFIX=ROOT.relative_to(REPO).as_posix()
def git(*args):return subprocess.check_output(['git',*args],cwd=REPO,text=True).strip()
def main():
 ensure('local commit and receipt',90);m=verify_frozen();state=read(ROOT/'task_state.json');tag=read(ROOT/'git_freeze_manifest.json');assert git('branch','--show-current')=='experiment/cfaf-contract-driven-v1';assert git('rev-parse','HEAD')==state['baseline_commit'];assert git('rev-parse','experiment/cfaf-sparse-source-repair-v1')==state['baseline_commit'];assert git('rev-parse','wolala2026')==tag['local_commit'];assert git('rev-parse',tag['annotated_tag']+'^{}')==tag['local_commit'];assert git('cat-file','-t',tag['annotated_tag'])=='tag';assert all(sha(REPO/p)==h for p,h in state['protected_files'].items())
 required=['REPORT.md','MAKE_OR_REUSE.md','CONTRACTS.md','WOLALA2026_FREEZE.md','PREREGISTRATION.md','experiment_manifest.json','dataset1_results.jsonl','dataset2_results.jsonl','dataset3_results.jsonl','comparison_summary.csv','paired_mode_confusions.json','grounding_metrics.json','operational_failures.json','api_usage.json','security_audit.json','regression_audit.json','RESULTS_FOR_PAPER.tex','PAPER_INTEGRATION_NOTES.md','DATASET3_ADJUDICATION_TEMPLATE.csv','DATASET3_ADJUDICATION_RUBRIC.md']
 for p in required:assert (ROOT/p).is_file(),p
 plan=read(ROOT/'selection_plan.json');summary=read(ROOT/'comparison_summary.json');usage=read(ROOT/'api_usage.json');requests=rows(ROOT/'api_requests.jsonl');events=rows(ROOT/'api_events.jsonl');assert len(requests)==len(events)==usage['attempts']<=480;assert [r['attempt'] for r in requests]==list(range(1,len(requests)+1));assert all(r['started_at_epoch']-state['start_epoch']<6300 for r in requests);assert all(v['paired_executions_completed']==plan['planned_case_counts'][d] for d,v in summary.items());assert sum(v['planned'] for v in summary.values())==160
 rm=read(ROOT/'runtime_manifest.json');assert m['frozen_at_epoch']<=datetime.datetime.fromisoformat(rm['prepared_utc']).timestamp()<requests[0]['started_at_epoch']
 ignored=['api_requests.jsonl','api_events.jsonl','local/CASE_REPORT.md','local/dataset3_blinded_review_packet.jsonl','local/dataset3_blinding_key.json']+[d+s for d in plan['planned_case_counts'] for s in ['_runtime.jsonl','_gold.jsonl','_results_raw.jsonl']]
 for p in ignored:assert (ROOT/p).is_file() and subprocess.run(['git','check-ignore','-q',PREFIX+'/'+p],cwd=REPO).returncode==0,p
 write(ROOT/'raw_artifact_hashes.json',{'scope':'Only hashes/names of ignored original inputs, scorer data and raw traces; no raw content','files':{p:sha(ROOT/p) for p in ignored},'inference_complete_before_scoring':True})
 for d,N in plan['planned_case_counts'].items():
  assert len(rows(ROOT/(d+'_runtime.jsonl')))==len(rows(ROOT/(d+'_gold.jsonl')))==len(rows(ROOT/(d+'_results_raw.jsonl')))==N
 ds3=read(ROOT/'dataset3_selection_manifest.json')['records'];g3=rows(ROOT/'dataset3_gold.jsonl');assert len({r['sample_id'] for r in ds3})==80;assert all(a['sample_id']==b['sample_id'] and a['row_zero_based']==plan['dataset3']['selected_indices_zero_based'][i] for i,(a,b) in enumerate(zip(ds3,g3)))
 sec=read(ROOT/'security_audit.json');sec.update(raw_artifacts_confirmed_ignored=True,safe_commit_scope=PREFIX+' only',credential_value_scan='PASS',exact_question_and_long_source_reference_scan='PASS',prior_files_unchanged=1090,precommit_elapsed_seconds=elapsed(),manual_push_only=True);write(ROOT/'security_audit.json',sec)
 inventory=sorted(set(git('ls-files','--cached','--others','--exclude-standard','--',PREFIX).splitlines())|{PREFIX+'/CHANGED_FILES.txt',PREFIX+'/checksums.sha256'});(ROOT/'CHANGED_FILES.txt').write_text('\n'.join(inventory)+'\n',encoding='utf-8')
 questions=[];longtexts=[]
 for d in plan['planned_case_counts']:
  for r in rows(ROOT/(d+'_runtime.jsonl')):
   questions.append(r['case']['query'])
   for source in r['case']['sources']:
    for key in ['content','aggregate_view']:
     text=source.get(key)
     if isinstance(text,str) and len(text)>=80:longtexts.append(text)
  for g in rows(ROOT/(d+'_gold.jsonl')):
   for key in ['answer_generate','answer_related_info','implementation_reasoning','gold_answer']:
    value=g.get(key)
    if isinstance(value,str) and len(value)>=40:longtexts.append(value)
   longtexts.extend(v for v in g.get('original_answers',[]) if isinstance(v,str) and len(v)>=40)
 credential=os.environ.get('OPENAI_API_KEY','').encode();violations=[]
 for p in inventory:
  if p.endswith('/checksums.sha256'):continue
  b=(REPO/p).read_bytes();assert not credential or credential not in b,'Credential value in safe output';text=b.decode('utf-8-sig')
  if any(q and q in text for q in questions):violations.append((p,'exact_original_question'))
  if any(v in text for v in longtexts):violations.append((p,'long_original_source_or_reference'))
 assert not violations,violations
 (ROOT/'checksums.sha256').write_text('\n'.join(sha(REPO/p)+'  '+p for p in inventory if not p.endswith('/checksums.sha256'))+'\n',encoding='utf-8')
 subprocess.run(['git','add','--',PREFIX],cwd=REPO,check=True);staged=git('diff','--cached','--name-only').splitlines();assert sorted(staged)==inventory;assert all(p.startswith(PREFIX+'/') for p in staged)
 diff=subprocess.run(['git','diff','--cached','--check'],cwd=REPO,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);assert diff.returncode==0,diff.stdout[:3000]
 for p in staged:assert subprocess.check_output(['git','show',':'+p],cwd=REPO)==(REPO/p).read_bytes(),p
 verify_frozen();subprocess.run(['git','-c','user.name=gkusper','-c','user.email=gkusper@aries.ektf.hu','commit','-m','Freeze CFAF baseline and add preregistered three-dataset contract study'],cwd=REPO,check=True)
 commit=git('rev-parse','HEAD');assert git('rev-parse','HEAD^')==state['baseline_commit'];assert not git('status','--porcelain');assert git('rev-parse','wolala2026')==tag['local_commit'];assert git('rev-parse','experiment/cfaf-sparse-source-repair-v1')==state['baseline_commit'];verify_frozen();assert all(sha(REPO/p)==h for p,h in state['protected_files'].items())
 for line in (ROOT/'checksums.sha256').read_text(encoding='utf-8').splitlines():h,p=line.split('  ',1);assert sha(REPO/p)==h,p
 receipt={'branch':git('branch','--show-current'),'commit':commit,'starting_commit':state['baseline_commit'],'historical_wolala_commit':tag['local_commit'],'local_freeze_tag':tag['annotated_tag'],'safe_files_committed':len(staged),'prior_files_unchanged':len(state['protected_files']),'planned_and_paired_complete':{d:{'planned':v['planned'],'complete':v['paired_executions_completed'],'incomplete':v['incomplete']} for d,v in summary.items()},'dataset1_mode_accuracy':{s:v['mode_accuracy_nonoperational'] for s,v in summary['dataset1']['systems'].items()},'dataset2_development_mode_accuracy':{s:v['mode_accuracy_nonoperational'] for s,v in summary['dataset2']['systems'].items()},'dataset3_mode_accuracy':None,'API_attempts':usage['attempts'],'input_tokens':usage['input_tokens'],'output_tokens':usage['output_tokens'],'elapsed_seconds':elapsed(),'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'two_hour_limit_respected':elapsed()<7200,'working_tree_clean':True,'pushed':False,'merged':False,'report':str(ROOT/'REPORT.md'),'paper_tex':str(ROOT/'RESULTS_FOR_PAPER.tex'),'local_case_report':str(ROOT/'local/CASE_REPORT.md'),'new_architecture_claimed_as_evaluated':False,'independent_semantic_adjudication':'PENDING'}
 write(REPO.parent/'cfaf_contract_driven_2h_v1_completion.json',receipt);print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
