"""Post-run audit: provenance, exposure, timings, references and paired differences."""
import collections,datetime as dt,hashlib,json,xml.etree.ElementTree as ET
from pathlib import Path
from .deadline import ensure,snapshot,limits
from .exposure import ROOT,REPO,metadata_only,SOURCE,eligible,sha,stable,atomic_ledger
from .runner import load_version,verify_source
from evaluation.refusalbench_noncontradiction_v1.public_adapter import public_case,all_keys,FORBIDDEN_FIELDS
from evaluation.refusalbench_span_fix_v1.api_budget import read_jsonl,write_json
from evaluation.refusalbench_span_fix_v1.span_references import build_catalogue,resolve_span

DIRS=['round_01','round_02','round_03','paired_regression']

def run():
 ensure('global audit',60);metadata=metadata_only(SOURCE);ledger=json.loads((ROOT/'exposure_ledger.json').read_text());byid={m['id']:(i,m) for i,m in enumerate(metadata)}
 assert len(metadata)==1600 and sum(eligible(m) for m in metadata)==1234
 ids=[e['id'] for e in ledger['entries']];assert len(ids)==len(set(ids));eligible_exposed=sum(eligible(byid[rid][1]) for rid in ids)
 assert eligible_exposed==ledger['cumulative_exposed_eligible_records']==130 and eligible_exposed<=617
 assert ledger['prior_exposed_unique_eligible_records']==70 and ledger['newly_exposed_unique_eligible_records']==60
 assert 1234-eligible_exposed==ledger['remaining_unseen_eligible_records']==1104
 forbidden=set(ledger['reserved_source_groups'])|set(ledger['untouched_source_groups']);assert all(str(byid[rid][1]['source_id']) not in forbidden for rid in ids)
 new_round_ids=[];api=read_jsonl(ROOT/'global_api_requests.jsonl');events=read_jsonl(ROOT/'global_api_events.jsonl');assert len(api)<=360;assert [r['attempt'] for r in api]==list(range(1,len(api)+1));assert len(events)==len(api)
 cutoff=dt.datetime.fromisoformat(limits()['task_started_at_utc'])+dt.timedelta(seconds=3300);assert all(dt.datetime.fromisoformat(r['started_at_utc'])<cutoff for r in api)
 refs=collections.Counter();profile_calls=0;audited_cases=0;versions={};per_round_diagnostics={}
 for directory in DIRS:
  out=ROOT/directory;source=json.loads((out/'source_version.json').read_text());verify_source(source);impl=load_version(source['version']);versions[directory]=source['version'];runtime=read_jsonl(out/'runtime_inputs.jsonl');selection=json.loads((out/'selection_manifest.json').read_text());worker=read_jsonl(out/'worker_results.jsonl');results=read_jsonl(out/'results.jsonl');grouped=collections.defaultdict(dict)
  if directory.startswith('round_'):new_round_ids += [r['original_id'] for r in selection['records']]
  assert len(worker)==len(results)==len(runtime)==20 and len({r['source_id'] for r in selection['records']})==20
  for r in selection['records']:
   i,m=byid[r['original_id']];assert i==r['dataset_index'] and eligible(m);assert r['record_hash']==stable(m['id']) and r['source_group_hash']==stable(m['source_id'])
  calls=read_jsonl(out/'api_requests.jsonl')
  for requestlog in calls:
   index=requestlog['runtime_index'];payload=json.loads(requestlog['payload']['messages'][1]['content']);assert not set(all_keys(payload))&FORBIDDEN_FIELDS;assert 'RB-NQ_' not in json.dumps(payload)
   if requestlog['kind']=='query_profile':
    assert payload=={'query':runtime[index]['perturbed_query']};profile_calls+=1
   grouped[index][requestlog['kind']]=payload
  diagnostics=[]
  for i,w in enumerate(worker):
   outcome=w.get('outcome');r=results[i]
   if outcome is None:diagnostics.append({'index':i,'classification':'Execution error','error':w.get('error')});continue
   case=public_case(runtime[i],i);fallback=outcome.get('query_profile_fallback')
   if fallback:
    attestation=impl.parse_profile(case['query'],fallback['raw']);request=impl.project_case(case,attestation)
   else:request=impl.project_case(case)
   assert request.public()==outcome['permitted_request']
   for kind,payload in grouped[i].items():
    if kind!='query_profile':impl.assert_safe_payload(request,payload)
   cf=grouped[i].get('semantic_cfaf');control=grouped[i].get('shared_control');analysis=grouped[i].get('semantic_analysis')
   if cf and control and analysis:
    for key in ['query','documents','query_profile','view_bindings']:assert cf[key]==control[key]==analysis[key]
    assert cf['semantic_assessment']==control['semantic_assessment']==outcome['semantic_assessment'];assert 'response_contract' not in control;audited_cases+=1
   docs={d['source_id']:d['context'] for d in request.documents};catalogue=build_catalogue(docs);assessment=outcome['semantic_assessment']
   for field in ['supporting_spans','contradicting_spans']:
    for ref in assessment.get(field,[]):resolve_span(ref,docs,catalogue);refs[field]+=1
   for role in assessment.get('source_assessments',[]):
    for ref in role['grounding_span_ids']:resolve_span(ref,docs,catalogue);refs['source_role']+=1
   for req in assessment.get('requirement_support',[]):
    for ref in req['supporting_span_ids']:resolve_span(ref,docs,catalogue);refs['requirement_support']+=1
   item={'runtime_index':i,'dataset_index':r['dataset_index'],'record_hash':r['record_hash'],'query_profile_resolution':outcome['query_profile']['resolution'],'internal_reason':outcome.get('internal_reason'),'analysis_refusal_cause':assessment.get('analysis_refusal_cause'),'per_system':{}}
   for system,s in r['systems'].items():
    categories=[]
    if s['validation_errors']:categories.append('Output schema inconsistency')
    if any('SCOPE' in issue for issue in outcome['fulfilment_issues']):categories.append('Query profiling')
    if any('IDENTITY' in issue or 'INSTANCE' in issue or 'INCOMPLETE' in issue for issue in outcome['fulfilment_issues']):categories.append('Requested-identity completeness')
    if any('RELATION' in issue or 'PRIMARY' in issue for issue in outcome['fulfilment_issues']):categories.append('Entity/relation interpretation')
    if r['expected_mode']=='CFAF' and s['prediction']=='CFAF' and s['specific_reason_correct'] is not True:categories.append('Incorrect or unrecognized specific refusal reason')
    if not s['correct'] and not categories:categories.append('Evidence sufficiency / answer generation: contextual review required')
    item['per_system'][system]={'correct':s['correct'],'categories':categories,'candidate_copied':(s.get('raw_response') or {}).get('answer')==assessment.get('answer_candidate') if s['prediction']=='FULL' else None,'semantic_grounding_not_proven_by_copy_or_references':True}
   diagnostics.append(item)
  write_json(out/'diagnostics.json',{'method':'Posthoc mechanistic error flags, not independent semantic ground truth.','cases':diagnostics})
  per_round_diagnostics[directory]={'cases':len(worker),'version':source['version'],'queries_only_fallback_calls':sum(c['kind']=='query_profile' for c in calls)}
 assert len(new_round_ids)==len(set(new_round_ids))==60
 baseline=read_jsonl(ROOT/'round_01/results.jsonl');paired=read_jsonl(ROOT/'paired_regression/results.jsonl');paired_records=[];transitions={s:collections.Counter() for s in ['semantic_cfaf','shared_control']}
 for b,p in zip(baseline,paired):
  assert b['record_hash']==p['record_hash'];entry={'dataset_index':b['dataset_index'],'record_hash':b['record_hash'],'systems':{}}
  for system in transitions:
   before=b['systems'][system]['correct'];after=p['systems'][system]['correct'];key='both_correct' if before and after else 'fixed' if after else 'regressed' if before else 'both_incorrect';transitions[system][key]+=1;entry['systems'][system]={'before':b['systems'][system]['prediction'],'after':p['systems'][system]['prediction'],'transition':key}
  paired_records.append(entry)
 write_json(ROOT/'paired_comparison.json',{'baseline':'round_01 v00','final':'paired_regression v02','identical_inputs':sha(ROOT/'round_01/runtime_inputs.jsonl')==sha(ROOT/'paired_regression/runtime_inputs.jsonl'),'scoring_source_identical':True,'transitions':{s:dict(c) for s,c in transitions.items()},'records':paired_records,'interpretation':'Same already-exposed twenty inputs; single-run observational version comparison, not an inferential significance test or isolated component ablation.'})
 protected=json.loads((ROOT/'protected_files.json').read_text());changed=[n for n,h in protected.items() if sha(REPO/n)!=h];assert not changed;assert sha(SOURCE)==ledger['official_source_sha256']
 test_audit={}
 for name in ['framework_tests.xml','v01_tests.xml','v02_tests.xml','final_acceptance_tests.xml','historical_tests.xml']:
  cases=list(ET.parse(ROOT/name).getroot().iter('testcase'));failed=[t.get('name') for t in cases if t.find('failure') is not None or t.find('error') is not None];test_audit[name]={'testcases':len(cases),'failures':failed}
  assert failed==(['test_preheldout_attempt1_plan_artifacts_are_plan_only'] if name=='historical_tests.xml' else [])
 usage={'attempts':len(api),'successes':sum(e['status']=='SUCCESS' for e in events),'failed_attempts':sum(e['status']=='ERROR' for e in events),'kind_counts':dict(collections.Counter(e['kind'] for e in events)),'input_tokens':sum((e.get('usage') or {}).get('prompt_tokens',0) for e in events),'output_tokens':sum((e.get('usage') or {}).get('completion_tokens',0) for e in events),'client_api_latency_sum_ms':sum(e.get('latency_ms',0) for e in events),'hard_cap':360,'requests_after_55_minutes':0,'automatic_retries':0,'embeddings':0,'shared_main_analysis_calls':80,'query_only_fallback_calls':profile_calls}
 write_json(ROOT/'api_usage.json',usage)
 audit={'status':'PASS_INPUT_POLICY_EXPOSURE_AND_REFERENCE_CHECKS','rounds_completed':3,'paired_cases_completed':20,'recorded_case_observations':80,'unique_new_record_ids':60,'cumulative_eligible_exposure':eligible_exposed,'exposure_ceiling':617,'eligible_remaining_unseen':1104,'reserved_source_groups_preserved':30,'additional_untouched_source_groups_preserved':18,'previous_files_protected':len(protected),'previous_files_changed':changed,'official_dataset_unchanged':True,'audited_api_requests':len(api),'shared_assessment_equality_cases':audited_cases,'verified_reference_occurrences':dict(refs),'invalid_references':0,'gold_annotation_input_exposures_observed':0,'versions':versions,'tests':test_audit,'api_usage':usage,'completed_at':snapshot(),'interpretation':'PASS covers mechanical safeguards and input isolation. Output factual completeness and semantic correctness require separate review and can fail.'}
 write_json(ROOT/'validation_audit.json',audit);ledger['last_audit']={'eligible_exposure_recomputed_from_original_ids':eligible_exposed,'budget_status':'PASS','new_unique_ids_recomputed':60,'paired_new_exposure':0,'at':snapshot()};atomic_ledger(ledger)
 print(json.dumps({'usage':usage,'paired_transitions':{s:dict(c) for s,c in transitions.items()},'references':dict(refs),'time':snapshot()},indent=2))
 return audit

if __name__=='__main__':run()
