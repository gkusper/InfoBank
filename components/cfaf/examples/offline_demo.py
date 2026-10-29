from component_cfaf.contracts import *
from component_cfaf.pipeline import Pipeline
from component_cfaf.profile import LocalProfiler
from component_cfaf.adapters.local import LegacyGovernance

class DemoProposal:
    def __init__(self):self.calls=0
    def propose(self,request,evidence):
        self.calls+=1;view=evidence.views[0];rid=request.requirements[0].requirement_id
        p=LLMProposal(requirements=request.requirements,source_assessments=[SourceAssessment(source_id=view.source_id,role='PRIMARY',relation='SUPPORTS',grounding_span_ids=[view.spans[0].span_id],note='Fictional example states the color.')],claims=[Claim(claim_id='color',requirement_ids=[rid],text='The fictional vessel is blue.',value_type=ValueType.TEXT,value='blue',subject_key=None,dependencies=[],evidence=[EvidenceRef(source_id=view.source_id,span_id=view.spans[0].span_id)])],requirement_support=[RequirementSupport(requirement_id=rid,status='SUFFICIENT',claim_ids=['color'],missing='')],interpretation_limit='')
        return ProviderResult(proposal=p,status='SUCCESS',usage={'attempts':0,'mock_proposal_calls':1},raw=None)

def main():
    provider=DemoProposal();governance=LegacyGovernance(lambda s,a:AccessDecision(access='FULL'))
    authority=Authority(principal='fictional-user',purpose='demo',policy_version='demo-v1',revocation_version='0',request_id='demo-1')
    source=RawSource(private_id='local-only',content='The fictional vessel is blue.',metadata={},public_metadata={'title':'Fictional source'})
    result=Pipeline(governance,provider).run('What color is the fictional vessel?',[source],authority)
    print(result.response.model_dump_json(indent=2));print('External model requests: 0 (offline synthetic proposal)')
if __name__=='__main__':main()
