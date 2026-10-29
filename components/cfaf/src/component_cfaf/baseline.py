"""Mechanical B guard: no requirement/sufficiency gate, no model call, no quota debit."""
from .contracts import StandardAnswer
from .render import NO_SUPPORT

def guard(answer,blocked_values=()):
    if not isinstance(answer,StandardAnswer) or answer.mode not in {'FULL','CFAF'} or not answer.answer.strip():return StandardAnswer(mode='CFAF',answer=NO_SUPPORT),'APPLICATION_VALIDATION_ERROR'
    if any(v and v in answer.answer for v in blocked_values):return StandardAnswer(mode='CFAF',answer=NO_SUPPORT),'POLICY_ERROR'
    return answer,'SUCCESS'
