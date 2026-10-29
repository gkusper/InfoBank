import json,pytest,httpx
from openai import OpenAI
from component_cfaf.adapters.openai_sdk import SDKProvider,payload,strict_schema,OUTPUT_CAP
from component_cfaf.pipeline import Pipeline
from component_cfaf.contracts import LLMProposal
from conftest import make_proposal,Stub

@pytest.mark.parametrize('kind',['success','refusal','length','invalid','429','timeout'])
def test_official_sdk_exactly_one_transport_attempt(kind,authority,source,governance,tmp_path):
    request,evidence,_=Pipeline(governance,Stub()).prepare('Color?',[source],authority);proposal=make_proposal(request,evidence);calls=[]
    def handler(req):
        calls.append(json.loads(req.content));body=calls[-1]
        assert body['model']=='gpt-4o-mini' and body['temperature']==0 and body['max_tokens']==2048
        assert body['response_format']['json_schema']['strict'] is True
        if kind=='timeout':raise httpx.ReadTimeout('test timeout',request=req)
        if kind=='429':return httpx.Response(429,json={'error':{'message':'test','type':'rate_limit','code':'rate_limit'}})
        content='{}' if kind=='invalid' else proposal.model_dump_json()
        message={'role':'assistant','content':None if kind=='refusal' else content,'refusal':'test refusal' if kind=='refusal' else None}
        return httpx.Response(200,json={'id':'chatcmpl-test','created':1,'object':'chat.completion','model':'gpt-4o-mini','choices':[{'index':0,'finish_reason':'length' if kind=='length' else 'stop','message':message}],'usage':{'prompt_tokens':10,'completion_tokens':20,'total_tokens':30}})
    client=OpenAI(api_key='test-only',max_retries=0,http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    provider=SDKProvider(client=client,ledger=tmp_path/'private.jsonl');r=provider.propose(request,evidence)
    assert len(calls)==1 and r.usage['attempts']==1
    expected={'success':'SUCCESS','refusal':'PROVIDER_REFUSAL','length':'TRUNCATED','invalid':'APPLICATION_VALIDATION_ERROR','429':'PROVIDER_HTTP_429','timeout':'TIMEOUT'}[kind]
    assert r.status==expected
    client.close()

def test_schema_has_no_final_decision_or_authority_fields():
    s=strict_schema(LLMProposal)
    assert s['additionalProperties'] is False
    assert not {'mode','principal','permission','trusted_provenance'} & s['properties'].keys()
    for model in s['$defs'].values():
        if 'properties' in model:assert set(model['required'])==set(model['properties']) and model['additionalProperties'] is False

def test_attempt_cap_and_deadline_no_request(authority,source,governance):
    request,evidence,_=Pipeline(governance,Stub()).prepare('Color?',[source],authority)
    class Client:
        max_retries=0
    p=SDKProvider(client=Client(),attempt_cap=0);r=p.propose(request,evidence);assert r.status=='ATTEMPT_CAP' and r.usage['attempts']==0
    p=SDKProvider(client=Client(),deadline_epoch=1,clock=lambda:2);assert p.propose(request,evidence).status=='TIME_BOUND'

def test_raw_identifiers_and_permissions_not_payload(authority,source,governance):
    r,e,_=Pipeline(governance,Stub()).prepare('Color?',[source],authority);body=json.dumps(payload(r,e))
    for secret in [source.private_id,authority.principal,'gold_answer','expected_top_level_mode','principal','policy_version']:
        assert secret not in body
