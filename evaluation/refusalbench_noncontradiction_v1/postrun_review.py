"""Non-independent post-run contextual review; no primary labels/predictions edited."""
import collections,hashlib,json,re
from pathlib import Path
from evaluation.refusalbench_span_fix_v1.api_budget import read_jsonl,write_json
from evaluation.refusalbench_span_fix_v1.span_references import build_catalogue,resolve_span
from .execute import ROOT,REPO,freeze_hashes
from .public_adapter import public_case
from evaluation.infobank_semantic_integration_v2.metadata_binding import project_case,assert_safe_payload

# Written after viewing actual query/context and raw results. These are agent
# judgments, not blinded human annotations, benchmark gold or model-judge calls.
NOTES={
0:('Nonfactual best-experience judgment has no criteria or opinions in the passage. Both refusals are defensible. CFAF gives a generic unresolved-target explanation instead of the subjective cause; control describes the missing evaluation. Control declares CFAF with fulfilment_status FULL.', ['query interpretation','incorrect CFAF reason','output semantic consistency'],False),
1:('Official ANSWER permits bridging from a named cast member to a particular role. The passage names David Tennant but does not attach him to Scrooge. CFAF is wrong under the official label, blocked by unresolved scope and an UNESTABLISHED premise despite SUFFICIENT support. Control matches the official label but the actor-to-role link is not established by this passage alone.', ['query interpretation','evidence sufficiency','benchmark ambiguity'],True),
2:('The CO2 average request is resolved as AGGREGATE_AVERAGE, but the passage is about Vikings release dates. Both correctly restrict. Public explanations identify missing relevance rather than the official granularity category; this is not a global average inferable from local data in the supplied text.', ['evidence sufficiency','incorrect CFAF reason','benchmark category breadth'],True),
3:('Matthew and Luke are explicitly identified. REQUEST_SCOPE_UNRESOLVED is the sole CFAF blocker, so this is a clear unnecessary refusal caused by query profiling. Control answers the two gospels directly and completely.', ['query interpretation'],False),
4:('The hypothetical cultural impact is not established by historical Sinterklaas facts. Both restrict. The semantic analyzer and CFAF explanation collapse counterfactual/nonfactual status into generic missing evidence; control explains why the hypothetical impact is unavailable.', ['query interpretation','incorrect CFAF reason'],False),
5:('The passage replaces the winner name with an unnamed top-seeded player. The analyzer nevertheless marks support SUFFICIENT and proposes that same placeholder as an answer to who. CFAF restricts because scope is unresolved, not because the missing identity was correctly detected. Control copies the supported description as FULL but leaves the requested identity unanswered.', ['evidence sufficiency','incomplete FULL response','query interpretation'],False),
6:('The passage distributes Dylan/Harrison/Petty/Lynne/Orbison across a recording narrative. Both refusals are official errors, with unresolved scope and a semantic demand for an explicit member list. Control then provides all five full names explicitly based on general knowledge, violating the supplied-context boundary and undermining its CFAF declaration. The passage contains the surnames, but does not establish all expanded names.', ['query interpretation','evidence sufficiency','unsupported added answer','contract/prose disagreement'],False),
7:('A cultural-centre membership list does not explicitly designate one state as geographically central. Official ANSWER preserves Madhya Pradesh/Chhattisgarh from earlier answer annotations; both refusals remain official errors. The analyzer missing-support judgment is defensible for the actual passage. Control adds that Madhya Pradesh is often considered central, an assertion absent from the passage.', ['evidence sufficiency','benchmark ambiguity','unsupported added answer'],True),
8:('The passage directly attaches Paul Hogan to Mick Dundee. The sole CFAF blocker is REQUEST_SCOPE_UNRESOLVED. Control gives a supported complete FULL answer. This is a clear profiling failure, not missing evidence.', ['query interpretation'],False),
9:('The actual query requests a specific example; the passage only defines the general term substitute good. Official ANSWER reasoning treats the genus term as a valid species/example answer. Both refusals are official errors, but their missing-example judgment is defensible. No new example is invented to improve the score.', ['query interpretation','evidence sufficiency','benchmark ambiguity'],True),
10:('The married-bachelor premise is logically incompatible with the ordinary meaning of bachelor. Both correctly restrict, but the analyzer and public explanations treat it as an unrecorded relationship rather than identify the false premise. This is a query-premise issue retained by the exact filter, not an internal passage-contradiction experiment.', ['query interpretation','incorrect CFAF reason'],False),
11:('One 1966 appearance cannot establish a whole-decade trend. Both correctly restrict; control explains that specific coverage gap. The inherited lexical reason recognizer does not recognize this paraphrase as the granularity category, so its automated unknown is not proof the prose is wrong.', ['evidence sufficiency','reason recognizer limitation'],False),
12:('Lori McKenna is explicitly named as writer. REQUEST_SCOPE_UNRESOLVED is the sole CFAF blocker. Control provides a supported complete answer. This is the third clear sole-profiler unnecessary refusal.', ['query interpretation'],False),
13:('The passage attributes movable-type press introduction to Gutenberg but says nothing about printing a second book. Both correctly restrict under the official false-premise label. Missing evidence does not by itself establish that the second-book premise is false; the official explanation also refers to a first-book statement absent from the perturbed passage.', ['query interpretation','incorrect CFAF reason','benchmark ambiguity'],True),
14:('Two different named songs make this song unresolved. Both correctly restrict; control gives both songwriter alternatives and explicitly states ambiguity, the only recognized correct specific refusal category. Its CFAF plus fulfilment_status FULL is internally inconsistent even though its cautious prose can be appropriate.', ['query interpretation','output semantic consistency'],False),
15:('The passage gives 1940s availability and 1920s experimental vaccine development, which are different milestones rather than necessarily conflicting facts. Both refusals are official errors. The analyzer demands a specific vaccination start date; a qualified availability answer could satisfy the intended benchmark reading, while the first-vaccination interpretation remains uncertain.', ['query interpretation','evidence sufficiency','benchmark ambiguity'],True),
16:('Both city names are replaced by placeholders. Both correctly restrict rather than supply an identity from world knowledge. Control explicitly says the first city is not specified; the lexical category recognizer misses that missing-information paraphrase. CFAF remains generic.', ['evidence sufficiency','reason recognizer limitation'],False),
17:('The passage names the Ark as the described container of the tablets. Both refusals are official errors because the analyzer adds a current geographical-location requirement not explicit in the query. Container versus current-location readings create legitimate interpretive uncertainty; an answer qualified to the biblical description was possible.', ['query interpretation','evidence sufficiency','benchmark ambiguity'],True),
18:('The passage directly attaches Joe Spano to John Clark Sr and adds a different actor with the same printed name in another role. Official REFUSE_AMBIGUOUS is retained. CFAF matches it because scope is unresolved although the assessment is SUFFICIENT; control FULL is an official failure to restrict but is textually supported under a name-only interpretation. Unique-person disambiguation could require more evidence.', ['query interpretation','benchmark ambiguity'],True),
19:('A factory foothold in 1611 and rights in 1612 do not establish when political control of India began. Both refusals are official errors under ANSWER, but the missing-control-date judgment is faithful to the actual passage. Control also declares CFAF with fulfilment_status FULL. No external historical date is supplied.', ['query interpretation','evidence sufficiency','benchmark ambiguity','output semantic consistency'],True),
}


def run():
 records=read_jsonl(ROOT/'results.jsonl');cases=read_jsonl(ROOT/'selected_cases.jsonl');worker=read_jsonl(ROOT/'worker_results.jsonl');runtime=read_jsonl(ROOT/'runtime_inputs.jsonl');requests=read_jsonl(ROOT/'api_requests.jsonl');protocol=json.loads((ROOT/'prerun_protocol.json').read_text())
 assert protocol['code_sha256']==freeze_hashes()
 byrequest=collections.defaultdict(dict);refcounts=collections.Counter();unresolved=0;sole_profile=[];generic_profile=[];contract_errors=[];raw_prose=[];external_cases=[];reviews=[]
 for requestlog in requests:
  index=requestlog['runtime_index'];req=project_case(public_case(runtime[index],index));payload=json.loads(requestlog['payload']['messages'][1]['content']);assert_safe_payload(req,payload);byrequest[index][requestlog['kind']]=payload
  assert requestlog['pre_call_policy_validation']=='PASS'
 for i,(record,w,case) in enumerate(zip(records,worker,cases)):
  outcome=w['outcome'];assert outcome is not None;req=project_case(public_case(runtime[i],i));calls=byrequest[i]
  for k in ['query','documents','query_profile','view_bindings']:assert calls['semantic_analysis'][k]==calls['semantic_cfaf'][k]==calls['shared_control'][k]
  assert calls['semantic_cfaf']['semantic_assessment']==calls['shared_control']['semantic_assessment']==outcome['semantic_assessment'];assert 'response_contract' not in calls['shared_control']
  assert not any(b['binding_status']=='TRUSTED_QUERY_TARGET' for b in req.view_bindings)
  docs={d['source_id']:d['context'] for d in req.documents};cat=build_catalogue(docs);a=outcome['semantic_assessment']
  for field in ['supporting_spans','contradicting_spans']:
   for ref in a[field]:resolve_span(ref,docs,cat);refcounts[field]+=1
  for role in a['source_assessments']:
   for ref in role['grounding_span_ids']:resolve_span(ref,docs,cat);refcounts['source_role']+=1
  for requirement in a['requirement_support']:
   for ref in requirement['supporting_span_ids']:resolve_span(ref,docs,cat);refcounts['requirement_support']+=1
  unresolved+=outcome['query_profile']['resolution']=='UNRESOLVED'
  if record['expected_mode']=='FULL' and 'REQUEST_SCOPE_UNRESOLVED' in outcome['fulfilment_issues']:generic_profile.append(i)
  if record['expected_mode']=='FULL' and outcome['fulfilment_issues']==['REQUEST_SCOPE_UNRESOLVED']:sole_profile.append(i)
  note,origins,questionable=NOTES[i];per={}
  for system in ['semantic_cfaf','shared_control']:
   r=record['systems'][system]['response'];field_error=r['top_level_mode']=='CFAF' and r['fulfilment_status']=='FULL'
   if field_error:contract_errors.append({'index':i,'system':system,'mode':r['top_level_mode'],'fulfilment_status':r['fulfilment_status']})
   supported=None;complete=None;agreement=True;quality='Generic/non-specific unresolved-target explanation.' if system=='semantic_cfaf' else 'Context-specific explanation; see case note; lexical category recognition is separate.'
   if system=='shared_control':
    if i in [3,8,12,18]:supported=True;complete=True
    elif i==1:supported=False;complete=None
    elif i==5:supported=True;complete=False
    elif i in [6,7]:supported=False;external_cases.append(i);agreement=False if i==6 else True
   if system=='shared_control' and i==6:raw_prose.append({'index':i,'system':system,'issue':'CFAF response supplies requested artist list using explicitly invoked general knowledge.'})
   if record['expected_mode']=='FULL' and r['top_level_mode']=='CFAF':quality+=' Unnecessary refusal under unchanged official label.'
   per[system]={'answer_supported_by_supplied_context':supported,'complete_fulfilment':complete,'mode_prose_agreement_agent_review':agreement,'contract_field_disagreement':field_error,'explanation_quality':quality,'human_review_required':True}
  reviews.append({'runtime_index':i,'original_id':case['id'],'review_provenance':'Post-run report-author agent, unblinded, non-independent; no extra API judge; official labels and predictions unchanged.','note':note,'error_attribution':origins,'benchmark_interpretation_concern':questionable,'systems':per})
 (ROOT/'postrun_reviews.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=True,sort_keys=True)+'\n' for r in reviews),encoding='utf-8')
 protected=json.loads((ROOT/'protected_files.json').read_text());changed=[n for n,h in protected.items() if hashlib.sha256((REPO/n).read_bytes()).hexdigest()!=h];assert not changed
 audit={'status':'PASS','previous_files_protected':len(protected),'previous_files_changed':changed,'frozen_code_unchanged':True,'live_api_requests_audited':len(requests),'shared_assessment_equal_cases':20,'unpermitted_metadata_bindings_invented':0,'gold_annotation_exposure_observed':0,'verified_reference_occurrences':dict(refcounts),'reference_validation_failures':0,'query_profile_UNRESOLVED_cases':unresolved,'official_FULL_errors_with_scope_unresolved':generic_profile,'official_FULL_errors_solely_scope_unresolved':sole_profile,'schema_failures':0,'model_output_field_inconsistencies':contract_errors,'context_only_violations_report_author_observed':external_cases,'mode_prose_disagreements_report_author_observed':raw_prose,'reserved_or_untouched_source_groups_executed':0,'no_contradiction_improvements':True,'review_limit':'Exact input/data-flow checks are mechanistic; support/completeness and benchmark interpretation notes are non-independent agent judgments.'}
 write_json(ROOT/'validation_audit.json',audit)
 summary=json.loads((ROOT/'summary.json').read_text());summary['posthoc_contextual_review']={'provenance':'Non-independent unblinded report-author agent; not primary rescoring or independent human ground truth','CFAF_generated_FULL':0,'shared_generated_FULL':6,'shared_supported_complete_FULL_agent_judged':4,'shared_unsupported_FULL_agent_judged':1,'shared_supported_but_incomplete_FULL_agent_judged':1,'CFAF_specific_reason_coverage_of_ten_gold_CFAF':0,'shared_specific_reason_coverage_of_ten_gold_CFAF':.1,'generic_or_unrecognized_gold_CFAF_reasons':{'semantic_cfaf':10,'shared_control':9},'contract_field_inconsistencies':contract_errors,'source_boundary_violations_in_CFAF_text':external_cases,'benchmark_interpretation_concerns':[r['runtime_index'] for r in reviews if r['benchmark_interpretation_concern']],'scope_UNRESOLVED_cases':unresolved,'sole_profiler_false_refusal_indices':sole_profile}
 write_json(ROOT/'summary.json',summary)
 case_report(records,cases,reviews)
 print(json.dumps({'audit':audit,'posthoc_review':summary['posthoc_contextual_review']},indent=2))


def cell(x):return str(x).replace('|','\\|').replace('\n',' ')
def case_report(records,cases,reviews):
 lines=['# Case-level RefusalBench filtered pilot analysis','','All indices below are zero-based. Official labels remain unchanged. Post-run agent review is unblinded and non-independent; it never changes primary accuracy or turns questionable labels into errors/fixes. No extra judge API calls were made.','','| Index | Official behavior | CFAF prediction / correct | Control prediction / correct | Explanation / grounding review |','|---:|---|---|---|---|']
 for r,review in zip(records,reviews):
  cf=r['systems']['semantic_cfaf'];co=r['systems']['shared_control'];lines.append(f"| {r['runtime_index']} | {r['official_expected_behavior']} | {cf['prediction']} / {cf['correct']} | {co['prediction']} / {co['correct']} | {cell(review['note'])} |")
 for i,(r,c,review) in enumerate(zip(records,cases,reviews)):
  lines+=['',f'## Case {i:02d}', '',f"Original ID: `{c['id']}`; source group `{c['source_id']}`.",'',f"Question: {c['perturbed_query']}",'',f"Official behavior: `{c['expected_rag_behavior']}` → `{r['expected_mode']}`.",'',f"Profile: `{r['query_profile']['resolution']}`; requirements: {', '.join(x['request_type'] for x in r['query_profile']['requirements'])}.",'',f"Gate issues: {', '.join(r['fulfilment_issues']) or 'none'}.",'']
  for system in ['semantic_cfaf','shared_control']:
   s=r['systems'][system];response=s['response'];lines+=[f"**{system}:** {s['prediction']}, official mode {'correct' if s['correct'] else 'incorrect'}.",'',response['answer'],'',f"Fine refusal category recognized by frozen lexical scorer: `{s['refusal_category']}`. {review['systems'][system]['explanation_quality']}",'']
  lines+=[review['note'],'',f"Attribution: {', '.join(review['error_attribution'])}.",'',f"Benchmark interpretation concern: {review['benchmark_interpretation_concern']}. All original annotations are retained."]
 (ROOT/'case_level_analysis.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

if __name__=='__main__':run()
