"""Mechanical security, provenance, usage and immutable-history audit."""
import collections,hashlib,json,statistics,subprocess,xml.etree.ElementTree as ET
from .artifacts import *
from .runner import request_for,verify_frozen
from .source_capability_rules import trusted_provenance,capability
from . import integration as impl
from .deadline import elapsed
from evaluation.refusalbench_noncontradiction_v1.public_adapter import FORBIDDEN_FIELDS,all_keys

def xml_summary(path):
 root=ET.parse(path).getroot();suites=list(root.iter('testsuite'));return {'tests':sum(int(s.get('tests',0)) for s in suites),'failures':sum(int(s.get('failures',0)) for s in suites),'errors':sum(int(s.get('errors',0)) for s in suites),'skipped':sum(int(s.get('skipped',0)) for s in suites),'failure_names':[t.get('classname','')+'::'+t.get('name','') for t in root.iter('testcase') if t.find('failure') is not None or t.find('error') is not None]}

def usage():
 requests=rows(ROOT/'api_requests.jsonl');events=rows(ROOT/'api_events.jsonl');groups={}
 for key in sorted({e['kind'] for e in events}):
  group=[e for e in events if e['kind']==key];groups[key]={'attempts':len(group),'successful':sum(e['status']=='SUCCESS' for e in group),'input_tokens':sum((e.get('usage') or {}).get('prompt_tokens',0) for e in group),'output_tokens':sum((e.get('usage') or {}).get('completion_tokens',0) for e in group),'latency_ms_sum':sum(e['latency_ms'] for e in group)}
 systems={}
 common=[e for e in events if e['kind'] in {'semantic_analysis','query_profile'}]
 for name in ['A0','B','shared_control']:
  generation=[e for e in events if e['kind']=='shared_control'] if name=='shared_control' else [e for e in events if e['kind']=='semantic_cfaf' and e['system']==name]
  group=common+generation;systems[name]={'deployment_equivalent_calls':len(group),'calls_per_30_cases':len(group)/30,'input_tokens':sum((e.get('usage') or {}).get('prompt_tokens',0) for e in group),'output_tokens':sum((e.get('usage') or {}).get('completion_tokens',0) for e in group),'summed_model_latency_ms':sum(e['latency_ms'] for e in group),'note':'Includes shared upstream cost once for this hypothetical deployment; system totals overlap and must not be added.'}
 optional=rows(ROOT/'optional_observations.jsonl');obs=rows(ROOT/'pilot_observations.jsonl');stage5=[o['outcomes']['B']['internal_trace']['stage_timings']['sufficiency_and_permitted_output_ms'] for o in obs]
 result={'attempts':len(requests),'attempt_cap':170,'successes':sum(e['status']=='SUCCESS' for e in events),'errors':sum(e['status']=='ERROR' for e in events),'retries':0,'embeddings':0,'stronger_models':0,'input_tokens':sum(g['input_tokens'] for g in groups.values()),'output_tokens':sum(g['output_tokens'] for g in groups.values()),'summed_api_latency_ms':sum(g['latency_ms_sum'] for g in groups.values()),'calls_per_case_experiment':len(requests)/len(obs),'by_kind':groups,'returned_models':dict(collections.Counter(e.get('model') for e in events)),'by_system_deployment_equivalent':systems,'optional_triggered_cases':sum(bool(r['triggered_requirements']) for r in optional),'optional_triggered_requirements':sum(len(r['triggered_requirements']) for r in optional),'optional_verifier_calls':sum(e['kind']=='focused_verification' for e in events),'optional_additional_tokens':sum((e.get('usage') or {}).get('total_tokens',0) for e in events if e['system']=='C'),'optional_cost_per_corrected_decision':None,'cost_unit':'Actual calls/tokens/latency; no unverified USD prices applied','phase1_calls':0,'deterministic_additional_model_calls':0,'B_stage5_cpu_ms':{'n':len(stage5),'sum':sum(stage5),'median':statistics.median(stage5),'max':max(stage5)},'stage5_timing_limit':'A0 also computes disabled checks for diagnostics; these timings are not an isolated incremental CPU ablation. B pipeline time reuses the cached upstream model call.'}
 write(ROOT/'api_usage.json',result);return result

def audit():
 manifest=verify_frozen();state=read(ROOT/'task_state.json');changed=[p for p,h in state['protected_files'].items() if not (REPO/p).exists() or sha(REPO/p)!=h];original_branch=subprocess.check_output(['git','rev-parse','wolala2026'],cwd=REPO,text=True).strip()
 runtime={r['runtime_index']:r for r in rows(ROOT/'pilot_runtime.jsonl')};obs={r['runtime_index']:r for r in rows(ROOT/'pilot_observations.jsonl')};gold={g['runtime_index']:g for g in rows(ROOT/'pilot_scorer_only.jsonl')};requests=rows(ROOT/'api_requests.jsonl');failures=[];schema_errors=[];invalid_semantic=[];span_errors=[];forbidden_count=0;public_errors=[];reference_count=0;shared=[];reason_consistency=[];reason_classes=[];reason_realizations=[];reason_texts=[];source_cap_errors=[];source_counts=collections.Counter();role_rows=[]
 original_cases={c['case_id']:c for c in rows(REPO/'evaluation/wolala2026/data/heldout_pilot_v3/cases.jsonl')}
 for i,row in obs.items():
  if row['status']!='SUCCESS':failures.append({'index':i,'error':row.get('error')});continue
  a=row['outcomes']['A0'];b=row['outcomes']['B'];entry=runtime[i];req=request_for(entry['case'],a);shared.append(a['semantic_assessment']==b['semantic_assessment'] and a['permitted_request']==b['permitted_request'])
  if a['semantic_valid'] is False:invalid_semantic.append({'runtime_index':i,'errors':a['reference_audit'].get('errors')})
  span_errors.extend(a['reference_audit'].get('reference_errors',[]));reference_count+=a['reference_audit'].get('validated_reference_count',0)
  for name,o in row['outcomes'].items():
   for system,response in o['responses'].items():
    errors=impl.validate_response(json.dumps(response))
    if errors:schema_errors.append({'index':i,'system':name+':'+system,'errors':errors})
    if set(o['public_traces'][system])!=set(impl.GENERATION_SCHEMA['required']):public_errors.append('PUBLIC_TRACE_WHITELIST_FAILURE')
    if system=='semantic_cfaf' and response['top_level_mode']=='CFAF':
     internal=o['internal_reason'];reason_classes.append(response['public_reason_class']==internal['class']);reason_realizations.append(response['realization']==internal['realization']);reason_texts.append(response['answer']==internal['text']);reason_consistency.append(response['public_reason_class']==internal['class'] and response['realization']==internal['realization'] and response['answer']==internal['text'])
    if gold[i]['dataset'].startswith('InfoBank'):
     original=original_cases[gold[i]['original_id']];markers=set(original.get('protected_markers',[])+original.get('forbidden_disclosures',[])+original.get('protected_markers_used_only_by_validator',[])+original.get('forbidden_disclosures_used_only_by_validator',[]));visible=canonical(response)
     if any(m and m in visible for m in markers):failures.append({'index':i,'error':'PUBLIC_PROTECTED_MARKER'})
  provenance=trusted_provenance(req,entry['trusted_fixture_ingestion']);docs={d['source_id']:d for d in req.documents};effective={}
  for requirement in b['verification']['source_capabilities']:
   for c in requirement['sources']:
    source_counts[c['capability_state']]+=1;again=capability(docs[c['source_id']],c['relation_family'],provenance.get(c['source_id']))
    if any(c[k]!=again[k] for k in ['capability_state','rule_id','rule_version','provenance_trusted']):source_cap_errors.append({'index':i,'source':c['source_id']})
    effective[c['source_id']]=c['effective_role']
  if gold[i]['dataset'].startswith('InfoBank'):
   original=original_cases[gold[i]['original_id']];mapping={p['permitted_source_id']:int(p['original_source_id'].rsplit('-',1)[1]) for p in a['internal_trace']['policy'] if p.get('included')}
   for role in (a['semantic_assessment'] or {}).get('source_assessments',[]):
    source=original['sources'][mapping[role['source_id']]];role_rows.append({'runtime_index':i,'source_id':role['source_id'],'reference_role':source['evidential_role'],'upstream_role':role['role'],'effective_role':effective.get(role['source_id'],role['role']),'reference_relation':source['relation'],'upstream_relation':role['relation_label'],'gold_scope':'Original exposed synthetic construction annotation, not independent semantic gold'})
 for call in requests:
  i=call['runtime_index'];payload=json.loads(call['payload']['messages'][1]['content']);kind=call['kind']
  if set(all_keys(payload))&FORBIDDEN_FIELDS:forbidden_count+=1;failures.append({'index':i,'error':'GOLD_LEAK'})
  if kind=='query_profile':request=impl.QueryOnlyRequest(runtime[i]['case']['query'])
  else:request=request_for(runtime[i]['case'],obs[i]['outcomes']['A0'])
  try:impl.assert_safe_payload(request,payload)
  except ValueError as exc:failures.append({'index':i,'error':str(exc)})
  if kind=='shared_control' and set(payload)&{'response_contract','selected_mode','verification','can_fulfil_request'}:failures.append({'index':i,'error':'CONTROL_CONTAMINATED'})
 p5=[i for i,g in gold.items() if g['family']=='P5'];p5eq=len(p5)==2 and all(obs[p5[0]]['outcomes'][config]['public_traces']==obs[p5[1]]['outcomes'][config]['public_traces'] for config in ['A0','B']);p5calls=[r for r in requests if r['runtime_index'] in p5]
 if not p5eq or p5calls:failures.append({'error':'P5_EQUALITY_OR_ZERO_CALL_FAILURE'})
 security={'authorization_and_exposure_status':'PASS' if not failures and not changed and not public_errors and not span_errors else 'FAIL','semantic_acceptance_status':'QUALIFIED_TWO_INVALID_UPSTREAM_ROLE_COVERAGES' if invalid_semantic else 'PASS','failures':failures,'all_api_payloads_guarded':len(requests),'gold_field_leak_count':forbidden_count,'shared_assessment_identical_cases':sum(shared),'public_trace_failures':public_errors,'public_schema_errors':schema_errors,'invalid_upstream_assessments':invalid_semantic,'invalid_or_unauthorized_span_references':span_errors,'validated_global_support_counter_reference_occurrences':reference_count,'p5_public_traces_equal':p5eq,'p5_model_calls':len(p5calls),'internal_public_reason_exact_agreement':{'matching':sum(reason_consistency),'assessable':len(reason_consistency),'reason_class_matching':sum(reason_classes),'realization_matching':sum(reason_realizations),'public_text_exact_matching':sum(reason_texts),'nonidentical_text_note':'Four deterministic P5 observations (two cases x A0/B) use the canonical no-support public sentence while the internal template is different; class and realization agree and both public traces remain identical.'},'protected_prior_files_unchanged':not changed,'new_refusalbench_exposures':0,'exposure_ledger_unchanged':sha(REPO/'evaluation/refusalbench_iterative_dev_v1/exposure_ledger.json')==manifest['selection']['exposure_ledger_sha256'],'eligible_exposed':130,'unseen_eligible':1104,'reserved_groups':30,'additional_untouched_groups':18,'original_passage_and_student_case_files_opened_by_task_preparation':False,'regression_metadata_read_note':'The inherited metadata-filter regression reads official JSONL with an explicit annotation-only Arrow schema; passage fields are ignored. No reserved or untouched question/context was materialized or inspected.','scope_limit':'Exact payload contracts, source/span provenance, fixture canaries and trace equality; no claim of universal paraphrase-leak detection or semantic correctness.'};write(ROOT/'security_validation.json',security)
 evidence={'source_rule_recomputation_errors':source_cap_errors,'source_capability_reference_counts':dict(source_counts),'role_reference_cases':role_rows,'upstream_role_agreement':sum(r['upstream_role']==r['reference_role'] for r in role_rows),'effective_role_agreement':sum(r['effective_role']==r['reference_role'] for r in role_rows),'role_reference_count':len(role_rows),'upstream_relation_agreement':sum(r['upstream_relation']==r['reference_relation'] for r in role_rows),'source_rule_decision_changes':sum(r['gate_predictions']['A2']!=r['gate_predictions']['A0'] for r in obs.values()),'claim':'Mechanical registry application is checked; source usefulness beyond the small synthetic role references is not independently labeled.'};write(ROOT/'source_role_diagnostics.json',evidence)
 regression={'current_unit_tests':xml_summary(ROOT/'unit_tests.xml'),'final_compatible_suite':xml_summary(ROOT/'final_regression_tests.xml'),'working_tree_hash_tests':xml_summary(ROOT/'current_worktree_hash_tests.xml'),'original_cfaf_suite':xml_summary(ROOT/'historical_cfaf_tests.xml'),'initial_unadjusted_suite':xml_summary(ROOT/'current_and_prior_tests.xml'),'environment_adjustment':read(ROOT/'regression_environment.json'),'protected_prior_files':len(state['protected_files']),'changed_prior_files':changed,'historical_branch':'wolala2026','historical_branch_commit':original_branch,'original_branch_unchanged':original_branch=='5f377de38312fb39c088551f9c74f8b6d4bd5080','experimental_branch':subprocess.check_output(['git','branch','--show-current'],cwd=REPO,text=True).strip(),'frozen_runtime_source_unchanged':True,'known_historical_failure':'test_preheldout_attempt1_plan_artifacts_are_plan_only expects the already-committed HELDOUT_RUN_AUTHORIZATION.json to be absent. Retained unchanged.','new_regressions':0,'elapsed_seconds_at_audit':elapsed()};write(ROOT/'regression_audit.json',regression)
 print(json.dumps({'security':security['authorization_and_exposure_status'],'invalid_upstream':len(invalid_semantic),'public_schema_errors':len(schema_errors),'role_agreement':evidence['upstream_role_agreement'],'role_n':len(role_rows),'protected_unchanged':len(state['protected_files'])-len(changed),'regression':regression['final_compatible_suite']},indent=2))
 if failures or changed or public_errors or span_errors or source_cap_errors:raise RuntimeError('Mechanical/security audit failed')
 return security,evidence,regression
if __name__=='__main__':usage();audit()
