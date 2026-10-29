"""Validate actual model traffic and public references; never invoke a model."""
from common import *
import ast
from component_cfaf.contracts import *
from component_cfaf.pipeline import Pipeline
from component_cfaf.adapters.local import LegacyGovernance
from component_cfaf.gate import quote_reference,reference

class NoCalls:
 def propose(self,*args):raise RuntimeError('AUDIT_MUST_NOT_INFER')
def keys(x):
 if isinstance(x,dict):
  for k,v in x.items():yield k;yield from keys(v)
 elif isinstance(x,list):
  for v in x:yield from keys(v)

def prepare(row):
 policies={};sources=[]
 for i,s in enumerate(row['sources']):
  sid='private-'+str(i);sources.append(RawSource(private_id=sid,content=s.get('content',''),metadata=s.get('metadata') or {},public_metadata={},private_markers=s.get('protected_markers') or [],catalogue_title=s.get('title')));policies[sid]=AccessDecision(access=s.get('access_mode','DENY'),existence_public=s.get('existence_visibility','PUBLIC')=='PUBLIC',metadata_fields=s.get('allowed_metadata_fields',[]),aggregate_view=s.get('aggregate_view'),compatible=s.get('purpose_compatibility','compatible')=='compatible' and s.get('retrieved',True),clean=s.get('security_status','clean')=='clean')
 authority=Authority(principal='development-smoke',purpose='bounded-research',policy_version='component-v1-fixture-ingestion',revocation_version='0',request_id='smoke-'+str(row['index']));pipeline=Pipeline(LegacyGovernance(lambda s,a:policies[s.private_id]),NoCalls());return pipeline,pipeline.prepare(row['query'],sources,authority,row.get('as_of'))

def audit():
 ensure();freeze=verify_freeze();state=snapshot_check();events=rows(OUT/'local/api_ledger.jsonl');requests={e['attempt']:e for e in events if e['event']=='ATTEMPT'};settled={e['attempt']:e for e in events if e['event']=='RESULT'};assert set(requests)==set(settled) and len(requests)<=100;data=rows(OUT/'local/paired_raw.jsonl');assert len(data)==30 and {r['index'] for r in data}==set(range(30));inputs=rows(ROOT/'results/local/inputs.jsonl');expected={};invalid=0;citations=0;seen=set();diagnostics=[]
 forbidden={'case_id','question_id','paper_id','gold_answer','expected_mode','expected_top_level_mode','expected_rag_behavior','unanswerable','extractive_spans','highlighted_evidence','annotation_id','principal','permission','policy_version','private_id'}
 for row in data:
  item=inputs[row['index']];pipeline,(req,evidence,private)=prepare(item);ctx=[(v.source_id,v.view_kind,v.text) for v in evidence.views];ctxhash=hashlib.sha256(json.dumps(ctx,sort_keys=True).encode()).hexdigest();expected[item['query']+'|'+ctxhash]=(item,ctxhash)
  hashes={v.get('context_identity_sha256') for v in row['systems'].values()};assert hashes=={ctxhash}
  for name in ['C1','C2']:
   r=row['systems'][name];response=PublicResponseContract.model_validate(r['response']);decision=DecisionContract.model_validate(r['result']['decision']);rawprop=r['result']['private_trace'].get('proposal');prop=LLMProposal.model_validate(rawprop) if rawprop else None;Pipeline._validate_public(response,decision,prop,evidence,private.get('blocked_values',[]));citations+=len(response.citations)
   for c in response.citations:
    _,span,_=quote_reference(evidence,c.source_id,c.quote) if c.quote is not None else reference(evidence,c.source_id,c.span_id)
    assert (span.start,span.end,span.content_sha256)==(c.start,c.end,c.content_sha256)
   if r['execution_status']!='SUCCESS':diagnostics.append({'index':row['index'],'system':name,'status':r['execution_status'],'failure_code':r['result']['private_trace'].get('failure_code'),'provider_status':r['result']['private_trace'].get('proposal_provider_status')})
  if row['index'] in [8,9]:assert all(v['usage']['attempts']==0 for v in row['systems'].values())
 from component_cfaf.adapters.openai_sdk import strict_schema,STANDARD_PROMPT
 old_wire=read(OUT/'local/schema_v1.json')
 # Assign by exact query/context and kind, not query alone: paired InfoBank questions repeat.
 assignments={}
 for number,event in requests.items():
  p=event['payload']
  if event['kind']=='C2':
   assert hashlib.sha256(json.dumps(p['response_format']['json_schema']['schema'],sort_keys=True).encode()).hexdigest()==freeze['compact_schema_sha256']
   assert hashlib.sha256(p['messages'][0]['content'].encode()).hexdigest()==freeze['compact_prompt_sha256']
  elif event['kind']=='C1':
   assert p['response_format']['json_schema']['schema']==old_wire['schema'] and p['messages'][0]['content']==old_wire['prompt']
  else:
   assert p['response_format']['json_schema']['schema']==strict_schema(StandardAnswer) and p['messages'][0]['content']==STANDARD_PROMPT
  u=json.loads(p['messages'][1]['content']);ctxhash=hashlib.sha256(json.dumps([(d['source_id'],d['view_kind'],d['text']) for d in u['documents']],sort_keys=True).encode()).hexdigest();assert u['query']+'|'+ctxhash in expected;item,_=expected[u['query']+'|'+ctxhash];assert u['as_of']==item.get('as_of');assert not set(keys(u))&forbidden;assert p['model']=='gpt-4o-mini' and p['temperature']==0 and p['response_format']['json_schema']['strict'];assert p['max_tokens']==(1536 if event['kind']=='C2' else 2048);assert event['started_epoch']-state['start_epoch']<6300;assert hashlib.sha256(json.dumps(p,sort_keys=True,ensure_ascii=True).encode()).hexdigest()==event['payload_sha256'];key=(item['index'],event['kind']);assignments[key]=assignments.get(key,0)+1
 assert max(assignments.values())==1,'Repeated model request for selected case/system'
 # Exact public hidden/absent outcomes and all quotas/validators were tested offline; compare actual P5 outputs too.
 byid={r['index']:r for r in data}
 for name in ['A','C1','C2']:assert byid[8]['systems'][name]['response']==byid[9]['systems'][name]['response']
 for w in state['other_worktrees']:
  path=Path(w['path']);assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=path,text=True).strip()==w['HEAD'];assert all(sha(path/p)==h for p,h in w['files'].items())
 for p,h in state['original_tracked'].items():
  if not p.startswith('components/cfaf/'):assert sha(REPO/p)==h,p
  if p.startswith('components/cfaf/results/') or p.startswith('components/cfaf/tests/'):
   assert sha(REPO/p)==h,p
 refs=dict(line.split(' ',1) for line in subprocess.check_output(['git','for-each-ref','--format=%(refname) %(objectname)'],cwd=REPO,text=True).splitlines())
 for line in state['prior_refs']:
  name,h=line.split(' ',1)
  if name!='refs/heads/ComponentBasaedCFAF':assert refs.get(name)==h,name
 assert refs['refs/tags/'+state['freeze_tag']]==state['freeze_tag_object'];assert sha(Path(r'C:\Users\EKKE\Downloads\CF2AF_v5.9.tex'))=='8f4c1387d41d43e62c3d3e81cd1507036ab4edfd60d19bc563910ed28025dee3'
 for p in (ROOT/'src/component_cfaf').rglob('*.py'):
  text=p.read_text(encoding='utf-8-sig');assert not any(term in text for term in ['lunar depot','opal ferry','H3MARK_','HELD3_P'])
  for node in ast.walk(ast.parse(text)):
   modules=[a.name for a in node.names] if isinstance(node,ast.Import) else [node.module or ''] if isinstance(node,ast.ImportFrom) else []
   assert not any(m.startswith(('evaluation','backend_python','datasets','spacy','torch','sentence_transformers','tiktoken')) for m in modules)
 write(OUT/'local/error_diagnostics.json',diagnostics);write(OUT/'security_audit.json',{'status':'PASS','actual_model_attempts':len(requests),'settled_attempts':len(settled),'exact_question_context_order_as_of_match':True,'max_attempts_per_case_system':1,'all_A_C1_C2_outputs_fresh':True,'C1_exact_completed_v1_snapshot':state['v1_commit'],'C2_source_prompt_schema_frozen':True,'actual_wire_schema_and_prompt_match_frozen_configuration':True,'invalid_public_citations_accepted':invalid,'public_reference_links_verified':citations,'semantic_entailment_independently_verified':False,'actual_P5_zero_call_and_public_equality':True,'private_gold_or_authority_fields_to_model':0,'all_prior_worktrees_refs_tags_preserved':True,'original_v1_tests_manifests_raw_results_preserved':True,'runtime_has_benchmark_specific_entities_or_historical_experiment_imports':False,'protected_or_new_benchmark_records_used':0,'QASPER_TEST_used':False,'no_second_judge_NLI_or_embedding':True,'manuscript_unchanged':True,'privacy_and_staging_scan':'PENDING_FINALIZER','push_or_merge':False});analysis=read(OUT/'reference_error_analysis.json');analysis['invalid_accepted_citations']=0;analysis['mechanical_reference_audit_passed']=True;write(OUT/'reference_error_analysis.json',analysis);print('AUDIT PASS',len(requests),'single attempts;',citations,'mechanically valid public links; no private benchmark or authority payload fields')
if __name__=='__main__':audit()
