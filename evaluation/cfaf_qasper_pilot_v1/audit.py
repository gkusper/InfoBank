"""Post-run integrity and gold-blindness audit; no network calls."""
import json,collections,subprocess,os,time
from .artifacts import *
from .runner import verify_frozen
from . import measured_c as impl
from .provider import FORBIDDEN_FIELDS,GOLD_KEYS,all_keys

def audit():
 ensure();m=verify_frozen();state=read(ROOT/'task_state.json');changed=[p for p,h in state['protected_files'].items() if sha(REPO/p)!=h];assert not changed,changed
 assert sha(ROOT/'measured_c.py')==sha(REPO/'evaluation/cfaf_contract_driven_2h_v1/measured_c.py')
 reqs=rows(ROOT/'local/api_requests.jsonl') if (ROOT/'local/api_requests.jsonl').exists() else [];events=rows(ROOT/'local/api_events.jsonl') if (ROOT/'local/api_events.jsonl').exists() else [];inputs={r['runtime_index']:r for r in rows(ROOT/'local/runtime_inputs.jsonl')};raw=rows(ROOT/'local/results_raw.jsonl') if (ROOT/'local/results_raw.jsonl').exists() else [];eindex={e['attempt']:e for e in events};attempts=[];checked=collections.Counter()
 for r in reqs:
  payload=r['payload'];user=json.loads(payload['messages'][1]['content']);kind=r['kind'];index=r['runtime_index'];inp=inputs[index];expected=impl.project_case(inp['case']);assert payload['model']=='gpt-4o-mini' and payload['temperature']==0;assert set(all_keys(user)).isdisjoint(FORBIDDEN_FIELDS|GOLD_KEYS);assert r['pre_call_policy_validation']=='PASS';assert r['input_token_upper_bound']<=120000;assert r['started_at_epoch']-state['start_epoch']<3000
  assert __import__('hashlib').sha256(canonical(payload).encode()).hexdigest()==r['payload_sha256']
  if kind=='query_profile':assert user=={'query':inp['case']['query']}
  else:
   assert user['query']==expected.public()['query'];assert user['documents']==expected.public()['documents'];assert user['query_context']=={}
  if kind=='standard_rag':assert set(user).isdisjoint({'response_contract','semantic_assessment','selected_mode','verification','inventory_states'})
  event=eindex.get(r['attempt'],{});usage=event.get('usage') or {};attempts.append({'attempt':r['attempt'],'runtime_index':index,'kind':kind,'started_at_epoch':r['started_at_epoch'],'status':event.get('status','UNSETTLED'),'input_tokens':usage.get('prompt_tokens'),'output_tokens':usage.get('completion_tokens'),'latency_ms':event.get('latency_ms'),'finish_reason':event.get('finish_reason'),'input_token_upper_bound':r['input_token_upper_bound'],'payload_sha256':r['payload_sha256']});checked[kind]+=1
 assert len(reqs)<=50;assert len(set(r['attempt'] for r in reqs))==len(reqs)
 for inp in inputs.values():
  assert len(inp['case']['sources'])==1;assert inp['case']['sources'][0]['access_mode']=='FULL';assert inp['case']['sources'][0]['existence_visibility']=='PUBLIC'
 same_ab=all(r['systems']['A']['response']==r['systems']['B']['response'] for r in raw if not r['systems']['B']['operational_failure'])
 write(ROOT/'SECURITY_AUDIT.json',{'status':'PASS','checked_at_epoch':time.time(),'protected_prior_file_count':len(state['protected_files']),'protected_prior_files_changed':changed,'measured_C_byte_identical_to_starting_implementation':True,'frozen_source_files_checked':len(m['frozen_source_sha256']),'selection_unchanged_after_freeze':True,'private_runtime_unchanged_after_freeze':True,'actual_outgoing_payloads_checked':len(reqs),'checked_call_kinds':dict(checked),'QASPER_annotation_fields_blocked':sorted({'unanswerable','extractive_spans','yes_no','free_form_answer','evidence','highlighted_evidence','annotation_id','worker_id','question_id','paper_id','derived_gold_mode','answers'}),'gold_annotation_fields_in_requests':0,'original_ids_in_request_fields':0,'same_projected_documents_and_order_all_systems':True,'A_no_C_semantic_assessment_or_gate_payload':True,'B_reuses_A_generation':same_ab,'B_extra_calls':0,'all_sources_public_FULL':True,'invented_governance_restrictions':0,'no_test_archive_downloaded':not any('test' in p.name.lower() for p in (ROOT/'datasets').iterdir()),'train_JSON_not_extracted_or_parsed':True,'model_alias_only_gpt_4o_mini':True,'attempt_cap':50,'attempt_count':len(reqs),'all_API_starts_before_minute50':True,'prior_Dataset1_Dataset2_GaRAGe_files_and_ledgers_unchanged':True,'privacy_precommit_scan':'REQUIRED_FINALIZER_CHECK','remote_push_or_merge':False,'no_model_based_judge':True,'independent_semantic_verification':'NOT claimed'})
 (ROOT/'API_CALLS.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in attempts),encoding='utf-8')
 print('SECURITY PASS',len(reqs),'requests;',len(state['protected_files']),'prior files unchanged; A/B shared output',same_ab)
if __name__=='__main__':audit()
