import copy,hashlib,json
from pathlib import Path
from types import SimpleNamespace
import pytest
from . import integration as impl
from .metadata_value_typing import decompose_fixed,bind_metadata,typed_value
from .trusted_target_resolution import Entry,make_catalogue,catalogue_from_request,resolve,validate_resolution,public_summary
from .claim_evidence_alignment import StructuredFact,align_claims,validate_fact,relation_diagnostics
from .aggregate_smoke_adapter import execute
from .vendor.relation_anchors import claim_relation_signals
from .vendor.query_anchors import deterministic_allowed_keyword_matches
from evaluation.cfaf_requirement_alignment_v1.requirement_alignment import align
from evaluation.infobank_semantic_integration_v2.synthetic_cases import source
from evaluation.refusalbench_iterative_dev_v1.functional_support import FunctionalProvider
from evaluation.cfaf_request_evidence_verification_v1.source_capability_rules import trusted_provenance

def doc(title='vesper dossier',text='Avel signed the ledger.',sid='local-doc-1',access='FULL',**extra):
 return {**source(title,access),'source_id':'private-target-source-'+sid,'title':title+' private-catalogue-entry','retrieval_aliases':[title],'content':text,**extra}
def case(query='Who signed the ledger?',sources=None):return {'case_id':'local-target-unit','pair_id':'unpaired','family':'synthetic','variant':'none','query':query,'sources':[doc()] if sources is None else sources}
def request(query='Who signed the ledger?',sources=None):return impl.project_case(case(query,sources))
def entry(view='view-0001',entity='entity-private-a',aliases=('vesper dossier',),**kw):return Entry(view,entity,kw.pop('entity_type','Document'),tuple(aliases),**kw)
def controlled(query,candidate,context,entities=None,sources=None):
 c=case(query,sources if sources is not None else [doc(text=context)]);r=impl.project_case(c);p=FunctionalProvider({'expected':{'answer':candidate},'controlled_semantic_supported':True},impl);d=json.loads(p.call(r,'semantic_analysis','',r.public(),1500).content);d['entities']=entities or [];return c,r,d

def test_unique_document_declared_alias():
 r=request('What is in vesper dossier?');c=make_catalogue(r,[entry()]);t=resolve(r,c);assert t['state']=='RESOLVED';assert t['permitted_view_ids']==['view-0001'];assert t['authority']=='TRUSTED_STRUCTURED_SOURCE';assert validate_resolution(t,r,c)

def test_single_retrieved_item_without_anchor_not_resolved():
 r=request('Tell me more.');t=resolve(r,make_catalogue(r,[entry()]));assert t['state']!='RESOLVED'

def test_two_similar_titles_ambiguous():
 r=request('What does the aurora dossier say?',[doc('aurora dossier red',sid='a'),doc('aurora dossier blue',sid='b')]);t=resolve(r,make_catalogue(r,[entry('view-0001','red',('aurora dossier','aurora dossier red')),entry('view-0002','blue',('aurora dossier','aurora dossier blue'))]));assert t['state']=='AMBIGUOUS';assert t['candidate_count_privileged']==2

def test_same_title_different_objects_ambiguous():
 r=request('Summarize vesper dossier.',[doc(sid='a'),doc(sid='b')]);t=resolve(r,make_catalogue(r,[entry(),entry('view-0002','entity-private-b')]));assert t['state']=='AMBIGUOUS'

def test_object_cluster_multiple_documents_and_owned_type():
 r=request('When was my camera bought?',[doc('warranty sheet',sid='a'),doc('purchase sheet',sid='b')]);entries=[entry('view-0001','camera-44',('Juniper J8 camera',),entity_type='camera',owned=True,ownership_evidenced=True),entry('view-0002','camera-44',('Juniper J8 receipt',),entity_type='camera',owned=True,ownership_evidenced=True)];t=resolve(r,make_catalogue(r,entries));assert t['state']=='RESOLVED';assert len(t['permitted_view_ids'])==2;assert t['candidate_count_privileged']==1

def test_two_owned_objects_same_type_require_clarification():
 r=request('When was my camera bought?',[doc(sid='a'),doc(sid='b')]);entries=[entry('view-0001','camera-a',('Juniper J8',),entity_type='camera',owned=True,ownership_evidenced=True),entry('view-0002','camera-b',('Solstice S6',),entity_type='camera',owned=True,ownership_evidenced=True)];assert resolve(r,make_catalogue(r,entries))['state']=='AMBIGUOUS'

def test_owned_type_requires_authoritative_ownership():
 r=request('When was my camera bought?');t=resolve(r,make_catalogue(r,[entry(aliases=('Juniper J8',),entity_type='camera',owned=True,ownership_evidenced=False)]));assert t['state']!='RESOLVED'

@pytest.mark.parametrize('q,edition,previous', [('Read the vesper dossier edition 2.','2',False),('Read the vesper dossier previous edition.','1',True)])
def test_trusted_edition_resolution(q,edition,previous):
 r=request(q,[doc(sid='a'),doc(sid='b')]);entries=[entry('view-0001','dossier',edition='1',is_previous=True),entry('view-0002','dossier',edition='2')];t=resolve(r,make_catalogue(r,entries));assert t['state']=='RESOLVED';assert t['permitted_view_ids']==['view-0001' if previous else 'view-0002']

def test_previous_version_not_guessed_without_ordering():
 r=request('Read vesper dossier previous edition.');assert resolve(r,make_catalogue(r,[entry(edition='4')]))['state']=='UNRESOLVED'

def test_context_mention_is_not_trusted_catalogue_binding():
 r=request('What is the price of prism object?', [doc(text='Prism object was mentioned next to a price.')]);t=resolve(r,catalogue_from_request(r,False));assert t['state']!='RESOLVED'

def test_explicit_authorized_identifier():
 r=request('Summarize device VX-93.');t=resolve(r,make_catalogue(r,[entry(identifiers=('VX-93',))]));assert t['state']=='RESOLVED';assert t['resolution_method']=='EXPLICIT_AUTHORIZED_IDENTIFIER'

def test_denied_source_excluded_from_catalogue():
 c=case('What does vesper dossier say?',[doc(access='DENY')]);r=impl.project_case(c);t=resolve(r,catalogue_from_request(r,True));assert not t['permitted_view_ids'];assert t['catalogue_entry_count_privileged']==0

@pytest.mark.parametrize('access',['METADATA','AGGREGATE'])
def test_limited_views_can_bind_without_body_disclosure(access):
 r=request('What file type is recorded for vesper dossier?',[doc(access=access,metadata={'file_type':'ODT'},allowed_metadata_fields=['file_type'],aggregate_view='Count: 19')]);t=resolve(r,catalogue_from_request(r,True));assert t['state']=='RESOLVED';assert 'Avel' not in json.dumps(r.public())

def test_unresolved_pronoun():
 r=request('When did it happen?');assert resolve(r,make_catalogue(r,[entry()]))['state']=='UNRESOLVED'

def test_target_public_summary_has_no_private_fields_or_counts():
 r=request('Read vesper dossier.');t=resolve(r,make_catalogue(r,[entry()]));s=json.dumps(public_summary(t));assert 'private' not in s;assert 'vesper' not in s;assert 'count' not in s;assert 'view-' not in s

def test_unauthorized_or_stale_binding_rejected():
 r=request()
 with pytest.raises(ValueError,match='UNAUTHORIZED'):make_catalogue(r,[entry('hidden-view')])
 c=make_catalogue(r,[entry()]);t=resolve(r,c);r.documents[0]['context']='changed'
 with pytest.raises(ValueError,match='STALE'):validate_resolution(t,r,c)

def test_llm_style_catalogue_dictionary_not_authority():
 r=request()
 with pytest.raises(ValueError):make_catalogue(r,[{'view_id':'view-0001','origin':'AUTHORIZED_INGESTION_SCHEMA'}])

def test_metadata_file_type_and_date_separately_typed():
 p=decompose_fixed('What file type and creation date are recorded for vesper dossier?');a,b=p['requirements'];assert a['access_class']==b['access_class']=='METADATA';assert a['value_type']=='STRING';assert b['answer_type']==b['value_type']=='DATE_TIME';assert b['requested_attribute']=='created_at'

def test_trusted_metadata_value_binding_and_precision():
 r=request('What file type and creation date are recorded for vesper dossier?',[doc(access='METADATA',metadata={'file_type':'ODT','created_at':'2047-04-23'},allowed_metadata_fields=['file_type','created_at'])]);t=resolve(r,catalogue_from_request(r,True));p=decompose_fixed(r.query,r.query_profile);bound=[bind_metadata(x,r,t,'ODT, created 2047-04-23.') for x in p['requirements']];assert all(b['status']=='FIELD_VALUE_MATCH' for b in bound);assert all(b['authority']=='TRUSTED_STRUCTURED_SOURCE' for b in bound)

def test_invalid_metadata_date_not_accepted_by_iso_shape():
 assert typed_value('2047-02-30','DATE_TIME') is False

def test_date_in_free_text_not_authoritative_metadata():
 r=request('When was the gate opened?',[doc(text='The gate opened on 2047-04-23.')]);t=resolve(r,make_catalogue(r,[]));req=decompose_fixed(r.query,r.query_profile)['requirements'][0];assert bind_metadata(req,r,t,'2047-04-23')['authority']=='UNRESOLVED'

def test_missing_metadata_attribute_preserves_unknown():
 r=request('What creation date is recorded for vesper dossier?',[doc(access='METADATA',metadata={'file_type':'ODT'},allowed_metadata_fields=['file_type'])]);t=resolve(r,catalogue_from_request(r,True));req=decompose_fixed(r.query,r.query_profile)['requirements'][0];b=bind_metadata(req,r,t,'2047-04-23');assert b['status']!='FIELD_VALUE_MATCH'

def test_query_number_not_source_evidence():
 req=decompose_fixed('How many 23-unit parcels arrived?')['requirements'][0];d=relation_diagnostics(req,'23 parcels',[{'quote':'A parcel arrived.'}]);assert d['unsupported_numeric_tokens'];assert d['numbers_only_in_question'];assert not d['semantic_entailment_proven']

def test_unsupported_date_and_predicate_are_shadow_diagnostics():
 req=decompose_fixed('When was the cargo purchased?')['requirements'][0];d=relation_diagnostics(req,'2049',[{'quote':'The warranty excludes water damage.'}]);assert d['unsupported_numeric_tokens'];assert d['authority']=='UNRESOLVED'

def test_main_relation_anchor_reuse_does_not_imply_entailment():
 assert 'causation' in claim_relation_signals('Water caused damage.');assert 'exclusion' in claim_relation_signals('Water damage is excluded.');assert deterministic_allowed_keyword_matches('My Juniper J8 needs care.',['Juniper J8','Forbidden S4'])==['Juniper J8']

def claim_with_fact(candidate=23,actual=23,op=None,requested='How many pears were gathered?',subject=('view-0001',),target_view='view-0001'):
 record={'predicate':'pears_count','value':actual,'value_type':'COUNT','subject_view_ids':list(subject)}
 if op:record['operation']=op
 sources=[doc(text=json.dumps(record),sid='one'),doc('other dossier',text='Other permitted object.',sid='two')];c,r,d=controlled(requested+' for vesper dossier?',str(candidate),json.dumps(record),[],sources);p=decompose_fixed(r.query,r.query_profile);a=align(p,d['answer_candidate'],d,r.documents);t=resolve(r,make_catalogue(r,[entry(),entry('view-0002','other',('other dossier',))]));f=StructuredFact('view-0001',subject,'pears_count',actual,'COUNT',r.signature(),hashlib.sha256(r.documents[0]['context'].encode()).hexdigest(),operation=op);return r,d,p,a,t,f

def test_correct_typed_count_relation_binding():
 r,d,p,a,t,f=claim_with_fact();out=align_claims(p,a,d,r,t,[f]);assert out['claims'][0]['relation_status']=='STRUCTURED_VALUE_MATCH';assert out['claims'][0]['authority']=='TRUSTED_STRUCTURED_SOURCE'

def test_wrong_numeric_value_detected_from_trusted_field():
 r,d,p,a,t,f=claim_with_fact(candidate=29);out=align_claims(p,a,d,r,t,[f]);assert out['claims'][0]['relation_status']=='STRUCTURED_VALUE_MISMATCH'

def test_wrong_structured_subject_detected():
 r,d,p,a,t,f=claim_with_fact(subject=('view-0002',));out=align_claims(p,a,d,r,t,[f]);assert 'WRONG_STRUCTURED_TARGET' in out['claims'][0]['uncertainties']

def test_forged_structured_fact_rejected_even_with_hash():
 r,d,p,a,t,f=claim_with_fact();bad=StructuredFact(f.source_id,f.subject_view_ids,f.predicate,101,f.value_type,f.request_signature,f.source_sha256)
 with pytest.raises(ValueError,match='NOT_BOUND'):validate_fact(bad,r)
 with pytest.raises(ValueError,match='UNTRUSTED'):validate_fact({'authority':'TRUSTED_STRUCTURED_SOURCE'},r)

def test_correct_multipart_fragments_and_unproven_association():
 c,r,d=controlled('Who gathered the most pears and how many pears did she gather?','Solenne gathered twenty-three pears.','Solenne gathered twenty-three pears.',['Solenne']);p=decompose_fixed(r.query,r.query_profile);a=align(p,d['answer_candidate'],d,r.documents);out=align_claims(p,a,d,r,{'state':'NOT_APPLICABLE','target_id':None,'permitted_view_ids':[]});assert len(out['claims'])==2;assert out['claims'][1]['candidate_value']==23;assert all(not c['general_entailment_proof'] for c in out['claims']);assert 'SUBJECT_VALUE_ASSOCIATION_REQUIRES_SEMANTICS' in out['claims'][1]['uncertainties']

def test_missing_second_fragment_not_proven_complete():
 c,r,d=controlled('Who sent the parcel and when was it dispatched?','Tovan','Tovan sent a parcel.',['Tovan']);p=decompose_fixed(r.query,r.query_profile);a=align(p,d['answer_candidate'],d,r.documents);out=align_claims(p,a,d,r,{'state':'NOT_APPLICABLE','target_id':None,'permitted_view_ids':[]});assert out['claims'][1]['candidate_value'] is None;assert 'CANDIDATE_FRAGMENT_UNRESOLVED' in out['claims'][1]['uncertainties']

@pytest.mark.parametrize('qualifier',['first','only','unique'])
def test_qualifier_is_not_proved_by_occurrence(qualifier):
 c,r,d=controlled(f'Who was the {qualifier} archivist?','Tovan','Tovan was an archivist.',['Tovan']);p=decompose_fixed(r.query,r.query_profile);a=align(p,d['answer_candidate'],d,r.documents);out=align_claims(p,a,d,r,{'state':'NOT_APPLICABLE','target_id':None,'permitted_view_ids':[]});assert 'QUALIFIER_ENTAILMENT_UNRESOLVED' in out['claims'][0]['uncertainties']

@pytest.mark.parametrize('operation,expected',[('count',3.0),('sum',84.0),('mean',28.0)])
def test_structured_aggregate_reuse(operation,expected):
 contributions=[{'source_id':'ca','contributor_id':'u1','value':17},{'source_id':'cb','contributor_id':'u2','value':28},{'source_id':'cc','contributor_id':'u3','value':39},{'source_id':'ca-z','contributor_id':'u1','value':999}];policy={c['source_id']:'AGGREGATE' for c in contributions};out=execute(contributions,policy,operation,k=3);assert out['generator_context']['value']==expected;assert 'u1' not in json.dumps(out);assert '999' not in json.dumps(out);assert 'contributor_count' not in json.dumps(out)

def test_below_threshold_and_denied_values_non_disclosing():
 c=[{'source_id':'private-a','contributor_id':'one','value':31},{'source_id':'denied','contributor_id':'two','value':'not inspected'}];policy={'private-a':'AGGREGATE','denied':'DENY'};a=execute(c,policy,k=3);b=execute([],{},k=3);assert a==b;assert a['generator_context']=={}

@pytest.mark.parametrize('bad',[True,'31',float('nan')])
def test_aggregate_requires_typed_numeric_input(bad):
 with pytest.raises(ValueError):execute([{'source_id':'allowed','contributor_id':'u1','value':bad}],{'allowed':'AGGREGATE'})

@pytest.mark.parametrize('config',['A0','B3','T1','T2','T3'])
def test_shadow_pipeline_architecture_and_no_new_gate(config):
 c=case();p=FunctionalProvider({'expected':{'answer':'Avel'},'controlled_semantic_supported':True},impl);o=impl.run_governed(c,p,config);assert o['selected_mode']=='FULL';assert len(o['internal_trace']['stage_sequence'])==8;assert not o['system_errors'];assert set(o['public_traces']['semantic_cfaf'])==set(impl.GENERATION_SCHEMA['required']);assert not o['verification'].get('target_claim') or o['verification']['target_claim']['shadow_only']

@pytest.mark.parametrize('access',['DENY','METADATA','AGGREGATE'])
def test_no_private_body_reaches_model(access):
 c=case(sources=[doc(text='PRIV_BODY_TARGET_CANARY',access=access,metadata={'file_type':'ODT'},allowed_metadata_fields=['file_type'],aggregate_view='Count: 23')]);p=FunctionalProvider({'expected':{'answer':'ODT'},'controlled_semantic_supported':True},impl);o=impl.run_governed(c,p);assert 'PRIV_BODY_TARGET_CANARY' not in json.dumps(p.calls);assert 'PRIV_BODY_TARGET_CANARY' not in json.dumps(o['public_traces'])

def test_p5_hidden_and_absent_indistinguishable():
 c=case(sources=[doc(access='DENY',existence_visibility='INTERNAL_ONLY')]);p=FunctionalProvider({'expected':{'answer':'x'}},impl);a=impl.run_governed(c,p);c['sources']=[];b=impl.run_governed(c,p);assert a['public_traces']==b['public_traces'];assert not p.calls

def test_invalid_span_and_high_confidence_do_not_promote_full():
 c,r,d=controlled('Who signed the ledger?','Avel','Avel signed.',['Avel']);d['confidence']=1;d['requirement_support'][0]['supporting_span_ids']=['denied:span-8'];a,_,_=impl.parse_analysis(json.dumps(d),r);from .integration_controls import assess
 assert not assess(r,a,d,'T3')['validated_request_fulfilment']

def test_model_dictionary_cannot_claim_resolved_authority():
 from .trusted_target_resolution import validate_target_authority
 r=request()
 with pytest.raises(ValueError,match='NATIVE_AUTHORITY'):validate_target_authority({'state':'RESOLVED','target_id':'invented','permitted_view_ids':['view-0001']},r)

def test_mutated_native_target_attestation_rejected():
 from .trusted_target_resolution import validate_target_authority
 r=request('Read vesper dossier.');t=resolve(r,make_catalogue(r,[entry()]));t['target_id']='invented'
 with pytest.raises(ValueError,match='TAMPERED'):validate_target_authority(t,r)

def test_actor_role_claim_uses_trusted_field_not_cast_cooccurrence():
 record={'predicate':'actor_role','value':'Herald','value_type':'STRING','subject_view_ids':['view-0001']};c,r,d=controlled('Who portrays the envoy for vesper dossier?','Courier',json.dumps(record),['Courier']);p=decompose_fixed(r.query,r.query_profile);a=align(p,d['answer_candidate'],d,r.documents);t=resolve(r,make_catalogue(r,[entry()]));f=StructuredFact('view-0001',('view-0001',),'actor_role','Herald','STRING',r.signature(),hashlib.sha256(r.documents[0]['context'].encode()).hexdigest());out=align_claims(p,a,d,r,t,[f]);assert out['claims'][0]['relation_status']=='STRUCTURED_VALUE_MISMATCH'

def test_count_average_mismatch_kept_separate():
 record={'predicate':'AGGREGATE_AVERAGE','value':41,'value_type':'COUNT','subject_view_ids':['view-0001'],'operation':'COUNT'};c,r,d=controlled('What is the average processing time for vesper dossier?','41',json.dumps(record),[]);p=decompose_fixed(r.query,r.query_profile);a=align(p,d['answer_candidate'],d,r.documents);t=resolve(r,make_catalogue(r,[entry()]));f=StructuredFact('view-0001',('view-0001',),'AGGREGATE_AVERAGE',41,'COUNT',r.signature(),hashlib.sha256(r.documents[0]['context'].encode()).hexdigest(),operation='COUNT')
 # The query representation has operation AVERAGE, independent of the number.
 from .claim_evidence_alignment import predicate
 pred=predicate(p['requirements'][0]);record['predicate']=pred;r._case['sources'][0]['content']=json.dumps(record);r=impl.project_case(r._case);a=align(p,d['answer_candidate'],d,r.documents);t=resolve(r,make_catalogue(r,[entry()]));f=StructuredFact('view-0001',('view-0001',),pred,41,'COUNT',r.signature(),hashlib.sha256(r.documents[0]['context'].encode()).hexdigest(),operation='COUNT');out=align_claims(p,a,d,r,t,[f]);assert out['claims'][0]['relation_status']=='STRUCTURED_OPERATION_MISMATCH'

def test_source_role_registry_still_distinguishes_visit_obligation_invoice_payment():
 from evaluation.cfaf_request_evidence_verification_v1.source_capability_rules import capability,trusted_provenance
 r=request();r.documents[0]['source_type']='BrowserHistory';p=trusted_provenance(r,True);assert capability(r.documents[0],'PAGE_VISIT',p['view-0001'])['capability_state']=='PERMITTED';assert capability(r.documents[0],'OBLIGATION',p['view-0001'])['capability_state']=='ADDITIONAL_EVIDENCE_REQUIRED'
 r.documents[0]['source_type']='Invoice';p=trusted_provenance(r,True);assert capability(r.documents[0],'PAYMENT',p['view-0001'])['capability_state']=='ADDITIONAL_EVIDENCE_REQUIRED'

def test_counterevidence_never_removed_by_minimal_span_recommendation():
 from .claim_evidence_alignment import minimal_span_recommendation
 req=decompose_fixed('Who signed the ledger?')['requirements'][0];out=minimal_span_recommendation(req,'Avel',[{'span_id':'view-0001:span-0000','quote':'Avel signed.'}],['view-0001:span-0001']);assert not out['applied_to_model_context'];assert out['reason'].startswith('COUNTEREVIDENCE')

def test_original_mode_selector_and_prompts_unchanged():
 from evaluation.refusalbench_iterative_dev_v1.versions.v02 import implementation as old
 assert impl.TopLevelModeSelectionStage is old.TopLevelModeSelectionStage;assert impl.GOVERNED_PROMPT==old.GOVERNED_PROMPT;assert impl.ANALYSIS_SCHEMA==old.ANALYSIS_SCHEMA

def test_no_gold_in_new_model_payloads():
 c=case();c.update(gold_answer='GOLD_CLAIM_CANARY',expected_top_level_mode='CFAF');p=FunctionalProvider({'expected':{'answer':'Avel'},'controlled_semantic_supported':True},impl);impl.run_governed(c,p);assert 'GOLD_CLAIM_CANARY' not in json.dumps(p.calls);assert 'target_claim' not in json.dumps(p.calls);assert 'expected_top_level_mode' not in json.dumps(p.calls)

def test_exact_reused_function_source_hashes():
 import ast
 from .artifacts import ROOT,read
 manifest=read(ROOT/'selected_reuse_manifest.json')
 for rec in manifest['selected_units']:
  text=(ROOT/rec['destination']).read_text(encoding='utf-8');lines=text.splitlines(keepends=True);matches=[]
  for node in ast.parse(text).body:
   names=[node.name] if isinstance(node,(ast.FunctionDef,ast.ClassDef)) else [n.id for n in node.targets if isinstance(n,ast.Name)] if isinstance(node,ast.Assign) else []
   if set(names)&set(rec['names']):
    start=min([node.lineno]+[d.lineno for d in getattr(node,'decorator_list',[])]);matches.append(''.join(lines[start-1:node.end_lineno]))
  assert len(matches)==1;assert hashlib.sha256(matches[0].encode('utf-8')).hexdigest()==rec['selected_source_sha256']

def test_current_task_clock_and_45_55_minute_cutoffs(monkeypatch):
 import time
 from . import deadline
 s=deadline.state();wall=time.time();mono=time.monotonic();monkeypatch.setattr(deadline,'state',lambda:{**s,'start_epoch':wall-2701,'start_monotonic':mono-2701})
 with pytest.raises(deadline.DeadlineReached,match='45-minute'):deadline.ensure('new implementation',large_work=True)
 monkeypatch.setattr(deadline,'state',lambda:{**s,'start_epoch':wall-3301,'start_monotonic':mono-3301})
 with pytest.raises(deadline.DeadlineReached,match='55-minute'):deadline.ensure('api',new_api=True)

def test_durable_attempt_cap_is_120(tmp_path,monkeypatch):
 from . import provider
 monkeypatch.setattr(provider,'ROOT',tmp_path);(tmp_path/'api_requests.jsonl').write_text(''.join(json.dumps({'attempt':i})+'\n' for i in range(120)));p=provider.BoundedProvider.__new__(provider.BoundedProvider)
 with pytest.raises(RuntimeError,match='120 API attempt'):p._post_json('/chat/completions',{})

def test_metadata_year_precision_derived_from_trusted_timestamp():
 r=request('What year is the creation date for vesper dossier?',[doc(access='METADATA',metadata={'created_at':'2047-04-23T10:00:00'},allowed_metadata_fields=['created_at'])]);p=decompose_fixed(r.query,r.query_profile);t=resolve(r,catalogue_from_request(r,True));b=bind_metadata(p['requirements'][0],r,t,'2047');assert b['status']=='FIELD_VALUE_MATCH';assert b['requested_precision']=='YEAR'
