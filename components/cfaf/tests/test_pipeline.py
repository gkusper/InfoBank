import json,pytest
from hypothesis import given,settings,strategies as st
from component_cfaf.contracts import *
from component_cfaf.pipeline import Pipeline
from component_cfaf.adapters.local import *
from component_cfaf.profile import LocalProfiler
from component_cfaf.render import NO_SUPPORT
from conftest import Stub

@pytest.mark.parametrize('n',[1,5,15,30])
@pytest.mark.parametrize('dense',[False,True])
def test_dense_sparse_inventory(n,dense,authority,source,governance):
    sources=[source.model_copy(update={'private_id':f'private-{i}'}) for i in range(n)]
    r=Pipeline(governance,Stub(dense=dense)).run('What color is the vessel?',sources,authority)
    assert r.response.mode=='FULL';inv=r.private_trace['source_assessment_inventory'];assert len(inv)==n
    assert list(inv.values()).count('NOT_ASSESSED')==(0 if dense else n-1)
    assert all('SUPPORT_NOT_INDEPENDENTLY_VERIFIED' in c.labels for c in r.response.citations)

@pytest.mark.parametrize('role',['CONTEXTUAL','IRRELEVANT','CONTRASTIVE','MISSING'])
def test_selected_support_needs_primary(role,authority,source,governance):
    def mutate(p):return p.model_copy(update={'source_assessments':[] if role=='MISSING' else [p.source_assessments[0].model_copy(update={'role':role})]})
    assert Pipeline(governance,Stub(mutate)).run('Color?', [source],authority).response.mode=='CFAF'

@pytest.mark.parametrize('query',['All colors?','What was the first color?','Color or owner?'])
def test_scope_not_assumed(query,authority,source,governance):
    assert Pipeline(governance,Stub()).run(query,[source],authority).response.mode=='CFAF'

def test_retriever_replacement(authority,source,governance):
    r=[Pipeline(governance,Stub(),retriever=x).run('vessel',[source],authority) for x in [ProvidedContextRetriever(),SQLiteRetriever()]]
    assert r[0].response==r[1].response

def test_search_never_sees_denied_text(authority,source):
    class Spy:
        def retrieve(self,r,views):assert views==[];return []
    p=Stub();g=LegacyGovernance(lambda s,a:AccessDecision(access='DENY'))
    absent=Pipeline(g,p,Spy()).run('Color?',[],authority);hidden=Pipeline(g,p,Spy()).run('Color?',[source],authority)
    assert hidden.response==absent.response and hidden.response.text==NO_SUPPORT and p.calls==0

def test_metadata_date_zero_call(authority,source):
    p=Stub();g=LegacyGovernance(lambda s,a:AccessDecision(access='METADATA',metadata_fields=['created_at']))
    r=Pipeline(g,p).run('metadata[created_at]',[source],authority)
    assert r.response.mode=='FULL' and '2026-10-01T12:00:00' in r.response.text and p.calls==0
    assert r.decision.support_origin=='APPLICATION_STRUCTURED' and 'gold_answer' not in json.dumps(r.private_trace)

def test_metadata_not_body(authority,source):
    g=LegacyGovernance(lambda s,a:AccessDecision(access='METADATA',metadata_fields=['title']))
    assert Pipeline(g,Stub()).run('What color?',[source],authority).response.mode=='CFAF'

def test_aggregate_threshold_scope(authority,source):
    from component_cfaf.structured import aggregate
    rows=[{'source_id':f's{i}','contributor_id':f'p{i}','value':i} for i in range(3)];policies={r['source_id']:'aggregate' for r in rows}
    assert aggregate(rows,policies,'count',3)['aggregate']['value']==3
    assert aggregate(rows[:2],policies,'count',3)['aggregate'] is None
    g=LegacyGovernance(lambda s,a:AccessDecision(access='AGGREGATE',aggregate_view=json.dumps({'operation':'count','value':3})))
    p=Stub();assert Pipeline(g,p).run('aggregate[count]',[source],authority).response.mode=='FULL' and p.calls==0
    assert Pipeline(g,Stub()).run('Who contributed?',[source],authority).response.mode=='CFAF'

def test_multipart_wrong_binding(authority,source,governance):
    query='Who led the project and how many tasks did she close?'
    r=Pipeline(governance,Stub()).run(query,[source],authority);assert r.response.mode=='FULL' and r.response.text=='Ada\n3'
    def wrong(p):return p.model_copy(update={'claims':[p.claims[0],p.claims[1].model_copy(update={'subject_key':'Bob'})]})
    assert Pipeline(governance,Stub(wrong)).run(query,[source],authority).response.mode=='CFAF'

@pytest.mark.parametrize('change',['remove','cycle','unknown_dependency','empty','bad_offset'])
def test_request_preservation(change,authority,source,governance):
    def mutate(p):
        if change in {'remove','empty'}:return p.model_copy(update={'requirements':p.requirements[:1] if change=='remove' else []})
        key='query_start' if change=='bad_offset' else 'depends_on';val=9999 if change=='bad_offset' else ['req-1'] if change=='cycle' else ['unknown']
        return p.model_copy(update={'requirements':[p.requirements[0].model_copy(update={key:val}),*p.requirements[1:]]})
    r=Pipeline(governance,Stub(mutate)).run('Who led and how many tasks?',[source],authority)
    assert r.response.mode=='CFAF' and r.response.execution_status=='APPLICATION_VALIDATION_ERROR'

def test_empty_request(authority,source,governance):
    p=Stub();r=Pipeline(governance,p).run(' ',[source],authority);assert r.response.mode=='CFAF' and p.calls==0

@pytest.mark.parametrize('ref',['view-0001:span-9999','view-9999:span-1','bogus'])
def test_invalid_span(ref,authority,source,governance):
    def mutate(p):return p.model_copy(update={'claims':[p.claims[0].model_copy(update={'evidence':[EvidenceRef(source_id='view-0001',span_id=ref)]})]})
    r=Pipeline(governance,Stub(mutate)).run('Color?',[source],authority);assert r.response.execution_status=='APPLICATION_VALIDATION_ERROR' and not r.response.citations

def test_alias_logged(authority,source,governance):
    def mutate(p):return p.model_copy(update={'claims':[p.claims[0].model_copy(update={'evidence':[EvidenceRef(source_id='view-0001',span_id='view-0001:span-1')]})]})
    r=Pipeline(governance,Stub(mutate)).run('Color?',[source],authority)
    assert r.response.mode=='FULL' and any(n['original']!=n['normalized'] for n in r.private_trace['normalized_references'])

@pytest.mark.parametrize('status',['PROVIDER_REFUSAL','TRUNCATED','TIMEOUT','INTERRUPTED','APPLICATION_VALIDATION_ERROR'])
def test_operational_status(status,authority,source,governance):
    r=Pipeline(governance,Stub(status=status)).run('Color?',[source],authority)
    assert r.decision.execution_status==status and r.decision.reason=='OPERATIONAL'

def test_revocation(authority,source):
    active=[True];g=LegacyGovernance(lambda s,a:AccessDecision(access='FULL'),lambda a:active[0])
    def revoke(p):active[0]=False;return p
    r=Pipeline(g,Stub(revoke)).run('Color?',[source],authority);assert r.response.execution_status=='APPLICATION_VALIDATION_ERROR' and not r.response.citations

def test_forbidden_publication(authority,source):
    denied=source.model_copy(update={'private_id':'hidden-record','content':'TOP_SECRET_PRIVATE_CONTENT'})
    g=LegacyGovernance(lambda s,a:AccessDecision(access='DENY' if s.private_id=='hidden-record' else 'FULL'))
    def leak(p):return p.model_copy(update={'claims':[p.claims[0].model_copy(update={'text':'TOP_SECRET_PRIVATE_CONTENT'})]})
    r=Pipeline(g,Stub(leak)).run('Color?',[source,denied],authority)
    assert r.response.execution_status=='APPLICATION_VALIDATION_ERROR' and 'TOP_SECRET' not in r.response.text

def test_quota_once(authority,source,governance):
    from component_cfaf.baseline import guard
    ledger=QuotaLedger(limit=1);assert Pipeline(governance,Stub(),quota=ledger).run('Color?',[source],authority).response.mode=='FULL'
    guard(StandardAnswer(mode='FULL',answer='blue'));assert list(ledger.used.values())==[1]
    assert Pipeline(governance,Stub(),quota=ledger).run('Color?',[source],authority.model_copy(update={'request_id':'q2'})).response.execution_status=='POLICY_ERROR'

def test_cache_scope(authority,source,governance):
    keys=[]
    for update in [{},{'principal':'bob'},{'policy_version':'v2'},{'revocation_version':'1'}]:
        _,e,_=Pipeline(governance,Stub()).prepare('Color?',[source],authority.model_copy(update=update));keys.append(e.cache_key)
    assert len(set(keys))==4

@given(st.text(min_size=1,max_size=80))
@settings(max_examples=40,deadline=None)
def test_p5_property(secret):
    a=Authority(principal='p',purpose='test',policy_version='1',revocation_version='0',request_id='q');g=LegacyGovernance(lambda s,a:AccessDecision(access='DENY',existence_public=False));s=RawSource(private_id='hidden',content=secret,metadata={},public_metadata={})
    r1=Pipeline(g,Stub()).run('Explain permitted material.',[s],a);r2=Pipeline(g,Stub()).run('Explain permitted material.',[],a)
    assert r1.response==r2.response and r1.usage['attempts']==0

def test_one_request_id_cannot_repeat_generation(authority,source,governance):
    provider=Stub();pipeline=Pipeline(governance,provider)
    assert pipeline.run('Color?',[source],authority).response.mode=='FULL'
    assert pipeline.run('Color?',[source],authority).response.execution_status=='POLICY_ERROR'
    assert provider.calls==1

def test_hash_and_offset_integrity(authority,source,governance):
    from component_cfaf.gate import reference,ContractError
    _,e,_=Pipeline(governance,Stub()).prepare('Color?',[source],authority)
    v=e.views[0].model_copy(update={'text':'tampered'})
    with pytest.raises(ContractError):reference(e.model_copy(update={'views':[v]}),'view-0001','view-0001:span-1')
    span=e.views[0].spans[0].model_copy(update={'end':99999});v=e.views[0].model_copy(update={'spans':[span]})
    with pytest.raises(ContractError):reference(e.model_copy(update={'views':[v]}),'view-0001','view-0001:span-1')

def test_no_optional_models_imported():
    import sys
    assert not any(k in sys.modules for k in ['spacy','sentence_transformers','torch','chromadb','langchain','haystack'])
