"""Explicit syntax only: structured shortcuts cannot be inferred by a model."""
import json,re,datetime
from .adapters.local import make_view
from .contracts import *
from .adapters.aggregate_core import AggregateConfig,AggregateContribution,execute_aggregate

def aggregate(contributions,decisions,operation='count',k=3):
    return execute_aggregate([AggregateContribution(**c) for c in contributions],decisions,AggregateConfig(k_threshold=k,operation=operation))

def shortcut(request,evidence):
    if len(request.requirements)!=1 or request.logic!='AND' or len(evidence.views)!=1:return None
    match=re.fullmatch(r'(metadata|aggregate)\[([A-Za-z_]+)\]',request.query.strip())
    if not match:return None
    kind,key=match.groups();view=evidence.views[0]
    if view.view_kind!=kind:return None
    data=json.loads(view.text)
    if kind=='metadata':
        if key not in data or data[key] is None or not isinstance(data[key],(str,int,float,bool)):return None
        value=data[key];t=ValueType.TEXT
        if key in {'date','created_at','updated_at','publication_date'}:
            datetime.datetime.fromisoformat(str(value).replace('Z','+00:00'));t=ValueType.DATE_TIME
        text=f'{key}: {value}'
    else:
        if key not in {'count','sum','mean'} or data.get('operation')!=key or type(data.get('value')) not in {int,float}:return None
        value=data['value'];t=ValueType.NUMBER;text=f'{key}: {value}'
    req=request.requirements[0];claim=Claim(claim_id='structured-1',requirement_ids=[req.requirement_id],text=text,value_type=t,value=str(value),subject_key=None,dependencies=[],evidence=[EvidenceRef(source_id=view.source_id,span_id=view.spans[0].span_id)])
    return LLMProposal(requirements=request.requirements,source_assessments=[SourceAssessment(source_id=view.source_id,role='PRIMARY',relation='SUPPORTS',grounding_span_ids=[view.spans[0].span_id],note='Application-authorized structured field')],claims=[claim],requirement_support=[RequirementSupport(requirement_id=req.requirement_id,status='SUFFICIENT',claim_ids=[claim.claim_id],missing='')],interpretation_limit='')
