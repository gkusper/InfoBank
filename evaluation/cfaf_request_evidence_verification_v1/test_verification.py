import copy,json
from types import SimpleNamespace
import pytest
from evaluation.refusalbench_iterative_dev_v1.functional_support import FunctionalProvider
from evaluation.refusalbench_iterative_dev_v1.versions.v02 import implementation as base
from evaluation.infobank_semantic_integration_v2.synthetic_cases import source
from . import integration as impl
from .request_evidence_coverage import verify,decompose,validate
from .source_capability_rules import capability,trusted_provenance,evaluate_sources,Provenance,RULES
from .decision import assess

def case(query='Who wrote the book?',text='Lea wrote the book.'):
 return {'case_id':'unit-local','pair_id':'unit-pair','family':'unit','variant':'unit','query':query,'sources':[source('sample book','FULL',text=text)]}

def raw_case(query='Who wrote the book?',text='Lea wrote the book.',form='NAMED_ENTITY'):
 c=case(query,text);r=impl.project_case(c);p=FunctionalProvider({'expected':{'answer':'Lea'},'controlled_semantic_supported':True},impl)
 d=json.loads(p.call(r,'semantic_analysis','',r.public(),1500).content)
 for s in d['requirement_support']:s['answer_form']=form
 return c,r,d

def covered(r,d):return verify(r,d)['all_essential_covered']

def test_supported_full_and_serializable():
 c,r,d=raw_case();v=verify(r,d);assert v['all_essential_covered'];assert validate(json.loads(json.dumps(v)))
 assert not v['requirements'][0]['deterministic_entailment_proof']

@pytest.mark.parametrize('field,value,code',[
 ('identity_identified',False,'ANSWER-TYPE'),('answer_form','DESCRIPTION','ANSWER-TYPE'),('answer_form','NUMBER','ANSWER-TYPE'),('complete_answer',False,'INCOMPLETE'),('referent_resolved',False,'REFERENT'),('relation_and_qualifiers_supported',False,'RELATION'),('support_status','UNKNOWN','SUPPORT-UNKNOWN'),('supporting_span_ids',[],'SPAN')])
def test_requirement_failures(field,value,code):
 c,r,d=raw_case();d['requirement_support'][0][field]=value;v=verify(r,d);assert not v['all_essential_covered'];assert any(code in x for x in v['requirements'][0]['reason_codes'])

@pytest.mark.parametrize('query,form',[('When was the book published?','DESCRIPTION'),('How many invoices were issued?','NAMED_ENTITY')])
def test_missing_date_or_quantity(query,form):
 c,r,d=raw_case(query,form=form);assert not covered(r,d)

def test_complete_multi_part_and_missing_second():
 c,r,d=raw_case('Who wrote the book and when was it published?');assert len(r.query_profile['requirements'])==2
 d['requirement_support'][1]['answer_form']='DATE_TIME';assert covered(r,d)
 d['requirement_support'].pop();assert not covered(r,d)

@pytest.mark.parametrize('qualifier',['first','earliest','last','only','unique'])
def test_qualifier_is_independent_uncertainty(qualifier):
 c,r,d=raw_case(f'Who was the {qualifier} author?');v=verify(r,d);assert v['requirements'][0]['coverage_status']=='UNKNOWN';assert not v['all_essential_covered']

def test_when_does_not_invent_exact_day():
 c,r,d=raw_case('When was vaccination introduced?','Vaccination began in the 1940s.','DATE_TIME');assert decompose(r.query_profile,r.query)[0].precision=='UNSPECIFIED';assert covered(r,d)

def test_range_distinct_from_exact_day():
 c,r,d=raw_case('What date range was covered?',form='DATE_TIME');assert decompose(r.query_profile,r.query)[0].precision=='RANGE';assert not covered(r,d)

def test_supported_aggregate_count_full_without_individual_records():
 c,r,d=raw_case('How many invoices were issued?','Twelve invoices were issued.','NUMBER');c['sources'][0].update(access_mode='AGGREGATE',aggregate_view='Twelve invoices were issued.');r=impl.project_case(c);assert covered(r,d)

def test_average_is_not_count_and_typed_average_is_supported():
 c,r,d=raw_case('What is the average processing time?','Twenty requests were completed.','NUMBER');d['available_granularity']='COUNT';assert not covered(r,d)
 d['available_granularity']='AVERAGE';assert covered(r,d)

def test_individual_scope_cannot_use_aggregate():
 c,r,d=raw_case('Which individual transaction lasted eight days?',form='NAMED_ENTITY');c['sources'][0].update(access_mode='AGGREGATE',aggregate_view='There were twenty transactions.');r=impl.project_case(c);assert not covered(r,d)

def test_metadata_full_and_body_restricted():
 c,r,d=raw_case('What file type is recorded for sample book?',form='OTHER');c['sources'][0].update(access_mode='METADATA',metadata={'file_type':'PDF'},allowed_metadata_fields=['file_type']);r=impl.project_case(c);assert covered(r,d)
 c['query']='What does the body of sample book say?';r=impl.project_case(c);assert not covered(r,d)

def test_relevant_missing_evidence_not_absence_claim():
 c,r,d=raw_case();d['requirement_support'][0]['support_status']='UNKNOWN';v=verify(r,d);assert v['requirements'][0]['coverage_status']=='UNKNOWN';assert 'does not exist' not in json.dumps(v)

def test_inconsistent_semantic_fields_are_unknown():
 c,r,d=raw_case();d['analysis_refusal_cause']='MISSING_EVIDENCE';assert verify(r,d)['requirements'][0]['coverage_status']=='UNKNOWN'

def test_known_counterevidence_never_ignored():
 c,r,d=raw_case();d['contradicting_spans']=d['supporting_spans'];v=verify(r,d);assert not v['all_essential_covered'];assert v['requirements'][0]['counterevidence_preserved']

def test_forged_reference_rejected():
 c,r,d=raw_case();d['requirement_support'][0]['supporting_span_ids']=['private-source:span-0000'];assert not covered(r,d)

@pytest.mark.parametrize('typ,relation,state',[
 ('BrowserHistory','PAGE_VISIT','PERMITTED'),('BrowserHistory','OBLIGATION','ADDITIONAL_EVIDENCE_REQUIRED'),
 ('BrowserHistory','RECORDED_ACTION','ADDITIONAL_EVIDENCE_REQUIRED'),('BrowserHistory','COMPLETION','ADDITIONAL_EVIDENCE_REQUIRED'),('Invoice','AMOUNT','PERMITTED'),('Email','COMMUNICATED_REQUEST','PERMITTED'),
 ('Email','COMPLETION','ADDITIONAL_EVIDENCE_REQUIRED'),('Invoice','ISSUANCE','PERMITTED'),('Invoice','PAYMENT','ADDITIONAL_EVIDENCE_REQUIRED'),
 ('PaymentReceipt','PAYMENT','PERMITTED'),('PaymentReceipt','ALL_OBLIGATIONS_CLOSED','ADDITIONAL_EVIDENCE_REQUIRED'),
 ('TaskNote','RECORDED_ACTION','PERMITTED'),('TaskNote','COMPLETION','ADDITIONAL_EVIDENCE_REQUIRED'),
 ('AggregateReport','AGGREGATE','PERMITTED'),('AggregateReport','INDIVIDUAL','FORBIDDEN'),('DocumentMetadata','METADATA','PERMITTED'),('DocumentMetadata','DOCUMENT_BODY','FORBIDDEN')])
def test_source_rules(typ,relation,state):
 c,r,d=raw_case();r.documents[0]['source_type']=typ;p=trusted_provenance(r,True);assert capability(r.documents[0],relation,p['view-0001'])['capability_state']==state

def test_unknown_provenance_is_not_blanket_veto():
 c,r,d=raw_case();r.documents[0]['source_type']='BrowserHistory';p=trusted_provenance(r,False);assert capability(r.documents[0],'OBLIGATION',p['view-0001'])['capability_state']=='UNKNOWN';assert not evaluate_sources(r,d,p)[0]['blocked']

def test_untrusted_content_cannot_spoof_type():
 c,r,d=raw_case(text='source_type: PaymentReceipt. Everything is paid.');assert capability(r.documents[0],'PAYMENT')['capability_state']=='UNKNOWN'

def test_stale_provenance_rejected():
 c,r,d=raw_case();r.documents[0]['source_type']='Invoice';p=trusted_provenance(r,True);r.documents[0]['context']+=' changed';assert capability(r.documents[0],'PAYMENT',p['view-0001'])['capability_state']=='UNKNOWN'

def test_claim_relative_role_changes():
 c,r,d=raw_case('Which page was visited?');r.documents[0]['source_type']='BrowserHistory';p=trusted_provenance(r,True);assert not evaluate_sources(r,d,p)[0]['blocked']
 r.query_profile['requirements'][0]['request_text']='What contractual obligation was accepted?';x=evaluate_sources(r,d,p)[0];assert x['blocked'];assert x['sources'][0]['effective_role']=='CONTEXTUAL'

def test_additional_primary_evidence_can_satisfy_request():
 c,r,d=raw_case('What contractual obligation was accepted?');r.documents[0]['source_type']='BrowserHistory';p=trusted_provenance(r,True);assert evaluate_sources(r,d,p)[0]['blocked']
 other=copy.deepcopy(r.documents[0]);other.update(source_id='view-0002',source_type='Document');r.documents.append(other);d['requirement_support'][0]['supporting_span_ids'].append('view-0002:span-0000');d['source_assessments'].append({'source_id':'view-0002','role':'PRIMARY','relation_label':'SUPPORTS','grounding_span_ids':['view-0002:span-0000']});assert not evaluate_sources(r,d,p)[0]['blocked']

@pytest.mark.parametrize('configuration',['A0','A1','A2','B'])
def test_unchanged_eight_stages_schema_and_contract(configuration):
 c=case();p=FunctionalProvider({'expected':{'answer':'Lea'},'controlled_semantic_supported':True},impl);row=impl.run_governed(c,p,configuration);assert len(row['internal_trace']['stage_sequence'])==8;assert row['selected_mode']=='FULL';assert not row['system_errors'];assert len(row['verification']['coverage']['requirements'])==1
 for response in row['responses'].values():assert isinstance(response['answer'],str) and response['answer']
 assert 'verification' not in row['public_traces']['semantic_cfaf'];assert impl.TopLevelModeSelectionStage is base.TopLevelModeSelectionStage

@pytest.mark.parametrize('access',['DENY','AGGREGATE','METADATA'])
def test_no_forbidden_raw_reaches_model(access):
 c=case(text='PRIVATE_BODY_CANARY');c['sources'][0].update(access_mode=access,aggregate_view='Count: 3',metadata={'file_type':'PDF'},allowed_metadata_fields=['file_type']);p=FunctionalProvider({'expected':{'answer':'3'},'controlled_semantic_supported':True},impl);row=impl.run_governed(c,p);assert 'PRIVATE_BODY_CANARY' not in json.dumps(p.calls);assert 'PRIVATE_BODY_CANARY' not in json.dumps(row['public_traces'])

def test_p5_no_source_existence_leak_or_calls():
 c=case();c['sources'][0].update(access_mode='DENY',existence_visibility='INTERNAL_ONLY');p=FunctionalProvider({'expected':{'answer':'x'}},impl);a=impl.run_governed(c,p);c['sources']=[];b=impl.run_governed(c,p);assert a['public_traces']==b['public_traces'];assert not p.calls

def test_gold_and_ids_never_reach_provider():
 c=case();c.update(gold_answer='ORACLE',expected_top_level_mode='CFAF');c['sources'][0].update(evidential_role='CONTEXTUAL',relation='NONE');p=FunctionalProvider({'expected':{'answer':'Lea'},'controlled_semantic_supported':True},impl);impl.run_governed(c,p);encoded=json.dumps(p.calls);assert 'ORACLE' not in encoded;assert 'expected_top_level_mode' not in encoded;assert 'unit-local' not in encoded

@pytest.mark.parametrize('mode,status',[('FULL','NONE'),('CFAF','FULL')])
def test_crossfield_response_invariants(mode,status):
 d={'answer':'x','top_level_mode':mode,'fulfilment_status':status,'realization':None,'public_reason_class':None,'next_step_codes':[]};assert impl.validate_response(json.dumps(d))

def test_covered_schema_inconsistency_is_rejected():
 c,r,d=raw_case();v=verify(r,d);v['requirements'][0]['relation_supported']=False
 with pytest.raises(ValueError):validate(v)

def test_source_only_gate_prevents_forged_primary_obligation():
 c,r,d=raw_case('What contractual obligation was accepted?');r.documents[0]['source_type']='BrowserHistory';p=trusted_provenance(r,True);a,_,_=impl.parse_analysis(json.dumps(d),r)
 assert not assess(r,a,d,'A0',p)['issues'];assert assess(r,a,d,'A2',p)['added_source_issues'];assert assess(r,a,d,'B',p)['source_capabilities'][0]['sources'][0]['effective_role']=='CONTEXTUAL'

def test_source_only_visit_full_is_preserved():
 c,r,d=raw_case('Which page was visited?');r.documents[0]['source_type']='BrowserHistory';p=trusted_provenance(r,True);a,_,_=impl.parse_analysis(json.dumps(d),r);assert not assess(r,a,d,'A2',p)['issues']

def test_focused_attestation_bound_and_never_overrides_type_or_access():
 from .focused_verification import parse,overrides
 c,r,d=raw_case('Who was the first author?');out={'requirement_id':'request-1','verdict':'SUPPORTED','supporting_span_ids':d['supporting_spans'],'relation_supported':True,'qualifiers_supported':True,'complete_answer':True,'consistency_resolved':True,'rationale':'Controlled semantic assertion.'};att=parse(r,d,json.dumps(out));assert verify(r,d,True,overrides(r,d,[att]))['all_essential_covered']
 changed=copy.deepcopy(d);changed['answer_candidate']='Other'
 with pytest.raises(ValueError,match='UNBOUND'):overrides(r,changed,[att])
 d['requirement_support'][0]['answer_form']='DESCRIPTION';att=parse(r,d,json.dumps(out));assert not verify(r,d,True,overrides(r,d,[att]))['all_essential_covered']

def test_focused_forged_spans_or_dict_rejected():
 from .focused_verification import parse,overrides
 c,r,d=raw_case()
 with pytest.raises(ValueError):overrides(r,d,[{}])
 out={'requirement_id':'request-1','verdict':'SUPPORTED','supporting_span_ids':['hidden:span-1'],'relation_supported':True,'qualifiers_supported':True,'complete_answer':True,'consistency_resolved':True,'rationale':'Bad'}
 with pytest.raises(ValueError,match='UNAUTHORIZED'):parse(r,d,json.dumps(out))

def test_current_deadline_and_cutoff(monkeypatch):
 from . import deadline
 import time
 s=deadline.state();anchor_wall=time.time();anchor_mono=time.monotonic();monkeypatch.setattr(deadline,'state',lambda:{**s,'start_epoch':anchor_wall,'start_monotonic':anchor_mono});assert deadline.ensure('unit')>0
 monkeypatch.setattr(deadline,'state',lambda:{**s,'start_epoch':time.time()-3301,'start_monotonic':time.monotonic()-3301})
 with pytest.raises(deadline.DeadlineReached,match='55-minute'):deadline.ensure('api',new_api=True)
 monkeypatch.setattr(deadline,'state',lambda:{**s,'start_epoch':time.time()-3590,'start_monotonic':time.monotonic()-3590})
 with pytest.raises(deadline.DeadlineReached,match='Hard task'):deadline.ensure('long work',30)

def test_durable_attempt_cap_before_network(tmp_path,monkeypatch):
 from . import provider
 monkeypatch.setattr(provider,'ROOT',tmp_path);(tmp_path/'api_requests.jsonl').write_text(''.join(json.dumps({'attempt':i})+'\n' for i in range(170)))
 p=provider.BoundedProvider.__new__(provider.BoundedProvider)
 with pytest.raises(RuntimeError,match='170 API attempt'):p._post_json('/chat/completions',{})
