"""Deterministic rendering preserves accepted claim text and explicit claim IDs."""
from .contracts import *
from .gate import reference,resolve_evidence
NO_SUPPORT='The currently usable evidence does not support the requested content.'
RESTRICTED='The request exceeds the currently permitted evidence view.'
OPERATIONAL='The response could not be validated. Please try again later.'

class DeterministicRenderer:
    def render(self,decision,proposal,evidence):
        citations=[];examined=[]
        if decision.mode=='FULL' and proposal:
            claims={c.claim_id:c for c in proposal.claims};texts=[];used=set()
            for cid in decision.accepted_claim_ids:
                claim=claims[cid];texts.append(claim.text)
                for ref in claim.evidence:
                    view,span,_=resolve_evidence(evidence,ref);used.add(view.source_id)
                    citations.append(Citation(claim_id=cid,source_id=view.source_id,span_id=span.span_id,start=span.start,end=span.end,content_sha256=view.content_sha256,quote=ref.quote,labels=['REFERENCE_VALID','APPLICATION_STRUCTURED' if decision.support_origin=='APPLICATION_STRUCTURED' else 'MODEL_ATTRIBUTED','SUPPORT_NOT_INDEPENDENTLY_VERIFIED'],public_metadata=view.public_metadata))
            text='\n'.join(texts)
            examined=[a.source_id for a in proposal.source_assessments if a.source_id not in used]
        else:
            text=OPERATIONAL if decision.execution_status!='SUCCESS' else RESTRICTED if decision.reason=='GOVERNANCE' else NO_SUPPORT
        return PublicResponseContract(text=text,mode=decision.mode,execution_status=decision.execution_status,reason=decision.reason,realization=decision.realization,next_steps=[] if decision.mode=='FULL' else ['Provide permitted evidence or clarify the request.'] if decision.execution_status=='SUCCESS' else ['Retry later.'],citations=citations,examined_sources=examined)
