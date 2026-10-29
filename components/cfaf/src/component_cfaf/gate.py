"""Mechanical proposal checks and request-relative acceptance; not entailment proof."""
from graphlib import TopologicalSorter,CycleError
from decimal import Decimal,InvalidOperation
import re,datetime
from .contracts import *
from .adapters.local import digest,canonical
from .adapters.legacy_selector import select

class ContractError(ValueError):pass

def reference(evidence,source_id,span_id,aliases=True):
    views={v.source_id:v for v in evidence.views}
    if source_id not in views:raise ContractError('UNKNOWN_OR_UNSUPPLIED_SOURCE')
    view=views[source_id]
    if digest(view.text)!=view.content_sha256:raise ContractError('SOURCE_HASH_MISMATCH')
    if len([i for i in evidence.inventory if i.source_id==source_id and i.supplied and i.content_sha256==view.content_sha256])!=1:raise ContractError('STALE_SOURCE_INVENTORY')
    original=span_id
    if aliases:
        match=re.fullmatch(re.escape(source_id)+r':span-(\d+)',span_id)
        if match:span_id=f'{source_id}:span-{int(match.group(1)):04d}'
    matches=[s for s in view.spans if s.span_id==span_id]
    if len(matches)!=1:raise ContractError('INVALID_SPAN_REFERENCE')
    span=matches[0]
    if span.content_sha256!=view.content_sha256 or not (0<=span.start<span.end<=len(view.text)):raise ContractError('INVALID_SPAN_HASH_OR_OFFSET')
    return view,span,{'original':original,'normalized':span_id}

def quote_reference(evidence,source_id,quote):
    views={v.source_id:v for v in evidence.views}
    if source_id not in views:raise ContractError('UNKNOWN_OR_UNSUPPLIED_SOURCE')
    view=views[source_id]
    if digest(view.text)!=view.content_sha256:raise ContractError('SOURCE_HASH_MISMATCH')
    entries=[i for i in evidence.inventory if i.source_id==source_id and i.supplied and i.content_sha256==view.content_sha256]
    if len(entries)!=1:raise ContractError('STALE_SOURCE_INVENTORY')
    if not isinstance(quote,str) or not quote.strip():raise ContractError('EMPTY_EVIDENCE_QUOTE')
    start=view.text.find(quote)
    if start<0:raise ContractError('QUOTE_NOT_FOUND')
    if view.text.find(quote,start+1)>=0:raise ContractError('AMBIGUOUS_EVIDENCE_QUOTE')
    end=start+len(quote);span=Span(span_id=f'{source_id}:quote-{start}-{end}',start=start,end=end,content_sha256=view.content_sha256)
    return view,span,{'source_id':source_id,'start':start,'end':end,'quote_sha256':digest(quote),'reference_kind':'EXACT_UNIQUE_QUOTE'}

def resolve_evidence(evidence,ref):
    if ref.quote is not None:
        if ref.span_id is not None:raise ContractError('AMBIGUOUS_REFERENCE_REPRESENTATION')
        return quote_reference(evidence,ref.source_id,ref.quote)
    if ref.span_id is None:raise ContractError('MISSING_EVIDENCE_REFERENCE')
    return reference(evidence,ref.source_id,ref.span_id)

def validate(request,evidence,proposal):
    if evidence.request_signature and evidence.request_signature!=digest(canonical(request.model_dump(mode='json'))):raise ContractError('STALE_REQUEST_BINDING')
    base={r.requirement_id:r for r in request.requirements};reqs={r.requirement_id:r for r in proposal.requirements}
    if len(reqs)!=len(proposal.requirements) or not base.keys()<=reqs.keys():raise ContractError('REQUIRED_REQUEST_PART_REMOVED_OR_DUPLICATED')
    for key,r in reqs.items():
        if not key or not 0<=r.query_start<r.query_end<=len(request.query) or not request.query[r.query_start:r.query_end].strip():raise ContractError('INVALID_QUERY_SPAN')
        if not set(r.depends_on)<=reqs.keys():raise ContractError('UNKNOWN_REQUIREMENT_DEPENDENCY')
        if key in base:
            b=base[key]
            if (b.query_start,b.query_end)!=(r.query_start,r.query_end) or b.required and not r.required or not set(b.depends_on)<=set(r.depends_on) or b.exhaustive and not r.exhaustive:raise ContractError('EXPLICIT_REQUEST_WEAKENED')
            if b.value_type!=ValueType.UNKNOWN and b.value_type!=r.value_type:raise ContractError('EXPLICIT_VALUE_TYPE_CHANGED')
    try:tuple(TopologicalSorter({k:set(r.depends_on) for k,r in reqs.items()}).static_order())
    except CycleError as exc:raise ContractError('CYCLIC_REQUIREMENTS') from exc
    roles={a.source_id:a for a in proposal.source_assessments};views={v.source_id:v for v in evidence.views};normal=[]
    if len(roles)!=len(proposal.source_assessments) or not roles.keys()<=views.keys():raise ContractError('DUPLICATE_OR_UNKNOWN_ASSESSMENT')
    for a in roles.values():
        if a.role not in {'PRIMARY','CONTEXTUAL','CONTRASTIVE','IRRELEVANT'} or a.relation not in {'SUPPORTS','CONTRADICTS','NONE'}:raise ContractError('INVALID_ROLE_OR_RELATION')
        if a.role=='PRIMARY' and not (a.grounding_span_ids or a.grounding_quotes):raise ContractError('PRIMARY_REQUIRES_GROUNDING')
        for ref in a.grounding_span_ids:
            _,_,n=reference(evidence,a.source_id,ref);normal.append(n)
        for quote in a.grounding_quotes:
            _,_,n=quote_reference(evidence,a.source_id,quote);normal.append(n)
    claims={c.claim_id:c for c in proposal.claims}
    if len(claims)!=len(proposal.claims):raise ContractError('DUPLICATE_CLAIM')
    for c in claims.values():
        if not c.claim_id or not c.text.strip() or not c.requirement_ids or not set(c.requirement_ids)<=reqs.keys():raise ContractError('INVALID_CLAIM_REQUIREMENT')
        if not c.evidence:raise ContractError('CLAIM_WITHOUT_REFERENCE')
        for ref in c.evidence:
            _,_,n=resolve_evidence(evidence,ref);normal.append(n)
    supports={s.requirement_id:s for s in proposal.requirement_support}
    if len(supports)!=len(proposal.requirement_support) or set(supports)!=set(reqs):raise ContractError('MISSING_OR_DUPLICATE_REQUIREMENT_SUPPORT')
    for s in supports.values():
        if s.status not in {'SUFFICIENT','MISSING','PARTIAL','UNKNOWN'} or not set(s.claim_ids)<=claims.keys():raise ContractError('INVALID_SUPPORT_RECORD')
    return reqs,roles,claims,supports,normal

def value_compatible(requirement,claim):
    if requirement.value_type!=ValueType.UNKNOWN and claim.value_type!=requirement.value_type:return False
    if requirement.value_type in {ValueType.ENTITY,ValueType.NUMBER,ValueType.DATE_TIME} and not claim.value:return False
    if requirement.value_type==ValueType.NUMBER:
        try:return Decimal(claim.value).is_finite()
        except (InvalidOperation,TypeError):return False
    if requirement.value_type==ValueType.DATE_TIME:
        if re.fullmatch(r'\d{4}',claim.value or ''):return True
        try:datetime.datetime.fromisoformat(claim.value.replace('Z','+00:00'))
        except (ValueError,TypeError):return False
    return True

def decide(request,evidence,proposal,origin='MODEL_ATTRIBUTED',permitted_restricted=None):
    reqs,roles,claims,supports,normal=validate(request,evidence,proposal)
    required={r.requirement_id for r in reqs.values() if r.required}
    for _ in reqs:
        required.update(parent for rid in list(required) for parent in reqs[rid].depends_on)
    states=[];missing=[];accepted=[]
    for r in reqs.values():
        if r.requirement_id not in required:continue
        s=supports[r.requirement_id];chosen=[claims[c] for c in s.claim_ids];okay=s.status=='SUFFICIENT' and bool(chosen)
        okay=okay and request.logic=='AND' and not proposal.interpretation_limit
        if r.exhaustive and not evidence.complete_scope:okay=False
        reason='EVIDENTIAL'
        for c in chosen:
            okay=okay and r.requirement_id in c.requirement_ids and value_compatible(r,c)
            for ref in c.evidence:
                a=roles.get(ref.source_id)
                okay=okay and a is not None and a.role=='PRIMARY' and a.relation=='SUPPORTS'
                view=next(v for v in evidence.views if v.source_id==ref.source_id)
                # This minimal boundary only grants restricted structured views through explicit local syntax.
                if view.view_kind!='content' and origin!='APPLICATION_STRUCTURED' and r.requirement_id not in (permitted_restricted or {}).get(view.source_id,[]):okay=False;reason='GOVERNANCE'
            for parent in r.depends_on:
                links=[b for b in c.dependencies if b.parent_requirement_id==parent]
                valid=[]
                for link in links:
                    p=claims.get(link.parent_claim_id)
                    valid.append(bool(p and parent in p.requirement_ids and p.value and c.subject_key and link.subject_key.strip().casefold()==p.value.strip().casefold()==c.subject_key.strip().casefold() and supports[parent].status=='SUFFICIENT'))
                okay=okay and len(links)==1 and all(valid)
        if okay:accepted.extend(s.claim_ids)
        else:missing.append(r.requirement_id)
        states.append({'can_fulfil_request':bool(okay),'permitted_content':'NONE','reason_class':reason,'cfaf_realization':'ABSTAIN'})
    if not states:states=[{'can_fulfil_request':False,'permitted_content':'NONE','reason_class':'EVIDENTIAL'}]
    choice=select(states);full=choice['mode']=='FULL'
    decision=DecisionContract(mode=choice['mode'],execution_status='SUCCESS',gate_status='GATE_ACCEPTED_FULL' if full else 'GATE_REQUIRED_CFAF',realization=choice['realization'],reason=choice['reason'],accepted_claim_ids=list(dict.fromkeys(accepted)) if full else [],missing_requirement_ids=missing,support_origin=origin)
    inventory={i.source_id:(roles[i.source_id].role if i.source_id in roles else 'NOT_ASSESSED') for i in evidence.inventory}
    return decision,{'normalized_references':normal,'source_assessment_inventory':inventory,'independent_entailment_proof':False,'support_origin':origin,'requirement_states':states}

def failure(status,reason='OPERATIONAL'):
    return DecisionContract(mode='CFAF',execution_status=status,gate_status='EXECUTION_FAILED' if status!='SUCCESS' else 'GATE_REQUIRED_CFAF',realization='ABSTAIN',reason=reason,accepted_claim_ids=[],missing_requirement_ids=[],support_origin='NONE')
