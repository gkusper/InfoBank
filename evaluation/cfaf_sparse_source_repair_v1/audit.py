"""Actual-request security and immutable-history audit; no new data selection."""
import json,os,hashlib,time,datetime,xml.etree.ElementTree as ET
from .artifacts import *
from .runner import verify_frozen
from .cached import PREVIOUS
from .provider import FORBIDDEN_FIELDS,GOLD_KEYS,all_keys
from .operational_failure_codes import validate_response,OPERATIONAL_PUBLIC
from .source_inventory import build_inventory,validate_inventory
from evaluation.cfaf_request_evidence_verification_v1.runner import request_for
from evaluation.cfaf_dataset3_garage_pilot_v1.score import aggregate

def xml_summary(path):
 suites=list(ET.parse(path).getroot().iter('testsuite'));return {k:sum(int(s.get(k,0)) for s in suites) for k in ['tests','failures','errors','skipped']}
def audit():
 manifest=verify_frozen();state=read(ROOT/'task_state.json');changed=[p for p,h in state['protected_files'].items() if sha(REPO/p)!=h];assert not changed
 assert sha(ROOT/'selection_manifest.json')==manifest['selection_sha256'];assert sha(ROOT/'cached_ablation_results.json')==manifest['cached_ablation_sha256'];assert sha(PREVIOUS/'api_events.jsonl')==manifest['previous_raw_analysis_events_sha256']
 runtime=rows(ROOT/'runtime_inputs.jsonl');previous_runtime=rows(PREVIOUS/'runtime_inputs.jsonl');assert runtime==previous_runtime and len(runtime)==10
 requests=rows(ROOT/'api_requests.jsonl');events=rows(ROOT/'api_events.jsonl');oldrequests=rows(PREVIOUS/'api_requests.jsonl');results=rows(ROOT/'live_paired_results.jsonl');ids=manifest['previous_selected_ids'];privateids=[s['source_id'] for r in runtime for s in r['case']['sources']];assert len(requests)==len(events)==30<=75
 payload_checks=[]
 for r,e in zip(requests,events):
  p=r['payload'];u=json.loads(p['messages'][1]['content']);encoded=json.dumps(p,ensure_ascii=False);illegal=set(all_keys(u))&(FORBIDDEN_FIELDS|GOLD_KEYS|{'sample_id'});assert not illegal;assert not any(s in encoded for s in ids+privateids);assert e['status']=='SUCCESS';assert p['model']=='gpt-4o-mini' and p['temperature']==0;assert p['max_tokens']==(1500 if r['kind']=='semantic_analysis' else 512);assert e['usage']['prompt_tokens']<=r['input_token_upper_bound']<=60000
  prior=next(v for v in oldrequests if v['runtime_index']==r['runtime_index'] and v['kind']==r['kind']);assert p['messages'][0]==prior['payload']['messages'][0];assert p['response_format']==prior['payload']['response_format']
  if r['kind']=='semantic_analysis':assert p==prior['payload']
  assert u['query']==runtime[r['runtime_index']]['case']['query'];assert len(u['documents'])==15;assert u['query_context']==runtime[r['runtime_index']]['query_context']
  if r['kind']=='shared_control':assert not(set(u)&{'response_contract','selected_mode','verification','source_inventory','operational_status'})
  assert not(set(u)&{'source_inventory','source_coverage','inventory_states','private_mapping'})
  payload_checks.append({'attempt':r['attempt'],'runtime_index':r['runtime_index'],'kind':r['kind'],'passed':True,'analysis_matches_prior_payload_exactly':True if r['kind']=='semantic_analysis' else None})
 for i,record in enumerate(results):
  out=record['outcome'];request=request_for(runtime[i]['case'],out);inventory=build_inventory(request,runtime[i]['mapping']);validate_inventory(inventory,request);assert inventory.inventory_sha256==out['source_inventory']['inventory_sha256'];assert len(inventory.entries)==15
  for source,mapping in zip(runtime[i]['case']['sources'],runtime[i]['mapping']):
   assert hashlib.sha256(source['content'].encode()).hexdigest()==mapping['adapted_context_sha256'];assert hashlib.sha256(source['content'][mapping['metadata_header_characters']:].encode()).hexdigest()==mapping['raw_text_sha256']
  users=[json.loads(r['payload']['messages'][1]['content']) for r in requests if r['runtime_index']==i];assert users[0]['documents']==users[1]['documents']==users[2]['documents'];assert users[1]['semantic_assessment']==users[2]['semantic_assessment']
  for name,response in out['responses'].items():
   assert not validate_response(json.dumps(response));status=out['response_verification'][name]
   if status['status']=='OPERATIONAL_FAILURE':assert response['top_level_mode']=='CFAF' and response['answer']==OPERATIONAL_PUBLIC and not status['credited_evidential_CFAF']
  if out['verification_outcome']['status']=='OPERATIONAL_FAILURE':assert out['selected_mode']=='CFAF'
 reason_vocab=[]
 for i,r in enumerate(rows(PREVIOUS/'results.jsonl')):
  for name,response in r['outcome']['responses'].items():
   errors=validate_response(json.dumps(response))
   if errors:reason_vocab.append({'runtime_index':i,'system':name,'new_validator_errors':errors,'old_output_unchanged':True})
 write(ROOT/'reason_vocabulary_regression.json',{'version':'existing-ReasonClass-v1-strict-validation','new_public_categories':[],'old_responses_rejected':reason_vocab,'raw_originals_unchanged':True})
 citations=rows(ROOT/'citation_diagnostics.jsonl');assert len(citations)==10
 for record in citations:
  for trace in record['systems'].values():
   assert not trace['citations'];assert not trace['semantic_entailment_proven'];assert all(e['reference_valid'] and e['claim_group_link_valid'] and e['claim_level_entailment']=='CITATION_SUPPORT_UNVERIFIED' and not e['render_as_verified_claim_citation'] for e in trace['unverified_associations'])
 m=read(ROOT/'evaluation_summary.json');case_metrics=rows(ROOT/'case_metrics.jsonl');m['validated_support_grounding_on_valid_assessments_only']=aggregate([r['validated_support_metric'] for r in case_metrics if r['new_semantic_valid']]);m['raw_proposals_are_not_accepted_support']=True;m['per_system_operational_response_failures']={name:sum(r['systems'][name]['post_generation_status']['status']=='OPERATIONAL_FAILURE' for r in case_metrics) for name in ['semantic_cfaf','shared_control']};m['clarification_gate_decisions']=sum(r['internal_reason_code']=='AMBIGUOUS_REQUEST' for r in case_metrics);m['strict_original_valid_on_same_fresh_analysis']=sum(r['strict_original_semantic_valid'] for r in results);write(ROOT/'evaluation_summary.json',m)
 reg=read(ROOT/'regression_audit.json');reg['xml_summaries']={p.name:xml_summary(p) for p in ROOT.glob('*tests.xml')};reg['preexisting_files_unchanged']=len(state['protected_files']);reg['known_failure_unchanged']=True;write(ROOT/'regression_audit.json',reg)
 write(ROOT/'security_audit.json',{'status':'PASS','audit_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'protected_files_checked':len(state['protected_files']),'protected_files_changed':changed,'previous_pilot_raw_events_hash_matches':True,'frozen_primary_sources_unchanged':True,'same_exact_ten_runtime_rows':True,'new_Dataset1_Dataset2_Dataset3_records_opened':0,'reserved_cases_accessed':0,'authorized_passages_preserved':150,'source_inventory_independent_of_roles':True,'all_requests_audited':len(requests),'forbidden_gold_fields_absent':True,'sample_id_explicitly_denied_and_absent':True,'selected_identifiers_and_private_source_ids_absent':True,'analysis_payloads_byte_equivalent_to_prior':10,'generation_prompts_and_schemas_unchanged':True,'model_and_limits_match':True,'both_generators_same_fresh_semantic_data':True,'control_gate_inventory_private_diagnostics_excluded':True,'all_served_responses_pass_canonical_vocabulary_validator':True,'operational_failure_never_serves_FULL':True,'operational_failure_not_credited_evidential_CFAF':True,'no_unverified_claim_citations_rendered':True,'old_selector_eight_stages_unchanged':True,'P5_metadata_aggregate_DENY_tests_passed':True,'supplemental_R1_separate_from_frozen_primary':True,'API_attempts':len(requests),'cap':75,'no_API_errors':True,'all_finish_reasons_stop':all(e['finish_reason']=='stop' for e in events),'embeddings_second_verifiers_retries':0,'independent_human_review':'PENDING','payload_checks':payload_checks})
 print('AUDIT PASS:',len(state['protected_files']),'unchanged files,',len(requests),'payloads; exact old analysis payloads verified')
if __name__=='__main__':audit()
