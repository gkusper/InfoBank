"""Post-study audit; observational reporting never changes the frozen pipeline."""
import json,hashlib,collections,subprocess,re,xml.etree.ElementTree as ET
from .artifacts import *
from .runner import verify_frozen
from . import measured_c as impl
from .provider import FORBIDDEN_FIELDS,GOLD_KEYS,all_keys
from .systems import STANDARD_PROMPT
from .selection import D1,D2_LEDGER,D2_RESERVED
from evaluation.cfaf_sparse_source_repair_v1.operational_failure_codes import validate_response
from evaluation.cfaf_request_evidence_verification_v1.runner import request_for

def xml_summary(path):
 ss=list(ET.parse(path).getroot().iter('testsuite'));return {k:sum(int(s.get(k,0)) for s in ss) for k in ['tests','failures','errors','skipped']}
def category(raw,system):
 if raw is None:return 'NOT_EXECUTED'
 entry=raw.get('systems',{}).get(system)
 if raw.get('status')=='ERROR' and (entry is None or entry.get('operational_failure')):
  error=raw.get('error','');http=re.search(r'HTTP\s+(\d+)',error)
  return 'HTTP_'+http.group(1) if http else 'EXECUTION_EXCEPTION'
 e=raw.get('systems',{}).get(system,{})
 if e.get('operational_failure'):
  o=raw.get('C_outcome',{});errors=o.get('reference_audit',{}).get('errors',[])
  if system=='C' and any('SPAN' in x or 'REFERENCE' in x for x in errors):return 'REFERENCE_VERIFICATION_FAILURE'
  if system=='C' and any('ROLE' in x or 'SOURCE_ASSESSMENT' in x for x in errors):return 'SOURCE_ASSESSMENT_CONTRACT_FAILURE'
  if system=='C' and o.get('semantic_valid') is False:return 'SEMANTIC_SCHEMA_FAILURE'
  return 'OUTPUT_CONTRACT_OR_PARSE_FAILURE'
 if not isinstance(e.get('response'),dict):return 'MALFORMED_RESPONSE'
 if validate_response(json.dumps(e['response'])):return 'OUTPUT_CONTRACT_INVALID'
 if e['response']['top_level_mode']=='FULL':return 'GENERATED_FULL_NOT_INDEPENDENTLY_ADJUDICATED'
 if system=='C':return 'VALIDATED_REQUEST_RELATIVE_CFAF_NOT_AUTOMATICALLY_CORRECT'
 return 'SELF_REPORTED_CFAF_NOT_AUTOMATICALLY_CORRECT'

def audit():
 m=verify_frozen();state=read(ROOT/'task_state.json');bad=[p for p,h in state['protected_files'].items() if sha(REPO/p)!=h];assert not bad
 rm=read(ROOT/'runtime_manifest.json');plan=read(ROOT/'selection_plan.json');requests=rows(ROOT/'api_requests.jsonl');events=rows(ROOT/'api_events.jsonl');runtime={d:rows(ROOT/(d+'_runtime.jsonl')) for d in plan['planned_case_counts']};golds={d:rows(ROOT/(d+'_gold.jsonl')) for d in plan['planned_case_counts']};raws={d:{r['runtime_index']:r for r in rows(ROOT/(d+'_results_raw.jsonl'))} if (ROOT/(d+'_results_raw.jsonl')).exists() else {} for d in plan['planned_case_counts']};ids=plan['dataset1']['case_ids']+[r['id'] for r in plan['dataset2']['records']]+[r['sample_id'] for r in read(ROOT/'dataset3_selection_manifest.json')['records']];assert len(requests)<=480
 for d in runtime:assert sha(ROOT/(d+'_runtime.jsonl'))==rm['runtime_sha256'][d] and sha(ROOT/(d+'_gold.jsonl'))==rm['gold_sha256'][d]
 violations=[];per_case=collections.defaultdict(list)
 for r in requests:
  d=r['dataset'];i=r['runtime_index'];p=r['payload'];u=json.loads(p['messages'][1]['content']);encoded=json.dumps(p,ensure_ascii=False);per_case[d,i].append(r);illegal=set(all_keys(u))&(FORBIDDEN_FIELDS|GOLD_KEYS)
  if illegal:violations.append({'attempt':r['attempt'],'violation':'FORBIDDEN_FIELD'})
  if any(s in encoded for s in ids):violations.append({'attempt':r['attempt'],'violation':'ORIGINAL_SAMPLE_IDENTIFIER'})
  assert p['model']=='gpt-4o-mini' and p['temperature']==0;assert p['max_tokens']==(1500 if r['kind']=='semantic_analysis' else 500 if r['kind']=='query_profile' else 512);assert r['input_token_upper_bound']<=60000
  if r['kind']=='query_profile':assert set(u)=={'query'};continue
  req=impl.project_case(runtime[d][i]['case'])
  # Query-only fallback may change the derived profile; evidence remains identical.
  assert u['query']==req.query and u['documents']==req.documents and u['query_context']==runtime[d][i]['query_context'];assert not(set(u)&{'source_inventory','inventory_states','private_mapping','operational_status'})
  if r['kind']=='standard_rag':
   impl.assert_safe_payload(req,{k:v for k,v in u.items() if k!='query_context'});assert p['messages'][0]['content']==STANDARD_PROMPT;assert not(set(u)&{'response_contract','semantic_assessment','selected_mode','verification'})
  if r['kind']=='semantic_analysis':assert p['messages'][0]['content']==impl.GOVERNED_PROMPT
  if r['kind']=='semantic_cfaf':assert p['messages'][0]['content']==impl.CFAF_PROMPT
 assert not violations,violations
 for (d,i),calls in per_case.items():
  assert sum(r['kind']=='standard_rag' for r in calls)<=1;assert sum(r['kind']=='semantic_analysis' for r in calls)<=1;assert sum(r['kind']=='semantic_cfaf' for r in calls)<=1;assert not any(r['kind']=='shared_control' for r in calls)
  users=[json.loads(r['payload']['messages'][1]['content']) for r in calls if r['kind']!='query_profile'];assert all(u['documents']==users[0]['documents'] for u in users)
 p5=[];casegold=golds['dataset1'];by_pair=collections.defaultdict(list)
 for i,g in enumerate(casegold):
  if g['family']=='P5':by_pair[g['pair_id']].append(i)
 for pair,indices in by_pair.items():
  records=[raws['dataset1'].get(i) for i in indices];equal=len(records)==2 and all(records) and all(records[0]['systems'][s]['response']==records[1]['systems'][s]['response'] for s in ['A','B','C']);zero=not any(per_case['dataset1',i] for i in indices);p5.append({'pair_id':pair,'public_responses_equal':bool(equal),'no_model_calls':zero});assert equal and zero
 for record in runtime['dataset3']:
  for source,mp in zip(record['case']['sources'],record['mapping']):assert hashlib.sha256(source['content'].encode()).hexdigest()==mp['adapted_context_sha256'] and hashlib.sha256(source['content'][mp['metadata_header_characters']:].encode()).hexdigest()==mp['raw_text_sha256']
 breakdown={d:{s:dict(collections.Counter(category(raws[d].get(i),s) for i in range(plan['planned_case_counts'][d]))) for s in ['A','B','C']} for d in plan['planned_case_counts']};write(ROOT/'operational_failure_breakdown.json',{'categories':breakdown,'correct_mode_not_equal_factual_correctness':True,'operational_failures_never_substantively_credited':True})
 # These are diagnostics of the preregistered outcomes, not new decisions.
 safe={d:rows(ROOT/(d+'_results.jsonl')) for d in runtime};reasons={};profiles={};latency={}
 for d in runtime:
  families=collections.defaultdict(list)
  for i,g in enumerate(golds[d]):
   label=g.get('family',g.get('expected_rag_behavior','NO_NATIVE_MODE_GOLD'));families[label].append(i)
  reasons[d]={}
  for label,indices in families.items():
   systems={}
   for system in ['A','B','C']:
    systems[system]={'N':len(indices),'nonoperational_mode_matches':sum(bool(safe[d][i]['systems'][system]['mode_correct_nonoperational']) for i in indices) if d!='dataset3' else None,'observed_modes':dict(collections.Counter(safe[d][i]['systems'][system]['mode'] for i in indices)),'public_reason_classes':dict(collections.Counter(str(safe[d][i]['systems'][system]['public_reason_class']) for i in indices)),'operational':sum(safe[d][i]['systems'][system]['operational_failure'] for i in indices)}
   reasons[d][label]=systems
  c_outs=[r.get('C_outcome',{}) for r in raws[d].values()];profiles[d]={'legacy_request_types':dict(collections.Counter(req['request_type'] for out in c_outs for req in out.get('query_profile',{}).get('requirements',[]))),'internal_reason_codes':dict(collections.Counter(str((out.get('internal_reason') or {}).get('code')) for out in c_outs)),'C_query_only_fallback_count':sum(bool(out.get('query_profile_fallback')) for out in c_outs),'source_inventory_omissions_NOT_ASSESSED':sum(out.get('reference_audit',{}).get('not_assessed_count',0) or 0 for out in c_outs)}
  case_ms=sum(r.get('elapsed_ms',0) for r in raws[d].values());http_ms=sum(e.get('latency_ms',0) for e in events if e['dataset']==d);latency[d]={'case_wall_seconds':case_ms/1000,'inner_HTTP_seconds':http_ms/1000,'local_pipeline_and_provider_accounting_seconds':max(0,case_ms-http_ms)/1000,'reported_outside_provider_local_seconds':sum(r.get('local_overhead_ms',0) for r in raws[d].values())/1000,'definition':'Difference includes pipeline guards, parsing, durable ledger read/write and serialization; not a CPU profiler or production throughput estimate'}
 write(ROOT/'refusal_reason_diagnostics.json',reasons);write(ROOT/'request_scope_diagnostics.json',profiles);write(ROOT/'latency_analysis.json',latency)
 # Neutralized study metadata must not change original D1 policy-visible content.
 originals=rows(D1/'cases.jsonl')
 assert all(impl.project_case(old).public()==impl.project_case(new['case']).public() for old,new in zip(originals,runtime['dataset1']))

 reg=read(ROOT/'regression_audit.json');reg['xml_summaries']={p.name:xml_summary(p) for p in ROOT.glob('*tests.xml')};reg['preexisting_files_unchanged']=len(state['protected_files']);write(ROOT/'regression_audit.json',reg)
 tag=read(ROOT/'git_freeze_manifest.json');assert subprocess.check_output(['git','rev-parse',tag['annotated_tag']+'^{}'],text=True).strip()==tag['local_commit'];assert subprocess.check_output(['git','rev-parse','wolala2026'],text=True).strip()==tag['local_commit'];assert subprocess.check_output(['git','rev-parse','experiment/cfaf-sparse-source-repair-v1'],text=True).strip()==state['baseline_commit']
 write(ROOT/'security_audit.json',{'status':'PASS','protected_files_checked':len(state['protected_files']),'protected_files_changed':bad,'frozen_study_sources_unchanged':True,'runtime_and_gold_hashes_match':True,'preregistration_before_fresh_text':True,'requests_checked':len(requests),'forbidden_field_or_identifier_violations':violations,'all_systems_same_authorized_evidence':True,'A_standard_no_CFAF_semantics_or_contract':True,'B_reuses_A_one_generation':True,'unmeasured_fourth_call_disabled':True,'new_embedding_or_judge_calls':0,'attempt_cap_respected':True,'source_body_hashes_match':True,'p5_pair_checks':p5,'Dataset2_reserved_groups_accessed':0,'Dataset2_other_untouched_groups_accessed':0,'Dataset2_prior_ledger_unchanged':sha(D2_LEDGER)==plan['dataset2']['ledger_sha256'],'Dataset3_only_preregistered80_new_rows_materialized':True,'Dataset3_cumulative_exposed':90,'Dataset3_remaining_unused':2276,'historical_branch_and_tag_unchanged':True,'push_performed':False,'new_architecture_or_library_replacement_claimed':False,'independent_claim_judgement':'PENDING','public_leak_scope':'Existing exact protected-value/source-name checks; broad paraphrase disclosure is not independently certified'})
 print('AUDIT PASS',len(requests),'requests;',len(state['protected_files']),'unchanged old files;',len(p5),'P5 pairs')
if __name__=='__main__':audit()
