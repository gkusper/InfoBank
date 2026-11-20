"""Utility script to run the CFAF pipeline with ReferenceSupportChecker
and export the resulting shadow audit dictionary to a clean JSON file.
"""
import json
from pathlib import Path
from component_cfaf.contracts import (
    Authority,
    Claim,
    EvidenceRef,
    LLMProposal,
    ProviderResult,
    RawSource,
    RequirementSupport,
    SourceAssessment,
    ValueType,
    AccessDecision,
)
from component_cfaf.adapters.local import LegacyGovernance
from component_cfaf.pipeline import Pipeline
from component_cfaf.support_checker import ReferenceSupportChecker


def main() -> None:
    doc = RawSource(
        private_id='doc-vessel-01',
        content='The expedition vessel is blue. It was launched in 2024.',
        metadata={'title': 'Expedition Log'},
        public_metadata={'title': 'Expedition Log'}
    )
    auth = Authority(
        principal='alice',
        purpose='audit_inspection',
        policy_version='v1',
        revocation_version='0',
        request_id='audit-req-01'
    )
    gov = LegacyGovernance(lambda s, a: AccessDecision(access='FULL'))
    checker = ReferenceSupportChecker()

    # 1. Case A: Valid Grounding (ACCEPTED)
    class ValidProvider:
        def propose(self, req, ev):
            view = ev.views[0]
            q = 'The expedition vessel is blue.'
            claim = Claim(
                claim_id='c1',
                requirement_ids=[req.requirements[0].requirement_id],
                text=q,
                value_type=ValueType.TEXT,
                value='blue',
                subject_key=None,
                dependencies=[],
                evidence=[EvidenceRef(source_id=view.source_id, quote=q)]
            )
            ass = SourceAssessment(
                source_id=view.source_id,
                role='PRIMARY',
                relation='SUPPORTS',
                grounding_quotes=[q],
                grounding_span_ids=[],
                note='Valid citation'
            )
            sup = RequirementSupport(
                requirement_id=req.requirements[0].requirement_id,
                status='SUFFICIENT',
                claim_ids=['c1'],
                missing=''
            )
            return ProviderResult(
                proposal=LLMProposal(
                    requirements=req.requirements,
                    source_assessments=[ass],
                    claims=[claim],
                    requirement_support=[sup],
                    interpretation_limit=''
                ),
                status='SUCCESS',
                usage={'attempts': 1, 'input_tokens': 10, 'output_tokens': 10},
                raw=None
            )

    # 2. Case B: Hallucinated Quote (REJECTED)
    class HallucinatingProvider:
        def propose(self, req, ev):
            view = ev.views[0]
            q = 'The expedition vessel is neon pink.'
            claim = Claim(
                claim_id='c2',
                requirement_ids=[req.requirements[0].requirement_id],
                text=q,
                value_type=ValueType.TEXT,
                value='pink',
                subject_key=None,
                dependencies=[],
                evidence=[EvidenceRef(source_id=view.source_id, quote=q)]
            )
            ass = SourceAssessment(
                source_id=view.source_id,
                role='PRIMARY',
                relation='SUPPORTS',
                grounding_quotes=[q],
                grounding_span_ids=[],
                note='Hallucinated quote'
            )
            sup = RequirementSupport(
                requirement_id=req.requirements[0].requirement_id,
                status='SUFFICIENT',
                claim_ids=['c2'],
                missing=''
            )
            return ProviderResult(
                proposal=LLMProposal(
                    requirements=req.requirements,
                    source_assessments=[ass],
                    claims=[claim],
                    requirement_support=[sup],
                    interpretation_limit=''
                ),
                status='SUCCESS',
                usage={'attempts': 1, 'input_tokens': 10, 'output_tokens': 10},
                raw=None
            )

    pipe_valid = Pipeline(gov, ValidProvider(), support_checker=checker)
    res_valid = pipe_valid.run('What color is the expedition vessel?', [doc], auth)

    pipe_hallu = Pipeline(gov, HallucinatingProvider(), support_checker=checker)
    res_hallu = pipe_hallu.run('What color is the expedition vessel?', [doc], auth)

    output = {
        "example_1_accepted_case": res_valid.private_trace.get("local_support_shadow"),
        "example_2_rejected_case": res_hallu.private_trace.get("local_support_shadow"),
    }

    out_path = Path("shadow_audit.json")
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Shadow audit exported successfully to: {out_path.resolve()}")


if __name__ == '__main__':
    main()
