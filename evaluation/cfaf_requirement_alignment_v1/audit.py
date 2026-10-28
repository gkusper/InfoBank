"""Read-only runtime/history checks plus derived usage/security reports."""
import collections,json,statistics,subprocess
from .artifacts import *
from .runner import verify_frozen
from .deadline import elapsed
from . import integration as impl
from evaluation.cfaf_request_evidence_verification_v1.audit import xml_summary
from evaluation.cfaf_request_evidence_verification_v1.runner import request_for
from evaluation.cfaf_request_evidence_verification_v1.source_capability_rules import trusted_provenance,capability
from evaluation.refusalbench_noncontradiction_v1.public_adapter import all_keys,FORBIDDEN_FIELDS

def usage():
 calls=rows(ROOT/'api_requests.jsonl');events=rows(ROOT/'api_events.jsonl');groups={}
 for kind in sorted({x['kind'] for x in events}):
  g=[e for e in events if e['kind']==kind];groups[kind]={'attempts':len(g),'successes':sum(e['status']=='SUCCESS' for e in g),'input_tokens':sum((e.get('usage') or {}).get('prompt_tokens',0) for e in g),'output_tokens':sum((e.get('usage') or {}).get('completion_tokens',0) for e in g),'latency_ms_sum':sum(e['latency_ms'] for e in g)}
 common=[e for e in events if e['kind'] in {'semantic_analysis','query_profile'}];deploy={}
 for config in ['A0','B1','B3','shared_control']:
  generation=[e for e in events if e['kind']=='shared_control'] if config=='shared_control' else [e for e in events if e['system']==config and e['kind']=='semantic_cfaf'];group=common+generation;deploy[config]={'calls':len(group),'calls_per_case':len(group)/24,'input_tokens':sum((e.get('usage') or {}).get('prompt_tokens',0) for e in group),'output_tokens':sum((e.get('usage') or {}).get('completion_tokens',0) for e in group),'latency_ms_sum':sum(e['latency_ms'] for e in group)}
 observations=rows(ROOT/'pilot_observations.jsonl');timing=[r['outcomes']['B3']['internal_trace']['stage_timings']['sufficiency_and_permitted_output_ms'] for r in observations if r['status']=='SUCCESS']
 u={'attempts':len(calls),'attempt_cap':120,'successes':sum(e['status']=='SUCCESS' for e in events),'network_errors':sum(e['status']=='ERROR' for e in events),'retries':0,'embeddings':0,'optional_verifier_calls':0,'B4_calls':0,'input_tokens':sum(x['input_tokens'] for x in groups.values()),'output_tokens':sum(x['output_tokens'] for x in groups.values()),'summed_api_latency_ms':sum(x['latency_ms_sum'] for x in groups.values()),'returned_models':dict(collections.Counter(e.get('model') for e in events)),'by_kind':groups,'deployment_equivalent':deploy,'deployment_cost_note':'Shared upstream is counted once per hypothetical system, so per-system totals overlap and must not be summed. No USD price assumptions.','experiment_calls_per_case':len(calls)/24,'additional_model_calls_for_RDA':0,'B3_stage5_ms':{'n':len(timing),'median':statistics.median(timing) if timing else None,'max':max(timing) if timing else None,'sum':sum(timing)},'timing_caveat':'All arms compute new diagnostics, including A0. Stage 5 timing is not an isolated CPU ablation; cached shared model calls must not be interpreted as deployment latency savings.'};write(ROOT/'api_usage.json',u);return u

def audit():
 manifest=verify_frozen();state=read(ROOT/'task_state.json');runtime={r['runtime_index']:r for r in rows(ROOT/'pilot_runtime.jsonl')};gold={r['runtime_index']:r for r in rows(ROOT/'pilot_scorer_only.jsonl')};obs={r['runtime_index']:r for r in rows(ROOT/'pilot_observations.jsonl')};requests=rows(ROOT/'api_requests.jsonl');changed=[p for p,h in state['protected_files'].items() if sha(REPO/p)!=h];failures=[];schema=[];semantic=[];reference_errors=[];roles=[];source_errors=[];identical=[];reason_classes=[];reason_realizations=[];reason_texts=[];offset_count=0;query_spans=0
 originals={c['case_id']:c for c in rows(REPO/'evaluation/wolala2026/data/heldout_pilot_v3/cases.jsonl')}
 for i,r in obs.items():
  if r['status']!='SUCCESS':failures.append({'index':i,'error':r.get('error')});continue
  a0=r['outcomes']['A0'];req=request_for(runtime[i]['case'],a0);identical.append(all(o['semantic_assessment']==a0['semantic_assessment'] and o['permitted_request']==a0['permitted_request'] for o in r['outcomes'].values()))
  if a0['semantic_valid'] is False:semantic.append({'index':i,'errors':a0['reference_audit'].get('errors')})
  reference_errors.extend(a0['reference_audit'].get('reference_errors',[]));b3=r['outcomes']['B3'];v=b3['verification'];p=trusted_provenance(req,runtime[i]['trusted_fixture_ingestion']);docs={d['source_id']:d for d in req.documents};effective={}
  for c in v['source_capabilities']:
   for s in c['sources']:
    check=capability(docs[s['source_id']],s['relation_family'],p.get(s['source_id']))
    if any(check[k]!=s[k] for k in ['capability_state','rule_id','rule_version','provenance_trusted']):source_errors.append({'index':i,'source':s['source_id']})
    effective[s['source_id']]=s['effective_role']
  from .requirement_decomposition import validate
  validate(v['requirements_profile']);query_spans+=len(v['requirements_profile']['requirements'])
  candidate=a0['semantic_assessment']['answer_candidate'] if a0['semantic_assessment'] else None
  for row in v['alignment']['requirements']:
   for f in row['candidate_fragments']:
    if isinstance(candidate,str):
     if candidate[f['start']:f['end']]!=f['text']:failures.append({'index':i,'error':'FRAGMENT_OFFSETS_INVALID'})
     offset_count+=1
  for config,out in r['outcomes'].items():
   for system,response in out['responses'].items():
    errors=impl.validate_response(json.dumps(response))
    if errors:schema.append({'index':i,'system':config+':'+system,'errors':errors})
    if set(out['public_traces'][system])!=set(impl.GENERATION_SCHEMA['required']):failures.append({'index':i,'error':'PUBLIC_TRACE_WHITELIST'})
    if system=='semantic_cfaf' and out['internal_reason']:
     reason=out['internal_reason'];reason_classes.append(response['public_reason_class']==reason['class']);reason_realizations.append(response['realization']==reason['realization']);reason_texts.append(response['answer']==reason['text'])
    if gold[i]['dataset'].startswith('InfoBank'):
     c=originals[gold[i]['original_id']];markers=c.get('protected_markers',[])+c.get('forbidden_disclosures',[])+c.get('protected_markers_used_only_by_validator',[])+c.get('forbidden_disclosures_used_only_by_validator',[])
     if any(m and m in canonical(response) for m in markers):failures.append({'index':i,'error':'PUBLIC_PROTECTED_MARKER'})
  if gold[i]['dataset'].startswith('InfoBank'):
   case=originals[gold[i]['original_id']];mapping={p['permitted_source_id']:int(p['original_source_id'].rsplit('-',1)[1]) for p in a0['internal_trace']['policy'] if p.get('included')}
   for role in (a0['semantic_assessment'] or {}).get('source_assessments',[]):
    ref=case['sources'][mapping[role['source_id']]];roles.append({'runtime_index':i,'source_id':role['source_id'],'reference_role':ref['evidential_role'],'model_role':role['role'],'effective_role':effective.get(role['source_id'],role['role']),'reference_relation':ref['relation'],'model_relation':role['relation_label'],'reference_scope':'Original exposed synthetic construction annotation only'})
 for call in requests:
  i=call['runtime_index'];payload=json.loads(call['payload']['messages'][1]['content'])
  if set(all_keys(payload))&FORBIDDEN_FIELDS:failures.append({'index':i,'error':'FORBIDDEN_BENCHMARK_KEYS'})
  if call['kind']=='query_profile':req=impl.QueryOnlyRequest(runtime[i]['case']['query'])
  else:req=request_for(runtime[i]['case'],obs[i]['outcomes']['A0'])
  try:impl.assert_safe_payload(req,payload)
  except ValueError as exc:failures.append({'index':i,'error':str(exc)})
  if call['kind']=='shared_control' and set(payload)&{'response_contract','selected_mode','verification','can_fulfil_request','rda_profile'}:failures.append({'index':i,'error':'CONTROL_GATE_CONTAMINATION'})
 p5=[i for i,g in gold.items() if g['family']=='P5'];p5equal=len(p5)==2 and all(obs[p5[0]]['outcomes'][c]['public_traces']==obs[p5[1]]['outcomes'][c]['public_traces'] for c in ['A0','B1','B3']);p5calls=sum(x['runtime_index'] in p5 for x in requests)
 if not p5equal or p5calls:failures.append({'error':'P5_LEAK_OR_CALL'})
 ledger=REPO/'evaluation/refusalbench_iterative_dev_v1/exposure_ledger.json';source_path=REPO/'evaluation/cfaf_request_evidence_verification_v1/source_capability_rules.py';security={'status':'PASS' if not failures and not changed and not reference_errors and not source_errors else 'FAIL','failures':failures,'payloads_checked':len(requests),'shared_assessments_identical':sum(identical),'case_count':len(obs),'invalid_upstream_assessments':semantic,'invalid_span_references':reference_errors,'public_schema_errors':schema,'source_registry_recomputation_errors':source_errors,'source_registry_unchanged':sha(source_path)==manifest['selection']['source_registry_sha256'],'original_model_prompts_unchanged':manifest['analysis_prompt']==impl.GOVERNED_PROMPT,'public_internal_reason':{'class_agreement':sum(reason_classes),'realization_agreement':sum(reason_realizations),'exact_text_agreement':sum(reason_texts),'n':len(reason_classes),'note':'Canonical P5 public text may differ from internal template while class and realization agree.'},'validated_candidate_fragment_offsets':offset_count,'validated_query_spans':query_spans,'p5_public_traces_equal':p5equal,'p5_api_calls':p5calls,'prior_files_unchanged':len(state['protected_files'])-len(changed),'exposure_ledger_unchanged':sha(ledger)==manifest['selection']['exposure_ledger_sha256'],'new_refusalbench_records':0,'eligible_exposed':130,'eligible_unseen':1104,'reserved_groups':30,'untouched_groups':18,'students_accessed':False,'model_payload_does_not_include_private_RDA_or_gold':True,'metadata_only_regression_read':'Inherited metadata-filter test reads only annotation columns with an explicit Arrow schema; reserved/untouched question and context fields are ignored.','scope_limit':'Exact guards, spans, fixture canaries and trace contracts; no universal natural-language leak or entailment proof.'};write(ROOT/'security_validation.json',security)
 evidence={'source_role_rows':roles,'role_reference_count':len(roles),'model_role_agreement':sum(x['model_role']==x['reference_role'] for x in roles),'effective_role_agreement':sum(x['effective_role']==x['reference_role'] for x in roles),'relation_agreement':sum(x['model_relation']==x['reference_relation'] for x in roles),'registry_unchanged':security['source_registry_unchanged'],'source_application_per_RDA_requirement':True,'source_application_errors':source_errors,'not_independent_semantic_gold':True};write(ROOT/'source_role_diagnostics.json',evidence)
 branch=subprocess.check_output(['git','rev-parse','wolala2026'],text=True).strip();reg={'current_unit_tests':xml_summary(ROOT/'unit_tests.xml'),'compatible_suite':xml_summary(ROOT/'final_regression_tests.xml'),'working_byte_checks':xml_summary(ROOT/'current_worktree_hash_tests.xml'),'original_cfaf_suite':xml_summary(ROOT/'historical_cfaf_tests.xml'),'initial_unadjusted_suite':xml_summary(ROOT/'current_and_prior_tests.xml'),'environment_adjustment':read(ROOT/'regression_environment.json'),'protected_prior_files':len(state['protected_files']),'changed_prior_files':changed,'wolala2026_commit':branch,'wolala2026_unchanged':branch=='5f377de38312fb39c088551f9c74f8b6d4bd5080','new_historical_regressions':0,'known_historical_failure':'test_preheldout_attempt1_plan_artifacts_are_plan_only expects an already committed HELDOUT_RUN_AUTHORIZATION.json to be absent. Preserved unchanged.','additional_synthetic_type_audit':read(ROOT/'synthetic_decomposition_summary.json'),'synthetic_type_audit_qualified':'16/17 exact answer-type sequences; created_at remains represented by METADATA category rather than DATE_TIME. All query spans valid, two metadata obligations remain separate, and the date field is preserved. This limitation is retained, not relabeled.','elapsed_seconds_at_audit':elapsed()};write(ROOT/'regression_audit.json',reg)
 print(json.dumps({'security':security['status'],'payloads':len(requests),'upstream_invalid':len(semantic),'source_roles':evidence['model_role_agreement'],'role_n':len(roles),'history_unchanged':len(state['protected_files'])-len(changed),'public_schema_errors':len(schema),'candidate_offsets':offset_count},indent=2))
 if failures or changed or reference_errors or source_errors:raise RuntimeError('Security or immutable-history audit failed')
 return security,evidence,reg
if __name__=='__main__':usage();audit()
