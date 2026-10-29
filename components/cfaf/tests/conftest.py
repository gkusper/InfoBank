import pytest
from component_cfaf.contracts import *
from component_cfaf.adapters.local import LegacyGovernance
from component_cfaf.pipeline import Pipeline

@pytest.fixture
def authority():return Authority(principal='alice',purpose='test',policy_version='v1',revocation_version='0',request_id='q1')
@pytest.fixture
def source():return RawSource(private_id='private-id',content='Ada led the fictional project. Ada closed 3 tasks. The vessel is blue.',metadata={'created_at':'2026-10-01T12:00:00','title':'Sample','gold_answer':'DO NOT EXPOSE'},public_metadata={'title':'Public title'})
@pytest.fixture
def governance():return LegacyGovernance(lambda s,a:AccessDecision(access='FULL'))

def make_proposal(request,evidence,dense=False):
    view=evidence.views[0];ref=EvidenceRef(source_id=view.source_id,span_id=view.spans[0].span_id)
    assessments=[SourceAssessment(source_id=v.source_id,role='PRIMARY',relation='SUPPORTS',grounding_span_ids=[v.spans[0].span_id],note='Synthetic direct evidence') for v in (evidence.views if dense else [view])]
    claims=[];supports=[]
    for i,r in enumerate(request.requirements):
        value='Ada' if r.value_type==ValueType.ENTITY else '3' if r.value_type==ValueType.NUMBER else 'blue'
        claims.append(Claim(claim_id=f'c{i+1}',requirement_ids=[r.requirement_id],text=value,value_type=r.value_type if r.value_type!=ValueType.UNKNOWN else ValueType.TEXT,value=value,subject_key='Ada' if r.depends_on else None,dependencies=[DependencyBinding(parent_requirement_id=p,parent_claim_id='c1',subject_key='Ada') for p in r.depends_on],evidence=[ref]))
        supports.append(RequirementSupport(requirement_id=r.requirement_id,status='SUFFICIENT',claim_ids=[f'c{i+1}'],missing=''))
    return LLMProposal(requirements=request.requirements,source_assessments=assessments,claims=claims,requirement_support=supports,interpretation_limit='')

class Stub:
    def __init__(self,mutate=None,dense=False,status='SUCCESS'):self.calls=0;self.mutate=mutate;self.dense=dense;self.status=status
    def propose(self,request,evidence):
        self.calls+=1;p=make_proposal(request,evidence,self.dense)
        if self.mutate:p=self.mutate(p)
        return ProviderResult(proposal=p if self.status=='SUCCESS' else None,status=self.status,usage={'attempts':1,'input_tokens':0,'output_tokens':0},raw=None)
