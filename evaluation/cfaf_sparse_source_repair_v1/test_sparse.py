"""Fictional contract/security tests, never benchmark prediction fixtures."""
import copy,json,hashlib
from dataclasses import replace
import pytest
from . import integration as impl
from .source_inventory import build_inventory,validate_inventory,resolve_inventory_span
from .sparse_source_assessment import parse_sparse
from .reference_validation import normalize_reference
from .gate_controls import assess
from .operational_failure_codes import classify,validate_response,safe_operational_response,OPERATIONAL_PUBLIC
from .public_grounding_trace import build_public_grounding_trace
from evaluation.cfaf_target_claim_alignment_v1.test_target_claim import controlled,doc,case
from evaluation.cfaf_target_claim_alignment_v1 import integration as baseline
from evaluation.refusalbench_iterative_dev_v1.functional_support import FunctionalProvider
from evaluation.cfaf_request_evidence_verification_v1.prepare import selector

def sample(n=5,sparse=True):
 sources=[doc(title='fictional record '+str(i),text='Avel signed the ledger.' if i==0 else 'Fictional unrelated lantern '+str(i)+'.',sid=str(i)) for i in range(n)]
 c,r,d=controlled('Who signed the ledger?','Avel',sources[0]['content'],['Avel'],sources)
 if sparse:
  refs=[s for s in d['supporting_spans'] if s.startswith('view-0001:')];d['supporting_spans']=refs;d['source_assessments']=d['source_assessments'][:1]
  for req in d['requirement_support']:req['supporting_span_ids']=refs
 return c,r,d

def parsed(r,d,**kw):return parse_sparse(json.dumps(d),r,**kw)
def evaluated(r,d):
 a,data,audit=parsed(r,d);v=assess(r,a,data);return a,data,audit,v,selector(v,r,data)

@pytest.mark.parametrize('n',[1,5,15,30])
def test_dense_backward_compatibility(n):
 c,r,d=sample(n,False);old,_,_=baseline.parse_analysis(json.dumps(d),r);a,data,audit=parsed(r,d);assert old.valid and a.valid;assert data==d;assert audit['not_assessed_count']==0
@pytest.mark.parametrize('n',[1,5,15,30])
def test_sparse_subset_not_assessed_bookkeeping(n):
 c,r,d=sample(n);a,data,audit=parsed(r,d);assert a.valid;assert data==d;assert audit['not_assessed_count']==n-1;assert len(audit['inventory_states'])==n;assert all(set(x)=={'source_id','assessment_state'} for x in audit['inventory_states']);assert 'SOURCE_ROLE_COVERAGE_INVALID' not in audit['errors']
@pytest.mark.parametrize('n',[1,5,15,30])
def test_empty_assessment_allowed_if_no_support(n):
 c,r,d=sample(n);d.update(source_assessments=[],supporting_spans=[],answer_candidate=None,support_status='MISSING',premise_status='UNESTABLISHED',granularity_matches=False,uncertainty_causes=['evidence_missing'])
 for req in d['requirement_support']:req.update(supporting_span_ids=[],support_status='MISSING',complete_answer=False)
 a,data,audit,v,mode=evaluated(r,d);assert a.valid;assert audit['not_assessed_count']==n;assert mode=='CFAF';assert v['verification_outcome']['status']=='VALIDATED_CFAF'
def test_valid_selected_primary_and_required_support_preserved():
 c,r,d=sample();a,data,audit,v,mode=evaluated(r,d);assert a.valid and mode=='FULL';assert data==d;assert v['validated_request_fulfilment']
def test_contextual_not_sufficient():
 c,r,d=sample();d['source_assessments'][0].update(role='CONTEXTUAL',relation_label='NONE');a,data,audit,v,mode=evaluated(r,d);assert a.valid;assert mode=='CFAF';assert audit['substantive_source_issues'];assert v['verification_outcome']['status']=='VALIDATED_CFAF'
def test_unknown_view_invalid():
 c,r,d=sample();d['source_assessments'][0]['source_id']='view-9999';a,data,audit=parsed(r,d);assert not a.valid;assert any('ROLE_UNKNOWN_SOURCE' in e for e in audit['errors'])
def test_unknown_span_not_nearest_repaired():
 c,r,d=sample();d['supporting_spans']=['view-0001:span-0004'];a,data,audit=parsed(r,d);assert not a.valid;assert not audit['repairs'];assert any('UNKNOWN_SPAN_ID' in e for e in audit['errors']);assert classify(r,a,audit=audit)['reason']=='INVALID_EVIDENCE_REFERENCE'
@pytest.mark.parametrize('conflict',[False,True])
def test_duplicate_and_conflicting_source_rejected(conflict):
 c,r,d=sample();extra=copy.deepcopy(d['source_assessments'][0]);
 if conflict:extra['role']='IRRELEVANT'
 d['source_assessments'].append(extra);a,data,audit=parsed(r,d);assert not a.valid;assert any(('CONFLICTING' if conflict else 'DUPLICATE') in e for e in audit['errors'])
def test_reference_declared_source_must_match():
 c,r,d=sample();d['source_assessments'][0]['grounding_span_ids']=['view-0002:span-0000'];a,data,audit=parsed(r,d);assert not a.valid;assert 'ROLE_REFERENCE_SOURCE_MISMATCH' in audit['errors']
def test_support_cannot_use_unassessed_source():
 c,r,d=sample();d['source_assessments']=[];a,data,audit=parsed(r,d);assert not a.valid;assert any('SUPPORT_SOURCE_NOT_ASSESSED' in e for e in audit['errors'])
def test_missing_essential_requirement_remains_cfaf():
 c,r,d=sample();d['requirement_support'][0]['complete_answer']=False;a,data,audit,v,mode=evaluated(r,d);assert a.valid;assert mode=='CFAF';assert 'REQUEST_INCOMPLETE' in v['issues']
def test_missing_required_assessment_is_operational():
 c,r,d=sample();d['requirement_support']=[];a,data,audit,v,mode=evaluated(r,d);assert not a.valid;assert mode=='CFAF';assert v['verification_outcome']['status']=='OPERATIONAL_FAILURE'
def test_relevant_not_sufficient_relation_negative():
 c,r,d=sample();d['requirement_support'][0]['relation_and_qualifiers_supported']=False;a,data,audit,v,mode=evaluated(r,d);assert a.valid;assert mode=='CFAF';assert v['verification_outcome']['reason']=='UNSUPPORTED_RELATION'
def test_unique_quote_repair_exact_catalogue():
 c,r,d=sample(1);inv=build_inventory(r);ref,log,span=normalize_reference({'source_id':'view-0001','quote':r.documents[0]['context']},inv,r);assert ref=='view-0001:span-0000';assert log['method']=='UNIQUE_EXACT_CATALOGUE_QUOTE'
@pytest.mark.parametrize('quote',['Imaginary quotation','Avel'])
def test_absent_or_partial_quote_does_not_arbitrarily_select_window(quote):
 c,r,d=sample(1)
 with pytest.raises(ValueError):normalize_reference({'source_id':'view-0001','quote':quote},build_inventory(r),r)
def test_ambiguous_quote_rejected():
 c,r,d=controlled('What is recorded?','Echo.','Echo. Echo.');
 with pytest.raises(ValueError,match='QUOTE_NOT_UNIQUE'):normalize_reference({'source_id':'view-0001','quote':'Echo.'},build_inventory(r),r)
def test_verified_offsets_repair():
 c,r,d=sample(1);ref,log,span=normalize_reference({'source_id':'view-0001','start':0,'end':len(r.documents[0]['context'])},build_inventory(r),r);assert ref=='view-0001:span-0000';assert log['method']=='EXACT_CATALOGUE_OFFSETS'
def test_invalid_offsets_rejected():
 c,r,d=sample(1)
 with pytest.raises(ValueError):normalize_reference({'source_id':'view-0001','start':1,'end':4},build_inventory(r),r)
def test_original_marker_equivalent_mapping():
 c,r,d=sample(1);inv=build_inventory(r,[{'source_id':'view-0001','original_marker':'cite_8'}]);ref,log,span=normalize_reference('cite_8:span-0000',inv,r);assert ref=='view-0001:span-0000';assert log['method']=='EXACT_ORIGINAL_MARKER_EQUIVALENT_SPAN'
def test_original_marker_does_not_repair_unknown_window():
 c,r,d=sample(1);inv=build_inventory(r,[{'source_id':'view-0001','original_marker':'cite_8'}]);
 with pytest.raises(ValueError):normalize_reference('cite_8:span-0004',inv,r)
def test_inventory_hash_stable_and_all_authorized_sources():
 c,r,d=sample(30);a=build_inventory(r);b=build_inventory(r);assert a==b;assert len(a.entries)==30;assert validate_inventory(a,r);assert all(e.source_sha256 and e.spans for e in a.entries);assert 'original_marker' not in json.dumps(a.public())
def test_inventory_tampering_rejected():
 c,r,d=sample();inv=build_inventory(r)
 with pytest.raises(ValueError):validate_inventory(replace(inv,inventory_sha256='fake'),r)
def test_source_changed_after_projection_rejected():
 c,r,d=sample();inv=build_inventory(r);c['sources'][0]['content']='Changed unauthorized projection.'
 with pytest.raises(ValueError):validate_inventory(inv,r)
def test_reference_hash_mismatch_rejected():
 c,r,d=sample(1)
 with pytest.raises(ValueError,match='HASH_MISMATCH'):normalize_reference({'source_id':'view-0001','quote':r.documents[0]['context'],'source_sha256':'fake'},build_inventory(r),r)
def test_view_id_alias_dense_schema_compatibility():
 c,r,d=sample(1);d['source_assessments'][0]['view_id']=d['source_assessments'][0].pop('source_id');a,data,audit=parsed(r,d);assert a.valid;assert audit['repairs'];assert data['source_assessments'][0]['source_id']=='view-0001'
def test_deny_excluded_and_does_not_gain_permission_from_omission():
 c,r,d=sample();c['sources'][1].update(access_mode='DENY',existence_visibility='INTERNAL_ONLY');r=impl.project_case(c);inv=build_inventory(r);assert len(inv.entries)==4;assert c['sources'][1]['content'] not in json.dumps(r.public());assert all(e.access_mode!='DENY' for e in inv.entries)
@pytest.mark.parametrize('access',['METADATA','AGGREGATE'])
def test_limited_view_cannot_supply_body(access):
 s=doc(access=access,metadata={'file_type':'ODT'},allowed_metadata_fields=['file_type'],aggregate_view='Count: 29.',text='PRIVATE_BODY_CANARY');c=case('What does the body of vesper dossier say?',[s]);provider=FunctionalProvider({'expected':{'answer':'Avel'}},impl);out=impl.run_governed(c,provider);assert out['selected_mode']=='CFAF';assert 'PRIVATE_BODY_CANARY' not in json.dumps(provider.calls);assert out['source_inventory']['sources'][0]['access_mode']==access
@pytest.mark.parametrize('access,query,answer,extra',[('METADATA','What file type is recorded for vesper dossier?','ODT',{'metadata':{'file_type':'ODT'},'allowed_metadata_fields':['file_type']}),('AGGREGATE','How many parcels arrived for vesper dossier?','29',{'aggregate_view':'Parcel count: 29.'})])
def test_limited_view_can_fulfil_its_own_scope(access,query,answer,extra):
 c=case(query,[doc(access=access,**extra)]);p=FunctionalProvider({'expected':{'answer':answer}},impl);out=impl.run_governed(c,p);assert out['semantic_valid'];assert out['selected_mode']=='FULL'
def test_p5_hidden_absent_indistinguishable_zero_calls():
 c=case(sources=[doc(access='DENY',existence_visibility='INTERNAL_ONLY')]);p=FunctionalProvider({'expected':{'answer':'Avel'}},impl);a=impl.run_governed(c,p);c['sources']=[];b=impl.run_governed(c,p);assert a['public_traces']==b['public_traces'];assert a['responses']==b['responses'];assert not p.calls;assert not a['public_grounding_trace']['semantic_cfaf']['citations']
def test_operational_public_wording_is_not_evidence_absence():
 class InvalidProvider(FunctionalProvider):
  def call(self,request,kind,prompt,payload,limit):
   result=super().call(request,kind,prompt,payload,limit)
   if kind=='semantic_analysis':result.content='{}'
   return result
 c,r,d=sample();out=impl.run_governed(c,InvalidProvider({'expected':{'answer':'Avel'}},impl));assert out['selected_mode']=='CFAF';assert out['verification_outcome']['status']=='OPERATIONAL_FAILURE';assert all(v['answer']==OPERATIONAL_PUBLIC for v in out['responses'].values());assert not out['verification_outcome']['credited_evidential_CFAF']
def test_evidential_reason_separate_from_operational():
 c,r,d=sample();d['requirement_support'][0]['complete_answer']=False;a,data,audit,v,mode=evaluated(r,d);assert v['verification_outcome']['status']=='VALIDATED_CFAF';assert v['verification_outcome']['credited_evidential_CFAF'];assert classify(r,a,v['issues'])['status']!='OPERATIONAL_FAILURE'
@pytest.mark.parametrize('reason',['MISSING_EVIDENCE','invented','OPERATIONAL_FAILURE'])
def test_noncanonical_public_reasons_rejected(reason):
 d=safe_operational_response();d['public_reason_class']=reason;assert 'NONCANONICAL_PUBLIC_REASON_CLASS' in validate_response(json.dumps(d))
def test_existing_canonical_operational_public_response():assert not validate_response(json.dumps(safe_operational_response()))
def test_no_automatic_public_citation_for_unsupported_claim():
 c,r,d=sample();d['answer_candidate']='Zev';response={'answer':'Zev','top_level_mode':'FULL','fulfilment_status':'FULL','realization':None,'public_reason_class':None,'next_step_codes':[]};trace=build_public_grounding_trace(r,d,response,True);assert trace['citations']==[];assert trace['unverified_associations'];assert all(x['claim_level_entailment']=='CITATION_SUPPORT_UNVERIFIED' for x in trace['unverified_associations']);assert not trace['semantic_entailment_proven']
def test_control_changed_answer_has_no_fabricated_candidate_mapping():
 c,r,d=sample();response={'answer':'Different claims.','top_level_mode':'FULL','fulfilment_status':'FULL','realization':None,'public_reason_class':None,'next_step_codes':[]};trace=build_public_grounding_trace(r,d,response,True);assert not trace['citations'];assert not trace['unverified_associations'];assert trace['missing_citation_reason']=='CITATION_SUPPORT_UNVERIFIED'
def test_unchanged_prompts_schemas_stages_selector():
 for name in ['GOVERNED_PROMPT','CFAF_PROMPT','CONTROL_PROMPT','ANALYSIS_SCHEMA','GENERATION_SCHEMA']:assert getattr(impl,name)==getattr(baseline,name)
 assert len(list(impl.StageName))==8;assert impl.TopLevelModeSelectionStage is baseline.TopLevelModeSelectionStage

def test_provider_sample_id_boundary_before_network(monkeypatch):
 from .provider import BoundedProvider
 monkeypatch.setenv('OPENAI_API_KEY','fictional-unit-key');p=BoundedProvider();c,r,d=sample(1);reached=[];monkeypatch.setattr(p,'generate_json',lambda **kw:reached.append(kw))
 with pytest.raises(ValueError,match='FORBIDDEN_BENCHMARK_FIELD'):p.call(r,'shared_control','',dict(r.public(),sample_id='fictional-benchmark-id'),512)
 assert not reached

def test_provider_control_has_no_gate_contract(monkeypatch):
 from .provider import BoundedProvider
 monkeypatch.setenv('OPENAI_API_KEY','fictional-unit-key');p=BoundedProvider();c,r,d=sample(1)
 with pytest.raises(ValueError,match='CONTROL_GATE_CONTAMINATION'):p.call(r,'shared_control','',dict(r.public(),response_contract={}),512)

def test_overlapping_quote_occurrences_are_ambiguous():
 c,r,d=controlled('What text is recorded?','A'*430,'A'*431)
 with pytest.raises(ValueError,match='QUOTE_NOT_UNIQUE'):normalize_reference({'source_id':'view-0001','quote':'A'*430},build_inventory(r),r)

def test_private_mapping_must_be_authorized():
 c,r,d=sample(1)
 with pytest.raises(ValueError,match='UNAUTHORIZED'):build_inventory(r,[{'source_id':'view-9999','original_marker':'cite_1'}])

def test_private_mapping_is_unambiguous():
 c,r,d=sample(2)
 with pytest.raises(ValueError,match='AMBIGUOUS'):build_inventory(r,[{'source_id':'view-0001','original_marker':'cite_1'},{'source_id':'view-0002','original_marker':'cite_1'}])

def test_inventory_before_call_matches_postrun_private_map():
 c,r,d=sample(1);p=FunctionalProvider({'expected':{'answer':'Avel'}},impl);p.private_mapping=[{'source_id':'view-0001','original_marker':'cite_8'}];out=impl.run_governed(c,p);assert out['reference_audit']['inventory_sha256']==out['source_inventory']['inventory_sha256'];assert 'cite_8' not in json.dumps(p.calls)
