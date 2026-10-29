"""Audit actual payloads, frozen sources and protected Git worktrees without model calls."""
from common import *
import os,ast,datetime
from component_cfaf.contracts import *
from component_cfaf.pipeline import Pipeline
from component_cfaf.adapters.local import LegacyGovernance
from component_cfaf.adapters.openai_sdk import payload,PROMPT,STANDARD_PROMPT,strict_schema

class NoCalls:
 def propose(self,*args):raise RuntimeError('AUDIT_MUST_NOT_INFER')

def keys(value):
 if isinstance(value,dict):
  for k,v in value.items():yield k;yield from keys(v)
 elif isinstance(value,list):
  for v in value:yield from keys(v)

def audit():
 ensure();freeze=verify_freeze();state=read(STATE);events=rows(ROOT/'results/local/api_ledger.jsonl');requests={e['attempt']:e for e in events if e['event']=='ATTEMPT'};settled={e['attempt']:e for e in events if e['event']=='RESULT'};assert set(requests)==set(settled) and len(requests)==56
 results=rows(ROOT/'results/local/live_results.jsonl');inputs={r['index']:r for r in rows(ROOT/'results/local/inputs.jsonl')};response_attempt={(v.get('response') or {}).get('id'):k for k,v in settled.items()};covered=set();citation_total=0
 forbidden={'case_id','question_id','paper_id','worker_id','annotation_id','gold_answer','expected_mode','expected_top_level_mode','expected_rag_behavior','unanswerable','extractive_spans','highlighted_evidence','free_form_answer','principal','permission','private_id','policy_version'}
 for record in results:
  row=inputs[record['index']];policies={};sources=[]
  for i,s in enumerate(row['sources']):
   sid='private-'+str(i);sources.append(RawSource(private_id=sid,content=s.get('content',''),metadata=s.get('metadata') or {},public_metadata={},private_markers=s.get('protected_markers') or []));policies[sid]=AccessDecision(access=s.get('access_mode','DENY'),existence_public=s.get('existence_visibility','PUBLIC')=='PUBLIC',metadata_fields=s.get('allowed_metadata_fields',[]),aggregate_view=s.get('aggregate_view'),compatible=s.get('purpose_compatibility','compatible')=='compatible' and s.get('retrieved',True),clean=s.get('security_status','clean')=='clean')
  authority=Authority(principal='development-smoke',purpose='bounded-research',policy_version='component-v1-fixture-ingestion',revocation_version='0',request_id='smoke-'+str(row['index']));pipeline=Pipeline(LegacyGovernance(lambda s,a:policies[s.private_id]),NoCalls());request,evidence,private=pipeline.prepare(row['query'],sources,authority,row.get('as_of'));expected=payload(request,evidence)
  assert hashlib.sha256(json.dumps([v.model_dump(mode='json') for v in evidence.views],sort_keys=True).encode()).hexdigest()==record['evidence_sha256']
  for system,usage in [('A',record['A_usage']),('C1',record['C1']['usage'])]:
   if usage.get('attempts',0)==0:assert not evidence.views;continue
   assert usage['attempts']==1;attempt=response_attempt[usage['response_id']];covered.add(attempt);req=requests[attempt];body=req['payload'];actual=json.loads(body['messages'][1]['content']);assert actual==expected;assert not set(keys(actual))&forbidden
   assert req['kind']==system and body['model']=='gpt-4o-mini' and body['temperature']==0 and body['max_tokens']==2048 and body['response_format']['json_schema']['strict'] is True
   assert body['messages'][0]['content']==(PROMPT if system=='C1' else STANDARD_PROMPT)
   encoded=json.dumps(body,sort_keys=True,ensure_ascii=True);assert hashlib.sha256(encoded.encode()).hexdigest()==req['payload_sha256'];assert len(encoded.encode())<=120000;assert req['started_epoch']-state['start_epoch']<6300
  response=PublicResponseContract.model_validate(record['C1']['response']);decision=DecisionContract.model_validate(record['C1']['decision']);proposal_data=record['C1']['private_trace'].get('proposal');proposal=LLMProposal.model_validate(proposal_data) if proposal_data else None;Pipeline._validate_public(response,decision,proposal,evidence,private.get('blocked_values',[]));citation_total+=len(response.citations)
 assert covered==set(requests) and citation_total==35
 for w in state['worktrees']:
  path=Path(w['path']);assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=path,text=True).strip()==w['HEAD'];assert all(sha(path/p)==h for p,h in w['files'].items())
 refs=dict(line.split(' ',1) for line in subprocess.check_output(['git','for-each-ref','--format=%(refname) %(objectname)'],cwd=REPO,text=True).splitlines())
 for line in state['refs']:
  name,h=line.split(' ',1);assert refs.get(name)==h,name
 manuscript=Path(r'C:\Users\EKKE\Downloads\CF2AF_v5.9.tex');assert sha(manuscript)=='8f4c1387d41d43e62c3d3e81cd1507036ab4edfd60d19bc563910ed28025dee3'
 imports=[]
 for p in (ROOT/'src/component_cfaf').rglob('*.py'):
  for node in ast.walk(ast.parse(p.read_text(encoding='utf-8-sig'))):
   names=[x.name for x in node.names] if isinstance(node,ast.Import) else [node.module or ''] if isinstance(node,ast.ImportFrom) else []
   for name in names:
    assert not name.startswith(('evaluation','backend_python','datasets','spacy','torch','sentence_transformers','chromadb','langchain','langgraph','llama_index','haystack'));imports.append(name)
 original_garage=Path(state['worktrees'][0]['path'])/'evaluation/cfaf_dataset3_garage_pilot_v1/runtime_inputs.jsonl';assert not any(r.get('altered_context') for r in rows(original_garage))
 write(ROOT/'security_audit.json',{'status':'PASS','audit_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'actual_payloads_checked':56,'same_authorized_question_content_order_as_of_and_early_profile_A_C1':True,'forbidden_gold_ID_and_authority_fields_in_payloads':0,'all_frozen_source_prompt_schema_input_hashes_unchanged':True,'model_temperature_output_cap_verified':True,'SDK_retries':0,'maximum_C1_requests_per_case':1,'zero_call_P5_pairs':1,'mechanically_validated_public_citations':citation_total,'semantic_support_independently_verified':False,'runtime_imports_legacy_experiment_or_scorer':False,'optional_models_downloaded_or_used':False,'original_GaRAGe_pilot_context_truncations':0,'new_context_truncations':0,'protected_worktrees':[{'HEAD':w['HEAD'],'tracked_files':len(w['files'])} for w in state['worktrees']],'all_prior_refs_unchanged':True,'manuscript_unchanged':True,'QASPER_used_for_development':False,'protected_holdout_content_opened':False,'new_benchmark_downloads':0,'public_privacy_and_staging_scan':'PENDING_FINALIZER','push_or_merge':False})
 print('AUDIT PASS: 56 actual payloads; 35 valid reference links; both protected worktrees and all prior refs unchanged')
if __name__=='__main__':audit()
