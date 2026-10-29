"""Eight logical stages, one proposal call and deterministic publication."""
import time
from .contracts import *
from .profile import LocalProfiler
from .adapters.local import ProvidedContextRetriever,QuotaLedger,evidence_contract,digest,canonical
from .render import DeterministicRenderer
from .structured import shortcut
from .structured_resolver import StructuredRequestResolver
from .gate import decide,failure,reference,resolve_evidence,ContractError

STAGES=['profiling','retrieval','access_views','evidence_assessment','sufficiency','mode_selection','realization','validation_audit']

class Pipeline:
    def __init__(self,governance,proposal,retriever=None,profiler=None,renderer=None,support_checker=None,quota=None,structured_resolver=None):
        self.governance=governance;self.proposal=proposal;self.retriever=retriever or ProvidedContextRetriever();self.profiler=profiler or LocalProfiler();self.renderer=renderer or DeterministicRenderer();self.checker=support_checker;self.quota=quota or QuotaLedger();self.structured=structured_resolver or StructuredRequestResolver()
        if self.checker is not None and not getattr(self.checker,'local_only',False):raise ValueError('ONLY_EXPLICIT_LOCAL_SHADOW_CHECKER_ALLOWED')
    def prepare(self,query,sources,authority,as_of=None,complete_scope=False):
        start=time.perf_counter();request=self.profiler.profile(query,as_of);self.quota.consume(authority,query)
        all_views,private=self.governance.project(query,sources,authority)
        selected=self.retriever.retrieve(request,all_views)
        base=evidence_contract(authority,all_views,selected,complete_scope);bindings=private.get('structured_bindings',[]);request_sig=digest(canonical(request.model_dump(mode='json')));structured_sig=digest(canonical(bindings))
        evidence=base.model_copy(update={'structured_bindings':bindings,'request_signature':request_sig,'structured_signature':structured_sig,'cache_key':digest(canonical([base.cache_key,request_sig,structured_sig]))})
        private.update(stages=STAGES,physical_order=['query_only_profile','authorization_prefilter_and_projection','authorized_retrieval','proposal','local_gate','deterministic_render','validation'],prepare_ms=(time.perf_counter()-start)*1000)
        return request,evidence,private
    def complete(self,request,evidence,private):
        start=time.perf_counter();proposal=None;usage={'attempts':0,'input_tokens':0,'output_tokens':0,'provider_ms':0,'local_model_ms':0,'cache_hits':0};trace=dict(private)
        try:
            if not self.governance.current(evidence.authority):raise ContractError('POLICY_REVOKED')
            if not evidence.views or not request.requirements:
                decision=failure('SUCCESS','EVIDENTIAL');trace['zero_call_reason']='NO_USABLE_VIEW_OR_EMPTY_REQUEST'
            else:
                resolution=self.structured.resolve(request,evidence);trace['structured_resolution']=resolution.audit
                proposal=resolution.proposal;origin='APPLICATION_STRUCTURED' if proposal else 'MODEL_ATTRIBUTED'
                if proposal:trace['zero_call_reason']='TRUSTED_STRUCTURED_REQUEST'
                elif resolution.blocked:
                    decision=failure('SUCCESS','EVIDENTIAL');trace['zero_call_reason']='UNRESOLVED_STRUCTURED_REQUEST'
                else:
                    result=self.proposal.propose(request,evidence);usage.update(result.usage);trace['proposal_provider_status']=result.status
                    if result.status!='SUCCESS':
                        decision=failure(result.status);proposal=None
                    else:proposal=result.proposal
                if proposal:
                    decision,gate_trace=decide(request,evidence,proposal,origin,resolution.permitted_restricted);trace.update(gate_trace)
                    trace['proposal']=proposal.model_dump(mode='json')
                    if self.checker:
                        try:trace['local_support_shadow']=self.checker.check(request,evidence,proposal)
                        except Exception as exc:trace['local_support_shadow']={'status':'ERROR','error_type':type(exc).__name__}
                elif 'decision' not in locals():raise ContractError('SUCCESS_WITHOUT_PROPOSAL')
            if not self.governance.current(evidence.authority):raise ContractError('POLICY_REVOKED')
            response=self.renderer.render(decision,proposal,evidence)
            self._validate_public(response,decision,proposal,evidence,trace.get('blocked_values',[]))
            if not self.governance.current(evidence.authority):raise ContractError('POLICY_REVOKED')
        except Exception as exc:
            trace['failure_code']=str(exc) if isinstance(exc,ContractError) else type(exc).__name__
            decision=failure('APPLICATION_VALIDATION_ERROR');response=DeterministicRenderer().render(decision,None,evidence)
        trace['local_complete_ms']=(time.perf_counter()-start)*1000-usage.get('provider_ms',0)
        trace['evidence_cache_key']=evidence.cache_key;trace['optional_NLI']='NOT_CONFIGURED' if not self.checker else 'LOCAL_SHADOW_ONLY'
        return RunResult(response=response,decision=decision,private_trace=trace,usage=usage)
    def run(self,query,sources,authority,as_of=None,complete_scope=False):
        try:return self.complete(*self.prepare(query,sources,authority,as_of,complete_scope))
        except Exception as exc:
            evidence=evidence_contract(authority,[],[]);d=failure('POLICY_ERROR','GOVERNANCE')
            return RunResult(response=DeterministicRenderer().render(d,None,evidence),decision=d,private_trace={'stages':STAGES,'failure_code':str(exc) if str(exc) in {'QUERY_QUOTA_EXCEEDED','POLICY_REVOKED','REQUEST_ID_REUSED_WITH_DIFFERENT_SCOPE','QUERY_ALREADY_CONSUMED'} else type(exc).__name__},usage={'attempts':0,'input_tokens':0,'output_tokens':0,'provider_ms':0})
    @staticmethod
    def _validate_public(response,decision,proposal,evidence,blocked):
        if response.mode!=decision.mode or response.execution_status!=decision.execution_status:raise ContractError('RENDERED_MODE_CHANGED')
        if decision.mode!='FULL':
            expected=DeterministicRenderer().render(decision,None,evidence)
            if response!=expected:raise ContractError('CFAF_TEMPLATE_CHANGED')
            return
        payload=response.text+' '+str([c.public_metadata for c in response.citations])
        if any(value and value in payload for value in blocked):raise ContractError('FORBIDDEN_PUBLIC_DISCLOSURE')
        if decision.mode!='FULL' and response.citations:raise ContractError('CFAF_PUBLISHED_CLAIM_CITATIONS')
        claims={c.claim_id:c for c in proposal.claims} if proposal else {}
        for c in response.citations:
            if c.claim_id not in decision.accepted_claim_ids:raise ContractError('UNACCEPTED_CLAIM_CITATION')
            view,span,_=resolve_evidence(evidence,EvidenceRef(source_id=c.source_id,quote=c.quote)) if c.quote is not None else reference(evidence,c.source_id,c.span_id)
            if (c.start,c.end,c.content_sha256)!=(span.start,span.end,view.content_sha256):raise ContractError('STALE_PUBLIC_CITATION')
            if not any(ref.source_id==c.source_id and resolve_evidence(evidence,ref)[1].span_id==span.span_id for ref in claims[c.claim_id].evidence):raise ContractError('UNATTRIBUTED_PUBLIC_CITATION')
            if c.public_metadata!=view.public_metadata:raise ContractError('UNAUTHORIZED_PUBLIC_METADATA')
