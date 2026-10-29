"""Five fictional v1.1 paths. Offline SDK transport is explicitly simulated."""
import json,httpx
from openai import OpenAI
from component_cfaf.contracts import *
from component_cfaf.pipeline import Pipeline
from component_cfaf.adapters.local import LegacyGovernance
from component_cfaf.compact import CompactSDKProvider
from component_cfaf.structured import aggregate

def main():
    a=Authority(principal='fictional-user',purpose='demo',policy_version='demo-1',revocation_version='0',request_id='demo')
    class Never:
        def propose(self,*args):raise AssertionError('Zero-call path invoked model')
    source=RawSource(private_id='private-demo',content='The fictional vessel is blue.',metadata={'file_type':'memo','created_at':'2026-05-04'},public_metadata={},catalogue_title='Archive Alpha metadata card')
    meta=LegacyGovernance(lambda s,a:AccessDecision(access='METADATA',metadata_fields=['file_type','created_at'],target_names=['Archive Alpha']))
    records=[]
    for name,query in [('metadata_FULL','What file type and creation date are recorded for Archive Alpha?'),('incomplete_CFAF','What file type and owner are recorded for Archive Alpha?')]:
        result=Pipeline(meta,Never()).run(query,[source],a);records.append({'demo':name,'response':result.response.model_dump(mode='json'),'external_calls':0})
    rows=[{'source_id':str(i),'contributor_id':str(i),'value':i+1,'access_mode':'AGGREGATE','unit':'hours','date':'2024-03-01'} for i in range(3)]
    spec={**a.model_dump(),'population':'team-alpha','metric':'effort','unit':'hours','rows':rows,'k':3,'period_start':'2024-01-01','period_end':'2024-12-31'}
    raw=aggregate([{k:r[k] for k in ['source_id','contributor_id','value']} for r in rows],{r['source_id']:'aggregate' for r in rows},'sum',3)
    snap={'operation':'sum','metric':'effort','unit':'hours','population':'team-alpha','value':raw['aggregate']['value']}
    governed=LegacyGovernance(lambda s,a:AccessDecision(access='AGGREGATE',aggregate_view=json.dumps(snap),aggregate_spec=spec,target_names=['Team Alpha']))
    result=Pipeline(governed,Never()).run('What is the total effort hours for Team Alpha in 2024?',[source],a);records.append({'demo':'aggregate_FULL','response':result.response.model_dump(mode='json'),'external_calls':0})
    deny=LegacyGovernance(lambda s,a:AccessDecision(access='DENY',existence_public=False));result=Pipeline(deny,Never()).run('What color is the fictional vessel?',[source],a);records.append({'demo':'P5_no_view','response':result.response.model_dump(mode='json'),'external_calls':0})
    requests=[]
    def handler(req):
        requests.append(1);proposal={'evidence':[{'id':'e1','source_id':'view-0001','quote':'The fictional vessel is blue.','role':'PRIMARY'}],'claims':[{'id':'c1','requirements':['req-1'],'text':'The fictional vessel is blue.','value_type':'TEXT','value':'blue','subject':None,'parents':[],'evidence':['e1']}],'missing':[],'unresolved':False}
        return httpx.Response(200,json={'id':'fictional-demo','created':0,'object':'chat.completion','model':'gpt-4o-mini','choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(proposal)}}],'usage':{'prompt_tokens':0,'completion_tokens':0,'total_tokens':0}})
    client=OpenAI(api_key='test-only',max_retries=0,http_client=httpx.Client(transport=httpx.MockTransport(handler)));provider=CompactSDKProvider(client=client);g=LegacyGovernance(lambda s,a:AccessDecision(access='FULL'));result=Pipeline(g,provider).run('What color is the fictional vessel?',[source],a);client.close();records.append({'demo':'ordinary_single_SDK_request','response':result.response.model_dump(mode='json'),'mock_transport_requests':len(requests),'external_calls':0})
    assert [r['response']['mode'] for r in records]==['FULL','CFAF','FULL','CFAF','FULL'] and len(requests)==1
    print(json.dumps({'status':'OFFLINE_FICTIONAL_DEMO','records':records},indent=2))
if __name__=='__main__':main()
