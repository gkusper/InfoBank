import json,pytest
from component_cfaf.contracts import *
from component_cfaf.pipeline import Pipeline
from component_cfaf.adapters.local import *
from component_cfaf.gate import quote_reference,resolve_evidence,ContractError,decide
from component_cfaf.compact import *
from component_cfaf.profile import LocalProfiler
from component_cfaf.structured import aggregate
from conftest import Stub,make_proposal

@pytest.fixture
def meta_source(source):return source.model_copy(update={'catalogue_title':'Archive Alpha metadata card','metadata':{'file_type':'memo','created_at':'2026-05-04','updated_at':'2026-05-05T13:40:00'}})
def metadata(fields=None,names=None,current=None):return LegacyGovernance(lambda s,a:AccessDecision(access='METADATA',metadata_fields=fields or ['file_type','created_at','updated_at'],target_names=names or ['Archive Alpha']),current)

@pytest.mark.parametrize('field,phrase,expected',[('file_type','file type','memo'),('created_at','creation date','2026-05-04'),('updated_at','modification time','2026-05-05T13:40:00')])
def test_nl_metadata(field,phrase,expected,authority,meta_source):
    p=Stub();r=Pipeline(metadata(),p).run(f'What is the {phrase} for Archive Alpha?',[meta_source],authority)
    assert r.response.mode=='FULL' and expected in r.response.text and p.calls==0

def test_two_fields_and_year(authority,meta_source):
    p=Stub();r=Pipeline(metadata(),p).run('What file type and creation date are recorded for Archive Alpha?',[meta_source],authority)
    assert r.response.mode=='FULL' and 'memo' in r.response.text and '2026-05-04' in r.response.text and p.calls==0
    r=Pipeline(metadata(),Stub()).run('What is the creation year for Archive Alpha?',[meta_source],authority)
    assert r.response.mode=='FULL' and '2026' in r.response.text

@pytest.mark.parametrize('query',['What file type and owner are recorded for Archive Alpha?','What is the creation timestamp for Archive Alpha?','What is the creation date for Unknown Archive?'])
def test_incomplete_metadata_never_full(query,authority,meta_source):
    r=Pipeline(metadata(),Stub()).run(query,[meta_source],authority);assert r.response.mode=='CFAF'

def test_metadata_not_permitted_field(authority,meta_source):
    assert Pipeline(metadata(['file_type']),Stub()).run('What is the creation date for Archive Alpha?',[meta_source],authority).response.mode=='CFAF'

def test_target_ambiguity_and_deny(authority,meta_source):
    other=meta_source.model_copy(update={'private_id':'other','catalogue_title':'Archive Alpha revised metadata card'})
    g=LegacyGovernance(lambda s,a:AccessDecision(access='METADATA',metadata_fields=['file_type']))
    assert Pipeline(g,Stub()).run('What is the file type for Archive Alpha?',[meta_source,other],authority).response.mode=='CFAF'
    g=LegacyGovernance(lambda s,a:AccessDecision(access='DENY'))
    r=Pipeline(g,Stub()).run('What is the file type for Archive Alpha?',[meta_source],authority);assert r.response.mode=='CFAF' and r.usage['attempts']==0

def aggregate_fixture(authority,source,op='sum',rows=None):
    unit='contributors' if op=='count' else 'hours';metric='contributors' if op=='count' else 'effort'
    rows=rows or [{'source_id':str(i),'contributor_id':str(i),'value':i+1,'unit':unit,'access_mode':'AGGREGATE','date':'2024-04-01'} for i in range(3)]
    spec={**authority.model_dump(),'metric':metric,'unit':unit,'countable':op=='count','population':'team-alpha','rows':rows,'k':3,'period_start':'2024-01-01','period_end':'2024-12-31'}
    value=aggregate([{k:r[k] for k in ['source_id','contributor_id','value']} for r in rows],{r['source_id']:'aggregate' for r in rows},op,3)['aggregate'];snapshot={'operation':op,'metric':metric,'unit':unit,'population':'team-alpha','value':value['value'] if value else None}
    g=LegacyGovernance(lambda s,a:AccessDecision(access='AGGREGATE',target_names=['Team Alpha'],aggregate_view=json.dumps(snapshot),aggregate_spec=spec))
    return g,spec,snapshot

@pytest.mark.parametrize('op,phrase,number',[('count','How many contributors',3),('sum','What is the total effort hours',6),('mean','What is the average effort hours',2)])
def test_nl_aggregate(op,phrase,number,authority,source):
    g,_,_=aggregate_fixture(authority,source,op);p=Stub();r=Pipeline(g,p).run(phrase+' for Team Alpha in 2024?',[source],authority)
    assert r.response.mode=='FULL' and str(number) in r.response.text and p.calls==0

@pytest.mark.parametrize('query',['What is the total revenue dollars for Team Alpha in 2024?','What is the total effort dollars for Team Alpha in 2024?','What is the total effort hours for Team Alpha in 2025?'])
def test_wrong_metric_unit_period(query,authority,source):
    g,_,_=aggregate_fixture(authority,source);assert Pipeline(g,Stub()).run(query,[source],authority).response.mode=='CFAF'

def test_dedup_and_threshold(authority,source):
    rows=[{'source_id':str(i),'contributor_id':'one' if i<2 else 'two','value':1,'unit':'hours','access_mode':'AGGREGATE','date':'2024-04-01'} for i in range(3)]
    g,_,_=aggregate_fixture(authority,source,rows=rows);r=Pipeline(g,Stub()).run('What is the total effort hours for Team Alpha in 2024?',[source],authority)
    assert r.response.mode=='CFAF' and r.usage['attempts']==0

def test_aggregate_stale_policy(authority,source):
    g,_,_=aggregate_fixture(authority,source);new=authority.model_copy(update={'policy_version':'v2'})
    assert Pipeline(g,Stub()).run('What is the total effort hours for Team Alpha in 2024?',[source],new).response.mode=='CFAF'

def test_quote_offsets_ambiguity_hash_and_inventory(authority,source,governance):
    req,e,_=Pipeline(governance,Stub()).prepare('What color?',[source],authority)
    view,span,_=quote_reference(e,'view-0001','The vessel is blue.');assert view.text[span.start:span.end]=='The vessel is blue.'
    for quote in ['Ada','not present','']:
        with pytest.raises(ContractError):quote_reference(e,'view-0001',quote)
    with pytest.raises(ContractError):quote_reference(e,'view-9999','The vessel is blue.')
    with pytest.raises(ContractError):quote_reference(e.model_copy(update={'inventory':[]}), 'view-0001','The vessel is blue.')
    with pytest.raises(ContractError):quote_reference(e.model_copy(update={'views':[e.views[0].model_copy(update={'text':'changed'})]}),'view-0001','changed')

def compact_example(request):
    return CompactProposal(evidence=[ProposedEvidence(id='e1',source_id='view-0001',quote='The vessel is blue.',role='PRIMARY')],claims=[ProposedClaim(id='c1',requirements=[request.requirements[0].requirement_id],text='The vessel is blue.',value_type=ValueType.TEXT,value='blue',subject=None,parents=[],evidence=['e1'])],missing=[],unresolved=False)

def test_compact_gate_renderer_and_missing(authority,source,governance):
    class CompactStub:
        calls=0
        def propose(self,r,e):
            self.calls+=1;return ProviderResult(proposal=expand(compact_example(r),r),status='SUCCESS',usage={'attempts':1},raw=None)
    p=CompactStub();r=Pipeline(governance,p).run('What color?',[source],authority)
    assert r.response.mode=='FULL' and r.response.citations[0].quote=='The vessel is blue.' and p.calls==1
    req,e,_=Pipeline(governance,Stub()).prepare('What color and who led?',[source],authority)
    compact=compact_example(req).model_copy(update={'missing':[req.requirements[1].requirement_id]})
    d,_=decide(req,e,expand(compact,req));assert d.mode=='CFAF'

def test_role_and_invalid_quote_never_promote(authority,source,governance):
    req,e,_=Pipeline(governance,Stub()).prepare('What color?',[source],authority);compact=compact_example(req)
    bad=compact.model_copy(update={'evidence':[compact.evidence[0].model_copy(update={'quote':'invented quote'})]})
    with pytest.raises(ContractError):decide(req,e,expand(bad,req))
    secondary=compact.model_copy(update={'evidence':[compact.evidence[0].model_copy(update={'role':'CONTEXTUAL'})]})
    d,_=decide(req,e,expand(secondary,req));assert d.mode=='CFAF'

@pytest.mark.parametrize('query',["Who wrote Humble and Kind?",'Who wrote "Who and What"?'])
def test_title_conjunction(query):assert len(LocalProfiler().profile(query).requirements)==1

def test_no_new_dependencies_and_compact_schema():
    from component_cfaf.adapters.openai_sdk import strict_schema
    import sys
    assert not any(name in sys.modules for name in ['spacy','torch','sentence_transformers'])
    schema=strict_schema(CompactProposal);assert set(schema['properties'])=={'evidence','claims','missing','unresolved'}
    assert not {'span_id','mode','permission','principal'} & set(str(schema).split())

@pytest.mark.parametrize('status',['refusal','length','success'])
def test_compact_sdk_one_request(status,authority,source,governance):
    import httpx
    from openai import OpenAI
    req,e,_=Pipeline(governance,Stub()).prepare('What color?',[source],authority);calls=[]
    def handler(request):
        body=json.loads(request.content);calls.append(body);assert body['max_tokens']==1536 and body['response_format']['json_schema']['strict']
        assert 'spans' not in body['messages'][1]['content'] and 'inventory' not in body['messages'][1]['content']
        message={'role':'assistant','content':compact_example(req).model_dump_json(),'refusal':'no' if status=='refusal' else None}
        return httpx.Response(200,json={'id':'test-c2','created':0,'object':'chat.completion','model':'gpt-4o-mini','choices':[{'index':0,'finish_reason':'length' if status=='length' else 'stop','message':message}],'usage':{'prompt_tokens':10,'completion_tokens':20,'total_tokens':30}})
    client=OpenAI(api_key='test-only',max_retries=0,http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    out=CompactSDKProvider(client=client).propose(req,e);assert len(calls)==1 and out.status=={'refusal':'PROVIDER_REFUSAL','length':'TRUNCATED','success':'SUCCESS'}[status];client.close()

def test_public_cfaf_factual_copy_is_withheld(authority,source,governance):
    from component_cfaf.render import DeterministicRenderer
    class BadRenderer(DeterministicRenderer):
        def render(self,*args):return super().render(*args).model_copy(update={'text':'The answer is confidential blue.'})
    out=Pipeline(governance,Stub(status='PROVIDER_REFUSAL'),renderer=BadRenderer()).run('Color?',[source],authority)
    assert out.decision.execution_status=='APPLICATION_VALIDATION_ERROR' and 'blue' not in out.response.text

def test_unsupported_aggregate_qualifier_is_not_silently_dropped(authority,source):
    g,_,_=aggregate_fixture(authority,source);out=Pipeline(g,Stub()).run('What is the total effort hours under age 30 for Team Alpha in 2024?',[source],authority)
    assert out.response.mode=='CFAF' and out.usage['attempts']==0

def test_request_binding_and_conflicting_reference(authority,source,governance):
    req,e,_=Pipeline(governance,Stub()).prepare('What color?',[source],authority);proposal=expand(compact_example(req),req)
    with pytest.raises(ContractError):decide(req.model_copy(update={'query':'Different question'}),e,proposal)
    with pytest.raises(ContractError):resolve_evidence(e,EvidenceRef(source_id='view-0001',span_id='view-0001:span-1',quote='The vessel is blue.'))

def test_structured_binding_integrity(authority,meta_source):
    pipeline=Pipeline(metadata(),Stub());request,evidence,private=pipeline.prepare('What is the file type for Archive Alpha?',[meta_source],authority)
    bad=evidence.model_copy(update={'structured_bindings':[]});out=pipeline.complete(request,bad,private)
    assert out.response.execution_status=='APPLICATION_VALIDATION_ERROR'

def test_resolver_is_replaceable(authority,meta_source):
    from component_cfaf.structured_resolver import Resolution
    class NoShortcut:
        def resolve(self,*args):return Resolution()
    out=Pipeline(metadata(),Stub(),structured_resolver=NoShortcut()).run('What is the file type for Archive Alpha?',[meta_source],authority)
    assert out.response.mode=='CFAF'

def test_dedup_above_threshold_and_authorization(authority,source):
    rows=[{'source_id':str(i),'contributor_id':['a','a','b','c'][i],'value':[1,1,2,3][i],'unit':'hours','access_mode':'AGGREGATE','date':'2024-04-01'} for i in range(4)]
    g,_,_=aggregate_fixture(authority,source,rows=rows);out=Pipeline(g,Stub()).run('What is the total effort hours for Team Alpha in 2024?',[source],authority)
    assert out.response.mode=='FULL' and '6.0' in out.response.text
    rows=[{**r,'access_mode':'DENY' if r['contributor_id']=='c' else 'AGGREGATE'} for r in rows]
    g,_,_=aggregate_fixture(authority,source,rows=rows);out=Pipeline(g,Stub()).run('What is the total effort hours for Team Alpha in 2024?',[source],authority)
    assert out.response.mode=='CFAF'
