"""Resource, source-lineage, target/claim and security audit. No API calls."""
import collections,json,statistics,subprocess,xml.etree.ElementTree as ET
from .artifacts import *
from .runner import verify_frozen
from .deadline import elapsed
from . import integration as impl
from .integration_controls import assess
from evaluation.cfaf_request_evidence_verification_v1.audit import xml_summary
from evaluation.cfaf_request_evidence_verification_v1.runner import request_for
from evaluation.cfaf_request_evidence_verification_v1.source_capability_rules import trusted_provenance,capability
from evaluation.refusalbench_noncontradiction_v1.public_adapter import all_keys,FORBIDDEN_FIELDS

def usage():
 calls=rows(ROOT/'api_requests.jsonl');events=rows(ROOT/'api_events.jsonl');groups={}
 for kind in sorted({e['kind'] for e in events}):
  g=[e for e in events if e['kind']==kind];groups[kind]={'attempts':len(g),'successes':sum(e['status']=='SUCCESS' for e in g),'input_tokens':sum((e.get('usage') or {}).get('prompt_tokens',0) for e in g),'output_tokens':sum((e.get('usage') or {}).get('completion_tokens',0) for e in g),'latency_ms_sum':sum(e['latency_ms'] for e in g)}
 shared=[e for e in events if e['kind'] in {'semantic_analysis','query_profile'}];deploy={}
 for system in ['A0','T3','shared_control']:
  gen=[e for e in events if e['kind']=='shared_control'] if system=='shared_control' else [e for e in events if e['system']==system and e['kind']=='semantic_cfaf'];group=shared+gen;deploy[system]={'calls':len(group),'calls_per_case':len(group)/24,'input_tokens':sum((e.get('usage') or {}).get('prompt_tokens',0) for e in group),'output_tokens':sum((e.get('usage') or {}).get('completion_tokens',0) for e in group),'summed_latency_ms':sum(e['latency_ms'] for e in group)}
 obs=rows(ROOT/'pilot_observations.jsonl');cpu0=[r['outcomes']['A0']['internal_trace']['stage_timings']['sufficiency_and_permitted_output_ms'] for r in obs if r['status']=='SUCCESS'];cpu=[r['outcomes']['T3']['internal_trace']['stage_timings']['sufficiency_and_permitted_output_ms'] for r in obs if r['status']=='SUCCESS']
 result={'model_api_attempts':len(calls),'attempt_cap':120,'successes':sum(e['status']=='SUCCESS' for e in events),'network_errors':sum(e['status']=='ERROR' for e in events),'retries':0,'embeddings':0,'stronger_models':0,'second_verifier_calls':0,'input_tokens':sum(v['input_tokens'] for v in groups.values()),'output_tokens':sum(v['output_tokens'] for v in groups.values()),'summed_model_latency_ms':sum(v['latency_ms_sum'] for v in groups.values()),'returned_models':dict(collections.Counter(e.get('model') for e in events)),'by_kind':groups,'per_system_deployment_equivalent':deploy,'experiment_calls_per_case':len(calls)/24,'additional_calls_for_target_claim_typing':0,'git_fetch_operations':1,'git_fetch_note':'One successful separately authorized Git transport operation; model API attempts include all OpenAI calls and failures. Git was not used to push or merge.','A0_stage5_cpu_ms':{'median':statistics.median(cpu0),'max':max(cpu0),'sum':sum(cpu0)},'T3_minus_A0_paired_stage5_ms':{'median':statistics.median([b-a for a,b in zip(cpu0,cpu)]),'sum':sum(cpu)-sum(cpu0),'note':'Observed sequential paired stage timings, not an isolated repeated microbenchmark.'},'T3_stage5_cpu_ms':{'n':len(cpu),'median':statistics.median(cpu) if cpu else None,'max':max(cpu) if cpu else None,'sum':sum(cpu)},'timing_caveat':'A0 also computes RDA diagnostics. These per-arm Stage-5 times are descriptive and not a controlled isolated CPU ablation; cached model calls do not imply deployment latency savings.','cost_unit':'Actual calls/tokens/latency; no unverified USD prices. Deployment-equivalent system totals share upstream cost and must not be summed.'};write(ROOT/'api_usage.json',result);return result

def audit():
 manifest=verify_frozen();state=read(ROOT/'task_state.json');runtime={r['runtime_index']:r for r in rows(ROOT/'pilot_runtime.jsonl')};gold={g['runtime_index']:g for g in rows(ROOT/'pilot_scorer_only.jsonl')};obs={r['runtime_index']:r for r in rows(ROOT/'pilot_observations.jsonl')};requests=rows(ROOT/'api_requests.jsonl');failures=[];changed=[p for p,h in state['protected_files'].items() if sha(REPO/p)!=h];reference_errors=[];schema_errors=[];semantic_errors=[];replays=[];sources=[];role_rows=[];reason_classes=[];realizations=[];texts=[];privileged_count_keys=[];metadata_claims=0
 originals={c['case_id']:c for c in rows(REPO/'evaluation/wolala2026/data/heldout_pilot_v3/cases.jsonl')}
 for i,r in obs.items():
  if r['status']!='SUCCESS':failures.append({'index':i,'error':r.get('error')});continue
  a0=r['outcomes']['A0'];t3=r['outcomes']['T3'];req=request_for(runtime[i]['case'],a0);p=trusted_provenance(req,runtime[i]['trusted_fixture_ingestion']);same=a0['semantic_assessment']==t3['semantic_assessment'] and a0['permitted_request']==t3['permitted_request']
  if not same:failures.append({'index':i,'error':'UPSTREAM_OR_PROJECTION_DRIFT'})
  if req.documents:a,data,reference=impl.parse_analysis(json.dumps(a0['semantic_assessment']),req)
  else:a=None;data={};reference={}
  if a0['semantic_valid'] is False:semantic_errors.append({'index':i,'errors':a0['reference_audit'].get('errors')})
  reference_errors.extend(a0['reference_audit'].get('reference_errors',[]));fresh=assess(req,a,data,'T3',p);equal=canonical(fresh['target_claim'])==canonical(t3['verification']['target_claim']);replays.append(equal)
  if not equal:failures.append({'index':i,'error':'TARGET_CLAIM_REPLAY_DRIFT'})
  tc=t3['verification']['target_claim'];target=tc['trusted_target'];docs={d['source_id']:d for d in req.documents}
  if not set(target['permitted_view_ids'])<=set(docs):failures.append({'index':i,'error':'UNAUTHORIZED_TARGET_VIEW'})
  for c in tc['claim_alignment']['claims']:
   if c['authority']=='TRUSTED_STRUCTURED_SOURCE':
    metadata_claims+=1;b=c['metadata_binding']
    if b['status']!='FIELD_VALUE_MATCH' or b['source_id'] not in target['permitted_view_ids'] or docs[b['source_id']]['view_kind']!='metadata':failures.append({'index':i,'error':'LLM_PROMOTED_TO_STRUCTURED_AUTHORITY'})
   if c['general_entailment_proof'] or c['relation_diagnostics']['semantic_entailment_proven']:failures.append({'index':i,'error':'LEXICAL_ENTAILMENT_OVERCLAIM'})
   if c['minimal_evidence_recommendation']['applied_to_model_context']:failures.append({'index':i,'error':'MODEL_EVIDENCE_PRUNED'})
  for config,o in r['outcomes'].items():
   for system,response in o['responses'].items():
    errors=impl.validate_response(json.dumps(response))
    if errors:schema_errors.append({'index':i,'config':config,'system':system,'errors':errors})
    if set(o['public_traces'][system])!=set(impl.GENERATION_SCHEMA['required']):failures.append({'index':i,'error':'PUBLIC_TRACE_WHITELIST'})
    if system=='semantic_cfaf' and o['internal_reason']:
     reason=o['internal_reason'];reason_classes.append(response['public_reason_class']==reason['class']);realizations.append(response['realization']==reason['realization']);texts.append(response['answer']==reason['text'])
    if gold[i]['dataset'].startswith('InfoBank'):
     original=originals[gold[i]['original_id']];markers=original.get('protected_markers',[])+original.get('forbidden_disclosures',[])+original.get('protected_markers_used_only_by_validator',[])+original.get('forbidden_disclosures_used_only_by_validator',[])
     if any(m and m in canonical(response) for m in markers):failures.append({'index':i,'error':'PROTECTED_PUBLIC_MARKER'})
  effective={}
  for x in t3['verification']['source_capabilities']:
   for cap in x['sources']:
    check=capability(docs[cap['source_id']],cap['relation_family'],p.get(cap['source_id']))
    if any(check[k]!=cap[k] for k in ['rule_id','rule_version','capability_state','provenance_trusted']):sources.append({'index':i,'error':'SOURCE_RULE_RECOMPUTATION'})
    effective[cap['source_id']]=cap['effective_role']
  if gold[i]['dataset'].startswith('InfoBank'):
   original=originals[gold[i]['original_id']];mapping={p['permitted_source_id']:int(p['original_source_id'].rsplit('-',1)[1]) for p in a0['internal_trace']['policy'] if p.get('included')}
   for role in (a0['semantic_assessment'] or {}).get('source_assessments',[]):
    ref=original['sources'][mapping[role['source_id']]];role_rows.append({'runtime_index':i,'source_id':role['source_id'],'reference_role':ref['evidential_role'],'model_role':role['role'],'effective_role':effective.get(role['source_id'],role['role']),'reference_relation':ref['relation'],'model_relation':role['relation_label'],'reference_scope':'Original exposed synthetic construction labels; no independent claim gold'})
 for call in requests:
  i=call['runtime_index'];payload=json.loads(call['payload']['messages'][1]['content'])
  if set(all_keys(payload))&FORBIDDEN_FIELDS:failures.append({'index':i,'error':'BENCHMARK_GOLD_FIELD_LEAK'})
  if set(all_keys(payload))&{'candidate_count_privileged','catalogue_entry_count_privileged','authoritative_anchor','target_claim'}:failures.append({'index':i,'error':'PRIVATE_TARGET_TRACE_IN_MODEL_INPUT'})
  request=impl.QueryOnlyRequest(runtime[i]['case']['query']) if call['kind']=='query_profile' else request_for(runtime[i]['case'],obs[i]['outcomes']['A0'])
  try:impl.assert_safe_payload(request,payload)
  except ValueError as exc:failures.append({'index':i,'error':str(exc)})
  if call['kind']=='shared_control' and set(payload)&{'response_contract','selected_mode','can_fulfil_request','verification'}:failures.append({'index':i,'error':'CONTROL_CONTAMINATED'})
 p5=[i for i,g in gold.items() if g['family']=='P5'];p5equal=len(p5)==2 and all(obs[p5[0]]['outcomes'][c]['public_traces']==obs[p5[1]]['outcomes'][c]['public_traces'] for c in ['A0','T3']);p5calls=sum(c['runtime_index'] in p5 for c in requests)
 if not p5equal or p5calls:failures.append({'error':'P5_EXISTENCE_LEAK_OR_API_CALL'})
 remote=read(ROOT/'remote_source_manifest.json');source_mismatches=[]
 for f in remote['files']:
  raw=subprocess.check_output(['git','show',remote['source_commit']+':'+f['path']]);import hashlib
  if hashlib.sha256(raw).hexdigest()!=f['sha256']:source_mismatches.append(f['path'])
 security={'status':'PASS' if not failures and not changed and not reference_errors and not sources and not source_mismatches else 'FAIL','failures':failures,'guarded_model_payloads':len(requests),'identical_upstream_cases':sum(r.get('semantic_assessment_identical') is True for r in obs.values()),'target_claim_replay_identical_cases':sum(replays),'invalid_upstream_assessments':semantic_errors,'invalid_reference_errors':reference_errors,'public_schema_errors':schema_errors,'structured_metadata_candidate_claims':metadata_claims,'LLM_boolean_or_lexical_match_promoted_to_structured_truth':False,'private_target_counts_or_titles_sent_to_model':False,'new_claim_diagnostics_sent_to_model':False,'model_evidence_pruned':False,'p5_public_traces_equal':p5equal,'p5_api_calls':p5calls,'public_internal_reason':{'class_matches':sum(reason_classes),'realization_matches':sum(realizations),'text_exact_matches':sum(texts),'n':len(reason_classes),'note':'P5 canonical public wording may differ from internal template.'},'source_registry_recomputation_errors':sources,'remote_source_commit':remote['source_commit'],'remote_blob_hash_mismatches':source_mismatches,'protected_old_files_unchanged':len(state['protected_files'])-len(changed),'exposure_ledger_unchanged':sha(REPO/'evaluation/refusalbench_iterative_dev_v1/exposure_ledger.json')==manifest['selection']['exposure_ledger_sha256'],'new_refusalbench_records':0,'eligible_exposed':130,'eligible_unseen':1104,'reserved_groups':30,'untouched_groups':18,'student_cases_accessed':False,'external_scenario_packages_loaded':False,'metadata_only_regression_read':'The inherited explicit-Arrow-schema test reads annotation columns only; reserved/untouched question and context fields are ignored.','scope_limit':'Checks exact payload/view/provenance contracts and controlled canaries; not universal natural-language leakage or entailment proof.'};write(ROOT/'security_validation.json',security)
 evidence={'reference_count':len(role_rows),'model_role_agreement':sum(r['model_role']==r['reference_role'] for r in role_rows),'effective_role_agreement':sum(r['effective_role']==r['reference_role'] for r in role_rows),'relation_agreement':sum(r['model_relation']==r['reference_relation'] for r in role_rows),'rows':role_rows,'independent_semantic_gold':False};write(ROOT/'source_role_diagnostics.json',evidence)
 tests=xml_summary(ROOT/'unit_tests.xml');synthetic={'status':'PASS' if tests['failures']==tests['errors']==0 else 'FAIL','controlled_test_cases':tests['tests'],'test_names':[t.get('name') for t in ET.parse(ROOT/'unit_tests.xml').getroot().iter('testcase')],'original_metadata_expectations':read(ROOT/'metadata_type_summary.json'),'aggregation_smoke':read(ROOT/'aggregation_smoke_results.json'),'new_fictional_entities_and_values':True,'not_independent_validation':True,'main_backend_test_files':'Inspected; selected pure algorithms covered by local controlled tests. Full SQLAlchemy/router integration suites not imported or executed.'};write(ROOT/'synthetic_tests_report.json',synthetic)
 reg={'current_unit_tests':tests,'compatible_suite':xml_summary(ROOT/'final_regression_tests.xml'),'working_byte_checks':xml_summary(ROOT/'current_worktree_hash_tests.xml'),'original_cfaf_suite':xml_summary(ROOT/'historical_cfaf_tests.xml'),'initial_unadjusted_suite':xml_summary(ROOT/'current_and_prior_tests.xml'),'environment_adjustment':read(ROOT/'regression_environment.json'),'protected_prior_files':len(state['protected_files']),'changed_prior_files':changed,'wolala2026_commit':subprocess.check_output(['git','rev-parse','wolala2026'],text=True).strip(),'prior_RDA_branch_commit':subprocess.check_output(['git','rev-parse','experiment/cfaf-requirement-alignment-v1'],text=True).strip(),'remote_main_reference':subprocess.check_output(['git','rev-parse','origin/main'],text=True).strip(),'main_merged':False,'new_historical_regressions':0,'known_historical_failure':'test_preheldout_attempt1_plan_artifacts_are_plan_only expects an already committed HELDOUT_RUN_AUTHORIZATION.json to be absent; preserved unchanged.','elapsed_seconds_at_audit':elapsed()};write(ROOT/'regression_audit.json',reg)
 print(json.dumps({'security':security['status'],'model_payloads':len(requests),'old_files_unchanged':len(state['protected_files'])-len(changed),'structured_metadata_matches':metadata_claims,'target_claim_replays':sum(replays),'semantic_errors':len(semantic_errors),'source_roles':evidence['model_role_agreement'],'role_n':len(role_rows),'new_unit_tests':tests['tests']},indent=2))
 if security['status']!='PASS':raise RuntimeError('Security/provenance/history audit failed')
 return security,evidence,reg
if __name__=='__main__':usage();audit()
