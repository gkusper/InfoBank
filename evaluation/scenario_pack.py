"""Roadmap v1.8 ScenarioPack descriptions and structural validation.

ScenarioPack is an evaluation-authoring contract.  It must not be imported by
the production API, and its gold fields must not be visible to an evaluation
runner before the raw run has been sealed.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from .actual_pipeline_gold import GoldAnnotation
from .actual_pipeline_inputs import QueryInput


SCENARIO_PACK_SCHEMA_ID = "infobank-scenario-pack-v1"
SCENARIO_PROJECTION_VERSION = "infobank-scenario-projection-v1"
SCENARIO_DATASET_VERSION = "scenario-pack-development-v1"
SCENARIO_IDS = (
    "S1_SOFA_01",
    "S2_TV_WARRANTY_01",
    "S3_TESCO_ORDERS_01",
    "S4_TESCO_BANK_01",
    "S5_TV_INSURANCE_01",
    "S6_EV_SOLAR_01",
)
OUTPUT_CLASSES = {
    "FULL_ANSWER",
    "CONSTRAINED_ANSWER",
    "AGGREGATE_RESULT",
    "METADATA_ONLY",
    "CLARIFICATION",
    "REFUSE_PERMISSION",
    "REFUSE_INSUFFICIENT_EVIDENCE",
    "REFUSE_NO_MATCH",
    "REFUSE_AGGREGATION_THRESHOLD",
    "REFUSE_CONFLICT",
}
PERMISSIONS = {"Owner", "Reader", "Aggregate", "Metadata", "Deny"}

PACK_FIELDS = {"scenario_id", "user_id", "object_id", "account_id", "sources", "queries"}
SOURCE_FIELDS = {
    "source_id",
    "source_type",
    "date",
    "valid_from",
    "valid_to",
    "relation_key",
    "permission",
}
QUERY_FIELDS = {
    "query_id",
    "query",
    "required_sources",
    "supporting_sources",
    "expected_output",
    "reference_answer",
    "reference_citations",
    "negative_reason",
}
CITATION_FIELDS = {"source_id", "page", "message_id", "record_id"}
ANSWER_OUTPUTS = {"FULL_ANSWER", "CONSTRAINED_ANSWER", "AGGREGATE_RESULT"}
NEGATIVE_REASON_REQUIRED_OUTPUTS = {
    "CLARIFICATION",
    "REFUSE_PERMISSION",
    "REFUSE_INSUFFICIENT_EVIDENCE",
    "REFUSE_NO_MATCH",
    "REFUSE_AGGREGATION_THRESHOLD",
    "REFUSE_CONFLICT",
}
NEGATIVE_REASON_ALLOWED_OUTPUTS = NEGATIVE_REASON_REQUIRED_OUTPUTS | {"CONSTRAINED_ANSWER"}
DEFAULT_REASON_CODES = {
    "FULL_ANSWER": "supported",
    "AGGREGATE_RESULT": "aggregate_threshold_satisfied",
    "METADATA_ONLY": "metadata_only",
}


def _source(
    source_id: str,
    source_type: str,
    relation_key: str,
    *,
    source_date: str | None = None,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "source_type": source_type,
        "date": source_date,
        "valid_from": None,
        "valid_to": None,
        "relation_key": relation_key,
        "permission": "Owner",
    }


def _query(
    query_id: str,
    query: str,
    required_sources: Iterable[str],
    supporting_sources: Iterable[str],
    expected_output: str,
    *,
    reference_answer: str | None = None,
    reference_citations: Iterable[dict[str, Any]] = (),
    negative_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "query_id": query_id,
        "query": query,
        "required_sources": list(required_sources),
        "supporting_sources": list(supporting_sources),
        "expected_output": expected_output,
        "reference_answer": reference_answer,
        # Filled only after the source documents exist and are page/message/record stable.
        "reference_citations": [dict(citation) for citation in reference_citations],
        "negative_reason": negative_reason,
    }


def roadmap_scenario_packs() -> list[dict[str, Any]]:
    """Return the six v1.8 stories without inventing not-yet-authored evidence."""

    s1_sources = (
        "lunara-s3-care-guide",
        "lunara-s3-purchase-receipt",
        "vellum-l2-armchair-care-notes",
        "polarweave-p9-rug-care-guide",
    )
    s2_sources = (
        "s2-tv-manual",
        "s2-tv-purchase-receipt",
        "s2-tv-warranty-terms",
        "s2-tv-product-sheet",
        "s2-tv-regional-service-notice",
        "s2-wrong-device-manual",
    )
    s3_orders = tuple(f"s3-tesco-order-{number:02d}" for number in range(1, 9))
    s4_statements = tuple(f"s4-bank-statement-{number:02d}" for number in range(1, 4))
    s5_sources = (
        "s2-tv-manual",
        "s2-tv-purchase-receipt",
        "s2-tv-warranty-terms",
        "s5-home-insurance-policy",
    )
    s6_sources = (
        "s6-ev-specification",
        "s6-wallbox-datasheet",
        "s6-inverter-datasheet",
        "s6-electrical-connection-description",
    )

    return [
        {
            "scenario_id": "S1_SOFA_01",
            "user_id": "synthetic-user-s1",
            "object_id": "LUN-S3-2401",
            "account_id": None,
            "sources": [
                _source(s1_sources[0], "cleaning_manual_pdf", "LUN-S3-2401"),
                _source(
                    s1_sources[1],
                    "purchase_receipt_pdf",
                    "LUN-S3-2401",
                    source_date="2025-11-14",
                ),
                _source(s1_sources[2], "leather_care_notes_pdf", "ARM-L2-880"),
                _source(s1_sources[3], "rug_care_guide_pdf", "RUG-P9-009"),
            ],
            "queries": [
                _query(
                    "S1-Q1",
                    "I spilled coffee on my sofa. How should I clean it?",
                    [s1_sources[0]],
                    s1_sources[2:],
                    "FULL_ANSWER",
                    reference_answer=(
                        "Blot the spill immediately with a clean white absorbent cloth without rubbing. "
                        "Use 5 mL of neutral liquid soap mixed with 250 mL of lukewarm water, test it "
                        "on a hidden area, dab from the edge toward the centre, remove the soap residue "
                        "with a clean damp cloth, and allow the sofa to air dry."
                    ),
                    reference_citations=(
                        {"source_id": s1_sources[0], "page": 1, "message_id": None, "record_id": None},
                    ),
                ),
                _query(
                    "S1-Q2",
                    "When did I buy this sofa?",
                    [s1_sources[1]],
                    [],
                    "FULL_ANSWER",
                    reference_answer="The sofa was purchased on 14 November 2025.",
                    reference_citations=(
                        {"source_id": s1_sources[1], "page": 1, "message_id": None, "record_id": None},
                    ),
                ),
                _query(
                    "S1-Q3",
                    "Can I use chlorine bleach?",
                    [s1_sources[0]],
                    s1_sources[2:],
                    "FULL_ANSWER",
                    reference_answer="No. The LUNARA S3 care guide explicitly prohibits chlorine bleach on the sofa fabric.",
                    reference_citations=(
                        {"source_id": s1_sources[0], "page": 1, "message_id": None, "record_id": None},
                    ),
                ),
                _query(
                    "S1-Q4",
                    "How long is the manufacturer's warranty?",
                    [],
                    [s1_sources[0], s1_sources[1]],
                    "REFUSE_INSUFFICIENT_EVIDENCE",
                    reference_answer=(
                        "The available sofa care guide and purchase receipt do not state a manufacturer "
                        "warranty duration, so the question cannot be answered from the available evidence."
                    ),
                    negative_reason="insufficient_evidence",
                ),
                _query(
                    "S1-Q5",
                    "How much did I pay for the sofa?",
                    [s1_sources[1]],
                    [],
                    "FULL_ANSWER",
                    reference_answer="The total paid for the sofa was 249,900 HUF.",
                    reference_citations=(
                        {"source_id": s1_sources[1], "page": 1, "message_id": None, "record_id": None},
                    ),
                ),
                _query(
                    "S1-Q6",
                    "Do the care guide and purchase receipt refer to the same sofa?",
                    [s1_sources[0], s1_sources[1]],
                    [],
                    "FULL_ANSWER",
                    reference_answer=(
                        "Yes. Both documents identify the LUNARA S3 three-seat fabric sofa with "
                        "product code LUN-S3-2401."
                    ),
                    reference_citations=(
                        {"source_id": s1_sources[0], "page": 1, "message_id": None, "record_id": None},
                        {"source_id": s1_sources[1], "page": 1, "message_id": None, "record_id": None},
                    ),
                ),
            ],
        },
        {
            "scenario_id": "S2_TV_WARRANTY_01",
            "user_id": "synthetic-user-tv",
            "object_id": "TV-001",
            "account_id": None,
            "sources": [
                _source(s2_sources[0], "user_manual_pdf", "TV-001"),
                _source(s2_sources[1], "purchase_receipt_pdf", "TV-001"),
                _source(s2_sources[2], "warranty_terms_pdf", "TV-001"),
                _source(s2_sources[3], "product_specification_pdf", "TV-001"),
                _source(s2_sources[4], "regional_service_notice_pdf", "TV-001"),
                _source(s2_sources[5], "wrong_object_manual_pdf", "DISPLAY-OTHER-001"),
            ],
            "queries": [
                _query(
                    "S2-Q1",
                    "Which television do I own, when did I purchase it, and what was the price?",
                    [s2_sources[1]],
                    [s2_sources[0]],
                    "FULL_ANSWER",
                    reference_answer=(
                        "You own a Velora V55 Smart TV. It was purchased on 12 March 2025 "
                        "for 319,900 HUF."
                    ),
                    reference_citations=(
                        {"source_id": s2_sources[1], "page": 1, "message_id": None, "record_id": None},
                    ),
                ),
                _query(
                    "S2-Q2",
                    "Is my Velora V55 still covered by the manufacturer warranty on 21 August 2026? "
                    "Explain using the purchase record and the manufacturer warranty terms.",
                    [s2_sources[1], s2_sources[2]],
                    [],
                    "FULL_ANSWER",
                    reference_answer=(
                        "Yes. The television was purchased on 12 March 2025, and the 24-month "
                        "manufacturer warranty ends on 12 March 2027. It is therefore covered "
                        "on 21 August 2026."
                    ),
                    reference_citations=(
                        {"source_id": s2_sources[1], "page": 1, "message_id": None, "record_id": None},
                        {"source_id": s2_sources[2], "page": 2, "message_id": None, "record_id": None},
                    ),
                ),
                _query(
                    "S2-Q3",
                    "My Velora V55 shows error E06 while I am using an HDMI source. "
                    "What does E06 mean, and what should I do first?",
                    [s2_sources[0]],
                    [],
                    "FULL_ANSWER",
                    reference_answer=(
                        "E06 indicates an HDMI handshake or connection failure. First turn off "
                        "and unplug both the television and the HDMI source device for 60 seconds, "
                        "then reconnect them."
                    ),
                    reference_citations=(
                        {"source_id": s2_sources[0], "page": 17, "message_id": None, "record_id": None},
                    ),
                ),
                _query(
                    "S2-Q4",
                    "How many HDMI and USB-A ports does the Velora V55 have, and what other "
                    "wired connections are listed?",
                    [s2_sources[3]],
                    [s2_sources[0]],
                    "FULL_ANSWER",
                    reference_answer=(
                        "The Velora V55 has 4 HDMI inputs, 2 USB-A ports, 1 Ethernet port, "
                        "1 optical audio output and 1 antenna input."
                    ),
                    reference_citations=(
                        {"source_id": s2_sources[3], "page": 3, "message_id": None, "record_id": None},
                    ),
                ),
                _query(
                    "S2-Q5",
                    "Do the documents establish that the 18-month regional service period replaces "
                    "the 24-month manufacturer warranty for my Velora V55? Explain the two periods "
                    "without assuming that one supersedes the other.",
                    [s2_sources[2], s2_sources[4]],
                    [s2_sources[1]],
                    "FULL_ANSWER",
                    reference_answer=(
                        "The documents define a 24-month manufacturer warranty and a separate "
                        "18-month regional service period, both calculated from the retail purchase "
                        "date. They do not state that the regional period replaces or supersedes "
                        "the manufacturer warranty."
                    ),
                    reference_citations=(
                        {"source_id": s2_sources[2], "page": 2, "message_id": None, "record_id": None},
                        {"source_id": s2_sources[4], "page": 1, "message_id": None, "record_id": None},
                    ),
                ),
                _query(
                    "S2-Q6",
                    "For the Velora V55, product code VEL-V55-2025, does error E06 mean a "
                    "temperature-sensor fault as described in the Aster M55 manual, or does it "
                    "mean something else? Use only the matching product documents.",
                    [s2_sources[0]],
                    [s2_sources[5]],
                    "FULL_ANSWER",
                    reference_answer=(
                        "For the Velora V55, E06 concerns HDMI connection negotiation, not a "
                        "temperature-sensor fault. The Aster M55 definition does not apply to "
                        "the Velora product."
                    ),
                    reference_citations=(
                        {"source_id": s2_sources[0], "page": 17, "message_id": None, "record_id": None},
                        {"source_id": s2_sources[0], "page": 20, "message_id": None, "record_id": None},
                    ),
                ),
            ],
        },
        {
            "scenario_id": "S3_TESCO_ORDERS_01",
            "user_id": "synthetic-user-tesco",
            "object_id": None,
            "account_id": "TESCO-ACCOUNT-001",
            "sources": [_source(source_id, "order_confirmation_pdf", "TESCO-ACCOUNT-001") for source_id in s3_orders],
            "queries": [
                _query(
                    "S3-Q1",
                    "Átlagosan hány naponta rendelek tejet?",
                    s3_orders,
                    [],
                    "AGGREGATE_RESULT",
                    reference_answer="A tejet tartalmazó rendelések dátumait rendezni kell, majd az egymást követő dátumok közti napok átlagát kell számítani.",
                ),
                _query(
                    "S3-Q2",
                    "Melyik hónapban rendeltem a legtöbb liter tejet?",
                    s3_orders,
                    [],
                    "AGGREGATE_RESULT",
                    reference_answer="A visszaigazolt tejmennyiséget hónaponként kell összegezni, majd a legnagyobb összeget kiválasztani.",
                ),
                _query(
                    "S3-Q3",
                    "Hányszor rendeltem tejet és kenyeret ugyanabban a kosárban?",
                    s3_orders,
                    [],
                    "AGGREGATE_RESULT",
                    reference_answer="Azokat a rendeléseket kell megszámolni, amelyek terméklistája tejet és kenyeret is tartalmaz.",
                ),
                _query(
                    "S3-Q4",
                    "Ki fogyasztotta el a tejet?",
                    [],
                    s3_orders,
                    "REFUSE_INSUFFICIENT_EVIDENCE",
                    negative_reason="insufficient_evidence",
                ),
            ],
        },
        {
            "scenario_id": "S4_TESCO_BANK_01",
            "user_id": "synthetic-user-tesco",
            "object_id": None,
            "account_id": "TESCO-ACCOUNT-001",
            "sources": [
                *[_source(source_id, "order_confirmation_pdf", "TESCO-ACCOUNT-001") for source_id in s3_orders],
                *[_source(source_id, "bank_statement_pdf", "TESCO-ACCOUNT-001") for source_id in s4_statements],
            ],
            "queries": [
                _query(
                    "S4-Q1",
                    "Mely tejtartalmú rendelések tényleges terhelése tért el a visszaigazolt összegtől, és összesen mennyi volt az eltérés?",
                    [*s3_orders, *s4_statements],
                    [],
                    "AGGREGATE_RESULT",
                    reference_answer="A tejtartalmú rendeléseket rendelésazonosító, dátum és összeg alapján kell a banki terhelésekkel párosítani, majd az eltéréseket összegezni.",
                ),
                _query(
                    "S4-Q2",
                    "Mennyit fizettem ténylegesen azokért a rendelésekért, amelyekben tej volt?",
                    [*s3_orders, *s4_statements],
                    [],
                    "AGGREGATE_RESULT",
                    reference_answer="A tejtartalmat a rendelési PDF-ekből, a tényleges terhelést a párosított banki rekordokból kell venni és összegezni.",
                ),
                _query(
                    "S4-Q3",
                    "Volt olyan visszaigazolt TESCO rendelés, amelyhez nem található banki terhelés?",
                    [*s3_orders, *s4_statements],
                    [],
                    "FULL_ANSWER",
                    reference_answer="A rendelésazonosító, dátum és összeg alapján párosítatlanul maradó rendeléseket kell felsorolni.",
                ),
                _query(
                    "S4-Q4",
                    "Mekkora a TESCO banki terheléseim összege?",
                    s4_statements,
                    s3_orders,
                    "AGGREGATE_RESULT",
                    reference_answer="Csak a bankkivonatok TESCO kereskedőhöz tartozó tényleges terheléseit kell összegezni.",
                ),
            ],
        },
        {
            "scenario_id": "S5_TV_INSURANCE_01",
            "user_id": "synthetic-user-tv",
            "object_id": "HOME-001",
            "account_id": None,
            "sources": [
                _source(s5_sources[0], "user_manual_pdf", "TV-001"),
                _source(s5_sources[1], "purchase_receipt_pdf", "TV-001"),
                _source(s5_sources[2], "warranty_terms_pdf", "TV-001"),
                _source(s5_sources[3], "insurance_policy_pdf", "HOME-001"),
            ],
            "queries": [
                _query("S5-Q1", "A TV E06 hibát ír ki. Mit javasol a kézikönyv első lépésként?", [s5_sources[0]], [], "FULL_ANSWER"),
                _query(
                    "S5-Q2",
                    "Ha a szerviz szerint villám vagy túlfeszültség okozta a hibát, milyen biztosítási fedezet lehet releváns, és milyen igazolás kell?",
                    [s5_sources[3], s5_sources[1]],
                    [],
                    "CONSTRAINED_ANSWER",
                    negative_reason="conditional_evidence",
                ),
                _query(
                    "S5-Q3",
                    "Ha a hiba a garanciális időn belül történt, mely dokumentumok alapján érdemes először garanciát és melyek alapján biztosítást ellenőrizni?",
                    [s5_sources[2], s5_sources[1], s5_sources[3]],
                    [],
                    "CONSTRAINED_ANSWER",
                    negative_reason="conditional_evidence",
                ),
                _query(
                    "S5-Q4",
                    "A biztosító biztosan kifizeti a javítást?",
                    [s5_sources[3]],
                    [s5_sources[1]],
                    "CONSTRAINED_ANSWER",
                    negative_reason="insufficient_evidence",
                ),
            ],
        },
        {
            "scenario_id": "S6_EV_SOLAR_01",
            "user_id": "synthetic-user-s6",
            "object_id": "HOME-001",
            "account_id": None,
            "sources": [
                _source(s6_sources[0], "ev_specification_pdf", "HOME-001"),
                _source(s6_sources[1], "wallbox_datasheet_pdf", "HOME-001"),
                _source(s6_sources[2], "inverter_datasheet_pdf", "HOME-001"),
                _source(s6_sources[3], "electrical_connection_description_pdf", "HOME-001"),
            ],
            "queries": [
                _query("S6-Q1", "Mekkora AC töltési teljesítményt támogat az autóm?", [s6_sources[0]], [], "FULL_ANSWER"),
                _query(
                    "S6-Q2",
                    "Az inverter és a wallbox névleges adatai alapján használható-e a jelenlegi rendszer az autó töltésére?",
                    [s6_sources[2], s6_sources[1], s6_sources[0]],
                    [s6_sources[3]],
                    "FULL_ANSWER",
                ),
                _query(
                    "S6-Q3",
                    "Tölthetem-e az autót közvetlenül a napelem panelről minden köztes berendezés nélkül?",
                    [s6_sources[0], s6_sources[1], s6_sources[2]],
                    [s6_sources[3]],
                    "CONSTRAINED_ANSWER",
                    negative_reason="conditional_evidence",
                ),
                _query(
                    "S6-Q4",
                    "Mennyi idő alatt tölt fel teljesen?",
                    [s6_sources[0]],
                    [],
                    "CLARIFICATION",
                    negative_reason="missing_current_state",
                ),
            ],
        },
    ]


def _issue(severity: str, code: str, path: str, message: str) -> dict[str, str]:
    return {"severity": severity, "code": code, "path": path, "message": message}


def _check_iso_date(value: Any, path: str, issues: list[dict[str, str]]) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str):
        issues.append(_issue("ERROR", "INVALID_DATE", path, "Date value must be an ISO date string or null."))
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        issues.append(_issue("ERROR", "INVALID_DATE", path, "Date value must use YYYY-MM-DD."))
        return None


def _check_exact_fields(value: dict[str, Any], expected: set[str], path: str, issues: list[dict[str, str]]) -> None:
    missing = sorted(expected - set(value))
    extra = sorted(set(value) - expected)
    if missing:
        issues.append(_issue("ERROR", "MISSING_FIELDS", path, f"Missing fields: {', '.join(missing)}."))
    if extra:
        issues.append(_issue("ERROR", "UNEXPECTED_FIELDS", path, f"Unexpected fields: {', '.join(extra)}."))


def validate_scenario_pack(pack: dict[str, Any]) -> list[dict[str, str]]:
    """Validate structural integrity and report honest authoring-readiness gaps."""

    issues: list[dict[str, str]] = []
    if not isinstance(pack, dict):
        return [_issue("ERROR", "INVALID_PACK", "$", "ScenarioPack must be a JSON object.")]
    _check_exact_fields(pack, PACK_FIELDS, "$", issues)
    if issues and any(issue["code"] == "MISSING_FIELDS" for issue in issues):
        return issues

    scenario_id = pack.get("scenario_id")
    if not isinstance(scenario_id, str) or not scenario_id.strip():
        issues.append(_issue("ERROR", "INVALID_SCENARIO_ID", "$.scenario_id", "scenario_id must not be empty."))
    if not isinstance(pack.get("user_id"), str) or not pack["user_id"].strip():
        issues.append(_issue("ERROR", "INVALID_USER_ID", "$.user_id", "user_id must not be empty."))
    identities = [pack.get("object_id"), pack.get("account_id")]
    if sum(isinstance(value, str) and bool(value.strip()) for value in identities) != 1:
        issues.append(_issue("ERROR", "INVALID_LOGICAL_IDENTITY", "$", "Exactly one of object_id or account_id must be set."))

    sources = pack.get("sources")
    queries = pack.get("queries")
    if not isinstance(sources, list):
        issues.append(_issue("ERROR", "INVALID_SOURCES", "$.sources", "sources must be an array."))
        sources = []
    if not isinstance(queries, list):
        issues.append(_issue("ERROR", "INVALID_QUERIES", "$.queries", "queries must be an array."))
        queries = []

    source_ids: set[str] = set()
    for index, source in enumerate(sources):
        path = f"$.sources[{index}]"
        if not isinstance(source, dict):
            issues.append(_issue("ERROR", "INVALID_SOURCE", path, "Source must be an object."))
            continue
        _check_exact_fields(source, SOURCE_FIELDS, path, issues)
        source_id = source.get("source_id")
        if not isinstance(source_id, str) or not source_id.strip():
            issues.append(_issue("ERROR", "INVALID_SOURCE_ID", f"{path}.source_id", "source_id must not be empty."))
        elif source_id in source_ids:
            issues.append(_issue("ERROR", "DUPLICATE_SOURCE_ID", f"{path}.source_id", f"Duplicate source_id: {source_id}."))
        else:
            source_ids.add(source_id)
        if not isinstance(source.get("source_type"), str) or not source["source_type"].strip():
            issues.append(_issue("ERROR", "INVALID_SOURCE_TYPE", f"{path}.source_type", "source_type must not be empty."))
        if not isinstance(source.get("relation_key"), str) or not source["relation_key"].strip():
            issues.append(_issue("ERROR", "INVALID_RELATION_KEY", f"{path}.relation_key", "relation_key must not be empty."))
        if source.get("permission") not in PERMISSIONS:
            issues.append(_issue("ERROR", "INVALID_PERMISSION", f"{path}.permission", "Unsupported permission value."))
        _check_iso_date(source.get("date"), f"{path}.date", issues)
        valid_from = _check_iso_date(source.get("valid_from"), f"{path}.valid_from", issues)
        valid_to = _check_iso_date(source.get("valid_to"), f"{path}.valid_to", issues)
        if valid_from and valid_to and valid_from > valid_to:
            issues.append(_issue("ERROR", "INVALID_VALIDITY_RANGE", path, "valid_from must not be after valid_to."))

    query_ids: set[str] = set()
    for index, query in enumerate(queries):
        path = f"$.queries[{index}]"
        if not isinstance(query, dict):
            issues.append(_issue("ERROR", "INVALID_QUERY", path, "Query must be an object."))
            continue
        _check_exact_fields(query, QUERY_FIELDS, path, issues)
        query_id = query.get("query_id")
        if not isinstance(query_id, str) or not query_id.strip():
            issues.append(_issue("ERROR", "INVALID_QUERY_ID", f"{path}.query_id", "query_id must not be empty."))
        elif query_id in query_ids:
            issues.append(_issue("ERROR", "DUPLICATE_QUERY_ID", f"{path}.query_id", f"Duplicate query_id: {query_id}."))
        else:
            query_ids.add(query_id)
        if not isinstance(query.get("query"), str) or not query["query"].strip():
            issues.append(_issue("ERROR", "INVALID_QUERY_TEXT", f"{path}.query", "query must not be empty."))
        if query.get("expected_output") not in OUTPUT_CLASSES:
            issues.append(_issue("ERROR", "INVALID_EXPECTED_OUTPUT", f"{path}.expected_output", "Unsupported output class."))

        required = query.get("required_sources")
        supporting = query.get("supporting_sources")
        if not isinstance(required, list) or not all(isinstance(item, str) and item for item in required):
            issues.append(_issue("ERROR", "INVALID_REQUIRED_SOURCES", f"{path}.required_sources", "required_sources must contain source IDs."))
            required = []
        if not isinstance(supporting, list) or not all(isinstance(item, str) and item for item in supporting):
            issues.append(_issue("ERROR", "INVALID_SUPPORTING_SOURCES", f"{path}.supporting_sources", "supporting_sources must contain source IDs."))
            supporting = []
        if len(required) != len(set(required)) or len(supporting) != len(set(supporting)):
            issues.append(_issue("ERROR", "DUPLICATE_SOURCE_REFERENCE", path, "Source references must be unique within each list."))
        if set(required) & set(supporting):
            issues.append(_issue("ERROR", "OVERLAPPING_SOURCE_ROLES", path, "A source cannot be both required and supporting."))
        unknown = sorted((set(required) | set(supporting)) - source_ids)
        if unknown:
            issues.append(_issue("ERROR", "UNKNOWN_SOURCE_REFERENCE", path, f"Unknown source IDs: {', '.join(unknown)}."))
        if query.get("expected_output") in ANSWER_OUTPUTS and not required:
            issues.append(_issue("ERROR", "ANSWER_WITHOUT_REQUIRED_SOURCE", path, "Answer outputs require at least one required source."))

        reference_answer = query.get("reference_answer")
        if reference_answer is not None and (not isinstance(reference_answer, str) or not reference_answer.strip()):
            issues.append(_issue("ERROR", "INVALID_REFERENCE_ANSWER", f"{path}.reference_answer", "reference_answer must be a non-empty string or null."))

        negative_reason = query.get("negative_reason")
        if query.get("expected_output") in NEGATIVE_REASON_REQUIRED_OUTPUTS and (
            not isinstance(negative_reason, str) or not negative_reason.strip()
        ):
            issues.append(_issue("ERROR", "MISSING_NEGATIVE_REASON", f"{path}.negative_reason", "This output requires a negative_reason."))
        if query.get("expected_output") not in NEGATIVE_REASON_ALLOWED_OUTPUTS and negative_reason is not None:
            issues.append(_issue("ERROR", "UNEXPECTED_NEGATIVE_REASON", f"{path}.negative_reason", "This output must not have a negative_reason."))

        citations = query.get("reference_citations")
        if not isinstance(citations, list):
            issues.append(_issue("ERROR", "INVALID_REFERENCE_CITATIONS", f"{path}.reference_citations", "reference_citations must be an array."))
            citations = []
        for citation_index, citation in enumerate(citations):
            citation_path = f"{path}.reference_citations[{citation_index}]"
            if not isinstance(citation, dict):
                issues.append(_issue("ERROR", "INVALID_REFERENCE_CITATION", citation_path, "Citation must be an object."))
                continue
            _check_exact_fields(citation, CITATION_FIELDS, citation_path, issues)
            if citation.get("source_id") not in source_ids:
                issues.append(_issue("ERROR", "UNKNOWN_CITATION_SOURCE", f"{citation_path}.source_id", "Citation source must exist in the pack."))
            locators = [citation.get("page"), citation.get("message_id"), citation.get("record_id")]
            if sum(value is not None for value in locators) != 1:
                issues.append(_issue("ERROR", "INVALID_CITATION_LOCATOR", citation_path, "Exactly one page, message_id or record_id is required."))
            page = citation.get("page")
            if page is not None and (not isinstance(page, int) or isinstance(page, bool) or page < 1):
                issues.append(_issue("ERROR", "INVALID_CITATION_PAGE", f"{citation_path}.page", "page must be a positive integer or null."))
            for locator_name in ("message_id", "record_id"):
                locator = citation.get(locator_name)
                if locator is not None and (not isinstance(locator, str) or not locator.strip()):
                    issues.append(_issue("ERROR", "INVALID_CITATION_LOCATOR_VALUE", f"{citation_path}.{locator_name}", f"{locator_name} must be a non-empty string or null."))

        if query.get("expected_output") in ANSWER_OUTPUTS and query.get("reference_answer") is None:
            issues.append(_issue("WARNING", "REFERENCE_ANSWER_PENDING", f"{path}.reference_answer", "Complete after the source document is authored."))
        cited_source_ids = {
            citation.get("source_id")
            for citation in citations
            if isinstance(citation, dict) and isinstance(citation.get("source_id"), str)
        }
        missing_required_citations = sorted(set(required) - cited_source_ids)
        if missing_required_citations:
            issues.append(
                _issue(
                    "WARNING",
                    "REFERENCE_CITATIONS_PENDING",
                    f"{path}.reference_citations",
                    f"Required sources without a stable locator: {', '.join(missing_required_citations)}.",
                )
            )

    if not 4 <= len(sources) <= 10:
        issues.append(_issue("WARNING", "SOURCE_TARGET_GAP", "$.sources", f"Roadmap first-target range is 4-10; this pack has {len(sources)}."))
    if not 6 <= len(queries) <= 12:
        issues.append(_issue("WARNING", "QUERY_TARGET_GAP", "$.queries", f"Roadmap first-target range is 6-12; this pack currently contains its {len(queries)} explicit example questions."))
    return issues


def validate_scenario_catalog(packs: list[dict[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    pack_reports: list[dict[str, Any]] = []
    catalog_issues: list[dict[str, str]] = []
    for pack in packs:
        scenario_id = str(pack.get("scenario_id", ""))
        if scenario_id in seen:
            catalog_issues.append(_issue("ERROR", "DUPLICATE_SCENARIO_ID", "$.scenario_id", f"Duplicate scenario_id: {scenario_id}."))
        seen.add(scenario_id)
        issues = validate_scenario_pack(pack)
        pack_reports.append(
            {
                "scenario_id": scenario_id,
                "source_count": len(pack.get("sources", [])) if isinstance(pack.get("sources"), list) else 0,
                "query_count": len(pack.get("queries", [])) if isinstance(pack.get("queries"), list) else 0,
                "error_count": sum(issue["severity"] == "ERROR" for issue in issues),
                "warning_count": sum(issue["severity"] == "WARNING" for issue in issues),
                "issues": issues,
            }
        )
    if tuple(pack.get("scenario_id") for pack in packs) != SCENARIO_IDS:
        catalog_issues.append(_issue("ERROR", "SCENARIO_SET_MISMATCH", "$", "Catalog must contain S1-S6 once, in roadmap order."))
    error_count = sum(report["error_count"] for report in pack_reports) + sum(issue["severity"] == "ERROR" for issue in catalog_issues)
    warning_count = sum(report["warning_count"] for report in pack_reports) + sum(issue["severity"] == "WARNING" for issue in catalog_issues)
    return {
        "schema_id": SCENARIO_PACK_SCHEMA_ID,
        "status": "INVALID" if error_count else ("STRUCTURALLY_VALID_WITH_READINESS_GAPS" if warning_count else "READY"),
        "scenario_count": len(packs),
        "source_count": sum(report["source_count"] for report in pack_reports),
        "query_count": sum(report["query_count"] for report in pack_reports),
        "error_count": error_count,
        "warning_count": warning_count,
        "catalog_issues": catalog_issues,
        "packs": pack_reports,
    }


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _jsonl_bytes(rows: Iterable[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    ).encode("utf-8")


def _write_known_artifact(path: Path, payload: bytes, *, replace: bool) -> None:
    if path.exists() and path.read_bytes() != payload and not replace:
        raise FileExistsError(f"Refusing to replace changed artifact without --replace: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _projection_blockers(pack: dict[str, Any]) -> list[dict[str, str]]:
    return [
        issue
        for issue in validate_scenario_pack(pack)
        if issue["severity"] == "ERROR"
        or issue["code"] in {"REFERENCE_ANSWER_PENDING", "REFERENCE_CITATIONS_PENDING"}
    ]


def project_scenario_pack(
    pack: dict[str, Any],
    *,
    dataset_version: str = SCENARIO_DATASET_VERSION,
    require_complete_evidence: bool = True,
) -> tuple[list[QueryInput], list[GoldAnnotation]]:
    """Split one authoring pack into runtime-only queries and scorer-only gold."""

    issues = validate_scenario_pack(pack)
    errors = [issue for issue in issues if issue["severity"] == "ERROR"]
    if errors:
        raise ValueError(f"ScenarioPack has {len(errors)} structural validation error(s)")
    blockers = _projection_blockers(pack)
    if require_complete_evidence and blockers:
        locations = ", ".join(sorted({issue["path"] for issue in blockers}))
        raise ValueError(f"ScenarioPack evidence is incomplete; projection refused: {locations}")

    scenario_id = str(pack["scenario_id"])
    policy_fixture_ref = f"{scenario_id}:source-permissions"
    runtime_queries: list[QueryInput] = []
    scorer_gold: list[GoldAnnotation] = []
    for query in pack["queries"]:
        runtime_queries.append(
            QueryInput(
                case_id=query["query_id"],
                evaluation_identity=pack["user_id"],
                query_text=query["query"],
                declared_purpose="grounded_question_answering",
                corpus_package_ref=scenario_id,
                policy_fixture_ref=policy_fixture_ref,
                runtime_parameters={"top_k": 6},
            )
        )
        citations = tuple(dict(item) for item in query["reference_citations"])
        citation_source_ids = [str(item["source_id"]) for item in citations]
        legacy_document_ids = tuple(dict.fromkeys([*query["required_sources"], *citation_source_ids]))
        legacy_page_ranges: dict[str, list[int]] = {}
        for citation in citations:
            page = citation.get("page")
            if page is not None:
                legacy_page_ranges.setdefault(str(citation["source_id"]), []).append(int(page))
        reason_code = query["negative_reason"] or DEFAULT_REASON_CODES.get(
            query["expected_output"], "controlled_output"
        )
        scorer_gold.append(
            GoldAnnotation(
                case_id=query["query_id"],
                expected_output_class=query["expected_output"],
                reason_code=reason_code,
                gold_document_ids=legacy_document_ids,
                gold_page_or_message_ranges=legacy_page_ranges,
                reference_answer=query["reference_answer"],
                factual_atoms=(),
                required_evidence_roles=(),
                action_status="NOT_APPLICABLE",
                dataset_version=dataset_version,
                metadata={
                    "scenario_id": scenario_id,
                    "supporting_sources": list(query["supporting_sources"]),
                    "manual_factual_atom_review_required": True,
                },
                required_sources=tuple(query["required_sources"]),
                reference_citations=citations,
            )
        )
    return runtime_queries, scorer_gold


def write_scenario_pack_projection(
    pack: dict[str, Any],
    output_root: str | Path,
    *,
    dataset_version: str = SCENARIO_DATASET_VERSION,
    replace: bool = False,
) -> dict[str, Any]:
    """Write a complete, gold-blind runtime/scorer projection.

    This is not a corpus builder. The matching source documents are bound to
    the real ingestion/evaluation flow during the corresponding S1-S6 step.
    """

    runtime_queries, scorer_gold = project_scenario_pack(
        pack,
        dataset_version=dataset_version,
        require_complete_evidence=True,
    )
    root = Path(output_root).resolve()
    runtime_relative = Path("runtime") / "query_inputs.jsonl"
    gold_relative = Path("scorer") / "gold_annotations.jsonl"
    runtime_payload = _jsonl_bytes(item.to_dict() for item in runtime_queries)
    gold_payload = _jsonl_bytes(item.to_dict() for item in scorer_gold)
    _write_known_artifact(root / runtime_relative, runtime_payload, replace=replace)
    _write_known_artifact(root / gold_relative, gold_payload, replace=replace)
    manifest = {
        "projection_version": SCENARIO_PROJECTION_VERSION,
        "dataset_version": dataset_version,
        "scenario_id": pack["scenario_id"],
        "query_count": len(runtime_queries),
        "runtime_query_path": runtime_relative.as_posix(),
        "runtime_query_sha256": hashlib.sha256(runtime_payload).hexdigest(),
        "scorer_gold_path": gold_relative.as_posix(),
        "scorer_gold_sha256": hashlib.sha256(gold_payload).hexdigest(),
        "gold_blind_runtime": True,
        "status": "READY_FOR_CORPUS_BINDING",
    }
    _write_known_artifact(root / "projection_manifest.json", _json_bytes(manifest), replace=replace)
    return manifest


def write_scenario_pack_bundle(output_root: str | Path, *, replace: bool = False) -> dict[str, Any]:
    """Write deterministic authoring manifests outside the repository."""

    root = Path(output_root).resolve()
    packs = roadmap_scenario_packs()
    report = validate_scenario_catalog(packs)
    if report["error_count"]:
        raise ValueError("ScenarioPack catalog has structural validation errors")

    index_entries: list[dict[str, Any]] = []
    for pack in packs:
        scenario_id = pack["scenario_id"]
        relative = Path("scenario_packs") / scenario_id / "scenario_pack.json"
        target = root / relative
        payload = _json_bytes(pack)
        _write_known_artifact(target, payload, replace=replace)
        (target.parent / "source_documents").mkdir(parents=True, exist_ok=True)
        index_entries.append(
            {
                "scenario_id": scenario_id,
                "manifest_path": relative.as_posix(),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "source_count": len(pack["sources"]),
                "query_count": len(pack["queries"]),
            }
        )

    index = {
        "schema_id": SCENARIO_PACK_SCHEMA_ID,
        "scenario_count": len(packs),
        "source_count": sum(len(pack["sources"]) for pack in packs),
        "query_count": sum(len(pack["queries"]) for pack in packs),
        "scenarios": index_entries,
    }
    _write_known_artifact(root / "scenario_pack_index.json", _json_bytes(index), replace=replace)
    _write_known_artifact(
        root / "validation_reports" / "scenario_pack_validation.json",
        _json_bytes(report),
        replace=replace,
    )
    return {**index, "validation_status": report["status"], "validation_report": "validation_reports/scenario_pack_validation.json"}
