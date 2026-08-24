from __future__ import annotations

import pytest

import models
import relevance
from owned_object_context import (
    STATUS_CLARIFICATION_REQUIRED,
    STATUS_INACTIVE,
    STATUS_RESOLVED,
    PermittedDocumentContent,
    contains_purchase_evidence,
    extract_declared_object_types,
    extract_product_codes,
    resolve_owned_object_context,
)
from routers import chat
from routing import RoutingMode, route_documents


CARE = PermittedDocumentContent(
    "care-guide",
    """PRODUCT
LUNARA S3 three-seat fabric sofa
PRODUCT CODE
LUN-S3-2401
Blot spills immediately. Never use chlorine bleach on this sofa.
""",
)
RECEIPT = PermittedDocumentContent(
    "receipt",
    """PURCHASE RECEIPT
ITEM
LUNARA S3 three-seat fabric sofa
PRODUCT CODE
LUN-S3-2401
RECEIPT NUMBER R-100
PURCHASE DATE 14 November 2025
PAYMENT STATUS PAID
TOTAL PAID 249,900 HUF
""",
)
RUG = PermittedDocumentContent(
    "rug-guide",
    """PRODUCT
PolarWeave P9 polypropylene rug
PRODUCT CODE RUG-P9-009
Diluted chlorine bleach may be used for a colorfastness-tested spot.
Do not transfer this instruction to a sofa.
""",
)
ARMCHAIR = PermittedDocumentContent(
    "armchair-guide",
    """PRODUCT
Vellum L2 leather armchair
PRODUCT CODE ARM-L2-880
Use a coated-leather conditioner.
These armchair notes are not sofa instructions.
""",
)


def test_extracts_only_label_scoped_product_identifiers_and_strong_purchase_evidence() -> None:
    assert extract_product_codes(RECEIPT.text) == ("LUN-S3-2401",)
    assert "R-100" not in extract_product_codes(RECEIPT.text)
    assert contains_purchase_evidence(RECEIPT.text) is True
    assert contains_purchase_evidence("Proof of purchase may be required for warranty service.") is False
    assert extract_declared_object_types(RUG.text) == ("rug",)
    assert extract_declared_object_types(ARMCHAIR.text) == ("armchair",)


def test_product_code_extraction_discards_model_alias_and_repeated_truncated_prefix() -> None:
    extracted_pdf_text = """PRODUCT
Velora V55 Smart TV
Product code VEL-V55-2025
Model / product code V55 / VEL-V55-2025
Product code VEL-V5 a and personalised-content choices separately.
The rear label shows product code VEL-V55-2025.
"""

    assert extract_product_codes(extracted_pdf_text) == ("VEL-V55-2025",)


def test_service_document_that_only_requests_proof_of_purchase_is_not_purchase_evidence() -> None:
    service_notice = """REGIONAL SERVICE NOTICE
The service period starts on the original retail purchase date.
Customers must retain the original proof of purchase.
Verify purchase using a retail receipt or invoice before service is scheduled.
"""

    assert contains_purchase_evidence(service_notice) is False


def test_owned_television_question_prefers_purchase_evidenced_type_cluster() -> None:
    velora_manual = PermittedDocumentContent(
        "velora-manual",
        """PRODUCT
Velora V55 Smart TV
PRODUCT CODE VEL-V55-2025
Model / product code V55 / VEL-V55-2025
""",
    )
    velora_receipt = PermittedDocumentContent(
        "velora-receipt",
        """PURCHASE RECEIPT
ITEM Velora V55 Smart TV
PRODUCT CODE VEL-V55-2025
PURCHASE DATE 12 March 2025
PAYMENT STATUS PAID
TOTAL PAID 319,900 HUF
""",
    )
    aster_manual = PermittedDocumentContent(
        "aster-manual",
        """PRODUCT
Aster M55 television
PRODUCT CODE AST-M55-2024
""",
    )

    result = resolve_owned_object_context(
        "Which television do I own, when did I purchase it, and what was the price?",
        [velora_manual, velora_receipt, aster_manual],
    )

    assert result.status == STATUS_RESOLVED
    assert result.candidate_document_ids == ("velora-manual", "velora-receipt")
    assert result.purchase_evidenced_object_count == 1


def test_duration_phrases_do_not_override_declared_product_name_resolution() -> None:
    velora_terms = PermittedDocumentContent(
        "velora-terms",
        """PRODUCT
Velora V55 Smart TV
PRODUCT CODE VEL-V55-2025
The manufacturer warranty period is 24 months.
""",
    )
    velora_service = PermittedDocumentContent(
        "velora-service",
        """PRODUCT
Velora V55 Smart TV
PRODUCT CODE VEL-V55-2025
The regional service period is 18 months.
""",
    )
    velora_receipt = PermittedDocumentContent(
        "velora-receipt",
        """PURCHASE RECEIPT
ITEM Velora V55 Smart TV
PRODUCT CODE VEL-V55-2025
PURCHASE DATE 12 March 2025
PAYMENT STATUS PAID
TOTAL PAID 319,900 HUF
""",
    )
    aster_receipt = PermittedDocumentContent(
        "aster-receipt",
        """PURCHASE RECEIPT
ITEM Aster M55 television
PRODUCT CODE AST-M55-2024
PURCHASE DATE 2 January 2025
PAYMENT STATUS PAID
TOTAL PAID 199,900 HUF
""",
    )

    result = resolve_owned_object_context(
        "Does the 18-month regional service period replace the 24-month manufacturer warranty for my Velora V55?",
        [velora_terms, velora_service, velora_receipt, aster_receipt],
    )

    assert result.status == STATUS_RESOLVED
    assert result.reason == "explicit_product_description"
    assert result.candidate_document_ids == ("velora-receipt", "velora-service", "velora-terms")
    assert result.purchase_evidenced_object_count == 2


@pytest.mark.parametrize(
    "question",
    [
        "I spilled coffee on my sofa. How should I clean it?",
        "When did I buy this sofa?",
        "Can I use chlorine bleach?",
        "How long is the manufacturer's warranty?",
        "How much did I pay for the sofa?",
        "Do the care guide and purchase receipt refer to the same sofa?",
    ],
)
def test_s1_six_questions_resolve_to_the_receipt_evidenced_lunara_cluster(question: str) -> None:
    result = resolve_owned_object_context(question, [CARE, RECEIPT, RUG, ARMCHAIR])

    assert result.status == STATUS_RESOLVED
    assert result.candidate_document_ids == ("care-guide", "receipt")
    assert result.purchase_evidenced_object_count == 1


def test_objectless_bleach_question_does_not_route_to_hard_negative_rug() -> None:
    result = resolve_owned_object_context("Can I use chlorine bleach?", [CARE, RECEIPT, RUG, ARMCHAIR])

    assert result.status == STATUS_RESOLVED
    assert result.reason == "unique_purchase_evidenced_object"
    assert "rug-guide" not in result.candidate_document_ids


def test_explicit_non_owned_object_can_resolve_its_permitted_cluster() -> None:
    result = resolve_owned_object_context("Can I use bleach on the rug?", [CARE, RECEIPT, RUG, ARMCHAIR])

    assert result.status == STATUS_RESOLVED
    assert result.reason == "explicit_object_type"
    assert result.candidate_document_ids == ("rug-guide",)


def test_multiple_receipt_evidenced_objects_require_clarification() -> None:
    rug_receipt = PermittedDocumentContent(
        "rug-receipt",
        """PURCHASE RECEIPT
ITEM PolarWeave P9 rug
PRODUCT CODE RUG-P9-009
PURCHASE DATE 1 December 2025
PAYMENT STATUS PAID
TOTAL PAID 39,900 HUF
""",
    )

    result = resolve_owned_object_context("Can I use chlorine bleach?", [CARE, RECEIPT, RUG, rug_receipt])

    assert result.status == STATUS_CLARIFICATION_REQUIRED
    assert result.reason == "multiple_purchase_evidenced_objects"
    assert result.candidate_document_ids == ()


def test_receipt_excluded_by_governance_cannot_establish_ownership() -> None:
    # The caller supplies only policy-permitted FULL content. Omitting RECEIPT
    # models a denied/metadata-only receipt without exposing its content here.
    result = resolve_owned_object_context("Can I use chlorine bleach?", [CARE, RUG, ARMCHAIR])

    assert result.status == STATUS_CLARIFICATION_REQUIRED
    assert result.reason == "no_purchase_evidenced_object"
    assert result.purchase_evidenced_object_count == 0


def test_unknown_explicit_product_identifier_is_a_wrong_object_hard_negative() -> None:
    result = resolve_owned_object_context("Can I use bleach on LUN-S3-9999?", [CARE, RECEIPT, RUG])

    assert result.status == STATUS_CLARIFICATION_REQUIRED
    assert result.reason == "explicit_product_identifier_not_uniquely_resolved"
    assert result.explicit_reference_match_count == 0


def test_unstructured_corpus_preserves_existing_retrieval_behavior() -> None:
    result = resolve_owned_object_context(
        "What modern challenges do rivers face?",
        [PermittedDocumentContent("river-paper", "Rivers face pollution, climate change, and overuse.")],
    )

    assert result.status == STATUS_INACTIVE
    assert result.reason == "no_structured_product_identifiers"


def test_public_trace_is_privacy_safe_and_deterministic() -> None:
    first = resolve_owned_object_context("Can I use chlorine bleach?", [CARE, RECEIPT, RUG])
    second = resolve_owned_object_context("Can I use chlorine bleach?", [RUG, RECEIPT, CARE])

    assert first == second
    assert first.public_trace() == second.public_trace()
    serialized = str(first.public_trace())
    assert "LUN-S3-2401" not in serialized
    assert "care-guide" not in serialized
    assert "chlorine" not in serialized
    assert first.public_trace()["content_scope"] == "policy_permitted_full_content_only"


def test_database_loader_never_reads_non_full_document_content(db_session) -> None:
    for document_id in ("care", "receipt", "aggregate", "metadata"):
        db_session.add(models.Document(id=document_id, file_path=f"{document_id}.pdf"))
        db_session.add(models.DocumentChunk(
            id=f"chunk-{document_id}",
            document_id=document_id,
            chunk_index=0,
            text_content=(RECEIPT.text if document_id == "receipt" else CARE.text),
            vector_id=f"vector-{document_id}",
        ))
    db_session.flush()
    governance = {
        "use_decisions": {
            "care": relevance.USE_FULL,
            "receipt": relevance.USE_DENY,
            "aggregate": relevance.USE_AGGREGATE,
            "metadata": relevance.USE_METADATA,
        }
    }

    loaded = chat._full_permitted_document_contents(db_session, governance)

    assert [record.document_id for record in loaded] == ["care"]
    assert resolve_owned_object_context("Can I use chlorine bleach?", loaded).reason == "no_purchase_evidenced_object"


def test_owned_object_scope_keeps_full_governed_candidate_metrics() -> None:
    scoped = route_documents(
        ["care", "receipt"],
        {"care": ["care"], "receipt": ["receipt"]},
        [],
        RoutingMode.KEYWORD_ROUTING,
    )

    decision = chat._routing_decision_in_governed_scope(
        scoped,
        ["care", "receipt", "rug", "armchair"],
    )

    assert decision.candidate_document_ids == ("care", "receipt")
    assert decision.excluded_document_ids == ("armchair", "rug")
    assert decision.candidate_set_size == 2
    assert decision.governed_input_count == 4
    assert decision.fallback_reason == "no_selected_keyword"
