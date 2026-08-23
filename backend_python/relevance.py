"""Usable relevance helpers for the InfoBank RAG pipeline.

This module operationalizes the CITDS 2026 idea that a retrieved source is not
just "similar" to the query. It also has a governance decision and an evidential
role that must be exposed to the generator and the user interface.
"""

import re
from typing import Any, Dict, Iterable, List, Set


SOURCE_ROLE_PRIMARY = "primary"
SOURCE_ROLE_CONTEXTUAL = "contextual"
SOURCE_ROLE_ANALOGICAL = "analogical"
SOURCE_ROLE_CONTRASTIVE = "contrastive"
SOURCE_ROLE_AGGREGATE_ONLY = "aggregate-only"
SOURCE_ROLE_GOVERNANCE_EXCLUDED = "governance-excluded"

USE_FULL = "full"
USE_AGGREGATE = "aggregate"
USE_METADATA = "metadata"
USE_DENY = "deny"

RELEVANCE_LEVELS = [
    "lexical",
    "semantic",
    "ontological",
    "pragmatic",
    "genre",
    "perlocutionary",
    "temporal_status",
    "governance",
    "evidential",
]

_TASK_PATTERNS = {
    "document_inventory": [
        r"\bwhat\s+are\s+my\s+(?:documents?|files?)\b",
        r"\b(?:what|which)\s+(?:documents?|files?)\s+(?:do\s+i\s+have|are\s+(?:uploaded|available)|have\s+i\s+uploaded)\b",
        r"\b(?:show|list)\s+(?:me\s+)?(?:my\s+)?(?:uploaded\s+)?(?:documents?|files?)\b",
        r"\bwhat\s+(?:did|have)\s+i\s+upload(?:ed)?\b",
        r"\b(?:mik|mi)\s+vannak\s+felt[öo]ltve\b",
        r"\b(?:milyen|melyik)\s+dokumentumaim\s+vannak\b",
        r"\b(?:milyen|melyik|mik)\s+(?:dokumentumok|f[aá]jlok|adatok)\s+(?:vannak\s+)?felt[öo]ltve\b",
        r"\b(?:mik|melyek)\s+a\s+(?:felt[öo]lt[öo]tt|saj[aá]t)\s+(?:dokumentumaim|f[aá]jljaim)\b",
        r"\b(?:list[aá]zd|sorold)\s+(?:fel\s+)?(?:a\s+)?(?:felt[öo]lt[öo]tt\s+)?(?:dokumentumaimat|f[aá]jljaimat)\b",
        r"\bmit\s+t[öo]lt[öo]ttem\s+fel\b",
    ],
    "current_action_list": [
        r"\b(todo|to-do|task|action item|action list|current action)\b",
        r"\b(teend[őo]\w*|feladat\w*|aktu[aá]lis teend[őo]\w*|tennival[oó]\w*)\b",
    ],
    "deadline_or_status": [
        r"\b(deadline|due|status|open|closed|current|active)\b",
        r"\b(hat[aá]rid[őo]|st[aá]tusz|nyitott|lez[aá]rt|aktu[aá]lis)\b",
    ],
    "comparison": [
        r"\b(compare|difference|contrast|similar|analogy)\b",
        r"\b(összehasonlít|különbség|hasonló|analógia)\b",
    ],
    "governance_question": [
        r"\b(permission|access|owner|ownership|transfer|aggregate|governance|policy)\b",
        r"\b(jogosultság|tulajdonos|hozzáférés|átadás|aggregált|szabályzat)\b",
    ],
    "document_question_answering": [
        r"\b(what|why|how|when|where|who|mikor|mi[ée]rt|hogyan|hol|ki)\b",
    ],
}

_GENRE_PATTERNS = {
    "manual": [r"\bmanual\b", r"\binstruction\b", r"\bsetup\b", r"\bconfiguration\b"],
    "invoice": [r"\binvoice\b", r"\breceipt\b", r"\breimbursement\b", r"\bpayment\b"],
    "contract": [r"\bcontract\b", r"\bagreement\b", r"\bterms\b"],
    "warning": [r"\bwarning\b", r"\brisk\b", r"\bmust not\b", r"\bprohibited\b"],
    "email_or_message": [r"\bemail\b", r"\bmessage\b", r"\breply\b", r"\bunanswered\b", r"\bthread\b"],
    "calendar_or_schedule": [r"\bcalendar\b", r"\bschedule\b", r"\bdeadline\b", r"\bdue\b", r"\bby 20\d{2}\b"],
    "activity_trace": [r"\bbrowser\b", r"\bhistory\b", r"\bsearch\b", r"\bvisited\b", r"\bactivity trace\b"],
    "statistics": [r"\baverage\b", r"\bmedian\b", r"\bcount\b", r"\bstatistics\b", r"\bpilot\b"],
    "policy": [r"\bpolicy\b", r"\bgovernance\b", r"\bpermission\b", r"\bowner\b", r"\baggregate\b"],
}

_SPEECH_ACT_PATTERNS = {
    "request": [r"\bplease\b", r"\bcould you\b", r"\bcan you\b", r"\brequest\b", r"\basked\b"],
    "assignment": [r"\bassigned\b", r"\bmust\b", r"\brequired\b", r"\bobligation\b", r"\bshould\b"],
    "commitment": [r"\bi will\b", r"\baccepted\b", r"\bcommitted\b", r"\bparticipation\b"],
    "completion": [r"\bcompleted\b", r"\bclosed\b", r"\bdone\b", r"\banswered\b", r"\bsent\b"],
    "cancellation": [r"\bcancelled\b", r"\bcanceled\b", r"\bwithdrawn\b", r"\bnot needed\b"],
    "reminder": [r"\breminder\b", r"\bfollow up\b", r"\boverdue\b"],
}

_TEMPORAL_PATTERNS = {
    "explicit_deadline": [r"\bby\s+20\d{2}-\d{2}-\d{2}\b", r"\bdue\s+20\d{2}-\d{2}-\d{2}\b", r"\bdeadline\b"],
    "open": [r"\bopen\b", r"\bunanswered\b", r"\bpending\b", r"\bcurrent\b", r"\bactive\b"],
    "closed": [r"\bclosed\b", r"\bcompleted\b", r"\bdone\b", r"\bcancelled\b", r"\banswered\b"],
    "recent": [r"\brecent\b", r"\btoday\b", r"\byesterday\b", r"\bthis week\b"],
}

_OBJECT_PATTERNS = {
    "person": r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b",
    "date": r"\b20\d{2}-\d{2}-\d{2}\b",
    "identifier": r"\b[A-Z]{2,}[A-Z0-9\-]{2,}\b",
    "course_or_topic": r"\b(Data Science|database systems|PhD|Ko[sš]ice|InfoBank|RAG)\b",
}

_CONFLICT_SIGNAL_RE = re.compile(
    r"\b(contradict(?:s|ed|ion|ory)?|conflict(?:s|ed|ing)?|unverified|must not override|supersed(?:e|ed|es))\b",
    flags=re.IGNORECASE,
)

# These words describe the existence or administration of a dispute, but not
# the disputed subject.  Excluding them prevents an unrelated conflict notice
# from constraining every question about the same document or object.
_GENERIC_CONFLICT_SCOPE_TERMS = {
    "applies", "approved", "authority", "authoritative", "bulletin", "claim",
    "conflict", "conflicts", "conflicted", "conflicting", "contradict",
    "contradicts", "contradicted", "contradiction", "date", "disagree",
    "document", "effective", "final", "fixture", "latest", "notice", "record",
    "required", "resolve", "service", "source", "states", "superseded", "term",
    "unverified", "version", "warranty",
}

# Claim relations are deliberately small, auditable semantic anchors.  They do
# not replace retrieval similarity; they prevent a matching noun from being
# treated as support for a different predicate (for example, turning a
# warranty exclusion into a claim about what caused damage).
_CLAIM_RELATION_PATTERNS = {
    "causation": [
        r"\bcaus(?:e|es|ed|ing)\b", r"\bresult(?:s|ed|ing)?\s+in\b",
        r"\blead(?:s|ing)?\s+to\b", r"\bokoz(?:za|ott|hat)?\b",
    ],
    "exclusion": [
        r"\bexclud(?:e|es|ed|ing|sion)\b", r"\bnot\s+covered\b",
        r"\boutside\s+(?:the\s+)?(?:warranty|coverage)\b",
        r"\bkiz[aá]r(?:t|va|ás)\b", r"\bnem\s+(?:fedezett|garanci[aá]lis)\b",
    ],
    "coverage": [
        r"\bcover(?:s|ed|age|ing)?\b", r"\bwarranty\s+applies\b",
        r"\bfedez(?:i|ett|et)?\b", r"\bgarancia\s+(?:vonatkozik|kiterjed)\b",
    ],
    "duration": [
        r"\bhow\s+long\b", r"\bduration\b", r"\bwarranty\s+term\b",
        r"\b\d+\s*[- ]?\s*(?:day|days|week|weeks|month|months|year|years)\b",
        r"\b(?:day|days|week|weeks|month|months|year|years)\b",
        r"\bmennyi\s+ideig\b", r"\bid[őo]tartam\b",
        r"\b\d+\s*(?:nap|h[eé]t|h[oó]nap|[ée]v)\b",
    ],
    "requirement": [
        r"\brequir(?:e|es|ed|ement|ements)\b", r"\bmust\b",
        r"\bneed(?:s|ed)?\s+to\b", r"\bprovide\b",
        r"\bsz[üu]ks[ée]ges\b", r"\bkell\b", r"\bmeg\s+kell\b",
    ],
    "price": [
        r"\bprice\b", r"\bcost(?:s|ed)?\b", r"\bhow\s+much\b",
        r"\b[aá]r(?:a|at)?\b", r"\bmennyibe\s+ker[üu]l\b",
    ],
    "purchase_date": [
        r"\bpurchase\s+date\b", r"\bdate\s+of\s+purchase\b",
        r"\bwhen\s+did\s+(?:i|you|we|they)\s+(?:buy|purchase)\b",
        r"\bmikor\s+(?:vettem|vetted|vásároltam|vásároltad)\b",
        r"\bvásárlás\s+dátuma\b",
    ],
}


def _normalize_word(value: str) -> str:
    return re.sub(r"[^\w\-áéíóöőúüűÁÉÍÓÖŐÚÜŰ]+", "", value).lower()


def _pattern_hits(text: str, pattern_map: Dict[str, List[str]]) -> List[str]:
    hits: List[str] = []
    for label, patterns in pattern_map.items():
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
            hits.append(label)
    return hits


def claim_relation_signals(text: str) -> List[str]:
    """Return stable relation labels used by evidence and conflict gates."""

    return _pattern_hits(text or "", _CLAIM_RELATION_PATTERNS)


def extract_lexical_terms(question: str, max_terms: int = 12) -> List[str]:
    """Extract lightweight lexical signals for traceability."""

    stopwords = {
        "the", "and", "or", "to", "of", "in", "on", "for", "a", "an", "is",
        "are", "my", "me", "what", "which", "how", "mi", "milyen", "hogy",
        "hogyan", "az", "a", "egy", "van", "vagy", "és", "nekem", "kell",
    }
    terms: List[str] = []
    for raw in re.findall(r"[\w\-áéíóöőúüűÁÉÍÓÖŐÚÜŰ]+", question):
        term = _normalize_word(raw)
        if len(term) < 3 or term in stopwords:
            continue
        if term not in terms:
            terms.append(term)
        if len(terms) >= max_terms:
            break
    return terms


def extract_entities(text: str) -> Dict[str, List[str]]:
    entities: Dict[str, List[str]] = {}
    for label, pattern in _OBJECT_PATTERNS.items():
        found = []
        for match in re.findall(pattern, text):
            value = match if isinstance(match, str) else " ".join(match)
            if value and value not in found:
                found.append(value)
        if found:
            entities[label] = found[:8]
    return entities


def query_scoped_conflict(chunk_text: str, query_profile: Dict[str, Any], question: str = "") -> Dict[str, Any]:
    """Decide whether a source conflict is about the subject of this query.

    Conflict markers remain conservative evidence signals, but they only defeat
    a claim when the marker-bearing sentence overlaps the query's non-generic
    topic.  An explicit conflict/authority question may also be matched by the
    same object identifier.  The returned trace contains counts and query terms
    only; it never exposes source sentences.
    """

    conflict_sentences = [
        sentence for sentence in re.split(r"(?<=[.!?])\s+|[\r\n]+", chunk_text or "")
        if _CONFLICT_SIGNAL_RE.search(sentence)
    ]
    if not conflict_sentences:
        return {
            "raw_signal": False,
            "query_relevant": False,
            "matched_query_terms": [],
            "matched_claim_relations": [],
            "marker_sentence_count": 0,
        }

    query_identifiers = {
        _normalize_word(value)
        for value in (query_profile.get("entities", {}).get("identifier") or [])
        if _normalize_word(value)
    }
    query_terms = {
        _normalize_word(value)
        for value in [
            *(query_profile.get("lexical_terms") or []),
            *(query_profile.get("semantic_tags") or []),
        ]
        if _normalize_word(value)
    }
    scoped_query_terms = query_terms - query_identifiers - _GENERIC_CONFLICT_SCOPE_TERMS
    marker_terms: Set[str] = set()
    marker_identifiers: Set[str] = set()
    for sentence in conflict_sentences:
        marker_terms.update(_normalize_word(value) for value in re.findall(r"[\w\-áéíóöőúüűÁÉÍÓÖŐÚÜŰ]+", sentence))
        marker_identifiers.update(
            _normalize_word(value)
            for value in extract_entities(sentence).get("identifier", [])
        )
    marker_terms.discard("")
    marker_identifiers.discard("")

    matched_topics = sorted(scoped_query_terms.intersection(marker_terms))
    query_relations = set(claim_relation_signals(question))
    marker_relations = set(claim_relation_signals(" ".join(conflict_sentences)))
    matched_relations = sorted(query_relations.intersection(marker_relations))
    explicit_conflict_question = bool(re.search(
        r"\b(conflict|conflicting|contradict|contradiction|disagree|final authority|authoritative source|which source)\b",
        question or "",
        flags=re.IGNORECASE,
    ))
    identifier_match = bool(query_identifiers.intersection(marker_identifiers))
    query_relevant = bool(
        matched_topics
        or matched_relations
        or (explicit_conflict_question and identifier_match)
    )
    return {
        "raw_signal": True,
        "query_relevant": query_relevant,
        "matched_query_terms": matched_topics[:8],
        "matched_claim_relations": matched_relations,
        "marker_sentence_count": len(conflict_sentences),
    }


def infer_task_intent(question: str) -> str:
    q = question.lower()
    for intent, patterns in _TASK_PATTERNS.items():
        if any(re.search(pattern, q, flags=re.IGNORECASE) for pattern in patterns):
            return intent
    return "general_document_question"


def infer_expected_genres(question: str, task_intent: str) -> List[str]:
    text_genres = _pattern_hits(question, _GENRE_PATTERNS)
    task_genre_defaults = {
        "document_inventory": ["metadata"],
        "current_action_list": ["email_or_message", "calendar_or_schedule", "activity_trace"],
        "deadline_or_status": ["calendar_or_schedule", "email_or_message"],
        "governance_question": ["policy"],
    }
    merged = text_genres + task_genre_defaults.get(task_intent, [])
    return list(dict.fromkeys(merged)) or ["any"]


def build_query_profile(question: str, selected_keywords: Iterable[str]) -> Dict[str, Any]:
    task_intent = infer_task_intent(question)
    return {
        "lexical_terms": extract_lexical_terms(question),
        "semantic_tags": list(selected_keywords),
        "entities": extract_entities(question),
        "task_intent": task_intent,
        "purpose": infer_purpose(task_intent),
        "expected_genres": infer_expected_genres(question, task_intent),
        "required_evidence_strength": infer_required_evidence_strength(task_intent),
        "levels": RELEVANCE_LEVELS,
    }


def infer_purpose(task_intent: str) -> str:
    if task_intent == "document_inventory":
        return "document_inventory"
    if task_intent == "current_action_list":
        return "action_reconstruction"
    if task_intent == "comparison":
        return "comparison_or_analogy"
    if task_intent == "governance_question":
        return "permission_and_policy_reasoning"
    if task_intent == "deadline_or_status":
        return "status_checking"
    return "grounded_question_answering"


def infer_required_evidence_strength(task_intent: str) -> str:
    if task_intent == "document_inventory":
        return "authorized_metadata_sufficient"
    if task_intent in {"current_action_list", "deadline_or_status", "governance_question"}:
        return "primary_required_for_direct_claim"
    if task_intent == "comparison":
        return "primary_or_analogical_with_label"
    return "primary_or_aggregate_with_role_label"


def build_governance_context(
    candidate_doc_ids: Iterable[str],
    direct_permission_doc_ids: Iterable[str],
    aggregate_doc_ids: Iterable[str],
) -> Dict[str, Any]:
    """Assign a use decision and base source role to every candidate document."""

    candidate_set: Set[str] = set(candidate_doc_ids)
    direct_set: Set[str] = set(direct_permission_doc_ids)
    aggregate_set: Set[str] = set(aggregate_doc_ids)
    decisions: Dict[str, str] = {}
    roles: Dict[str, str] = {}

    for doc_id in candidate_set:
        if doc_id in direct_set:
            decisions[doc_id] = USE_FULL
            roles[doc_id] = SOURCE_ROLE_PRIMARY
        elif doc_id in aggregate_set:
            decisions[doc_id] = USE_AGGREGATE
            roles[doc_id] = SOURCE_ROLE_AGGREGATE_ONLY
        else:
            decisions[doc_id] = USE_DENY
            roles[doc_id] = SOURCE_ROLE_GOVERNANCE_EXCLUDED

    usable_doc_ids = [doc_id for doc_id, decision in decisions.items() if decision in {USE_FULL, USE_AGGREGATE}]
    denied_doc_ids = [doc_id for doc_id, decision in decisions.items() if decision == USE_DENY]
    return {
        "use_decisions": decisions,
        "source_roles": roles,
        "usable_doc_ids": usable_doc_ids,
        "denied_doc_ids": denied_doc_ids,
        "has_primary_evidence": any(roles.get(doc_id) == SOURCE_ROLE_PRIMARY for doc_id in usable_doc_ids),
        "has_aggregate_evidence": any(roles.get(doc_id) == SOURCE_ROLE_AGGREGATE_ONLY for doc_id in usable_doc_ids),
    }


def classify_chunk_profile(question: str, chunk_text: str, file_name: str, query_profile: Dict[str, Any], base_role: str, use_decision: str) -> Dict[str, Any]:
    """Compute the full usable-relevance profile for a retrieved chunk."""

    text = f"{file_name}\n{chunk_text}"
    lexical_terms = query_profile.get("lexical_terms", [])
    lexical_hits = [term for term in lexical_terms if term.lower() in text.lower()]
    semantic_tags = query_profile.get("semantic_tags", [])
    semantic_hits = [tag for tag in semantic_tags if tag.lower() in text.lower()]
    genres = _pattern_hits(text, _GENRE_PATTERNS) or ["generic_document"]
    speech_acts = _pattern_hits(text, _SPEECH_ACT_PATTERNS) or ["informative"]
    temporal_signals = _pattern_hits(text, _TEMPORAL_PATTERNS) or ["unspecified"]
    chunk_entities = extract_entities(text)
    query_entities = query_profile.get("entities", {})

    ontological_links = infer_ontological_links(query_entities, chunk_entities, text)
    pragmatic_match = infer_pragmatic_match(query_profile.get("task_intent"), genres, speech_acts, temporal_signals)
    conflict_scope = query_scoped_conflict(chunk_text, query_profile, question)
    conflict_signal = conflict_scope["query_relevant"]
    refined_role = refine_source_role(
        base_role=base_role,
        use_decision=use_decision,
        genres=genres,
        speech_acts=speech_acts,
        temporal_signals=temporal_signals,
        pragmatic_match=pragmatic_match,
        task_intent=query_profile.get("task_intent", "general_document_question"),
        conflict_signal=conflict_signal,
    )
    if conflict_scope["raw_signal"] and not conflict_signal and refined_role == SOURCE_ROLE_PRIMARY:
        # A conflict notice about another claim may be retained as context, but
        # it cannot become primary proof or defeat an unrelated supported claim.
        refined_role = SOURCE_ROLE_CONTEXTUAL

    scores = {
        "lexical": min(1.0, len(lexical_hits) / max(1, len(lexical_terms))),
        "semantic": 1.0 if semantic_hits else (0.35 if semantic_tags else 0.0),
        "ontological": 1.0 if ontological_links else 0.0,
        "pragmatic": 1.0 if pragmatic_match else 0.0,
        "genre": 1.0 if set(genres).intersection(set(query_profile.get("expected_genres", []))) else 0.4,
        "perlocutionary": 1.0 if any(act in speech_acts for act in ["request", "assignment", "commitment", "reminder"]) else 0.25,
        "temporal_status": 1.0 if any(sig in temporal_signals for sig in ["explicit_deadline", "open", "closed", "recent"]) else 0.2,
        "governance": 1.0 if use_decision in {USE_FULL, USE_AGGREGATE} else 0.0,
        "evidential": evidential_score(refined_role),
    }

    return {
        "levels": scores,
        "role": refined_role,
        "base_role": base_role,
        "use_decision": use_decision,
        "lexical_hits": lexical_hits,
        "semantic_hits": semantic_hits,
        "entities": chunk_entities,
        "ontological_links": ontological_links,
        "genre": genres,
        "speech_acts": speech_acts,
        "temporal_status": temporal_signals,
        "pragmatic_match": pragmatic_match,
        "conflict_signal": conflict_signal,
        "conflict_scope": conflict_scope,
        "evidence_warnings": evidence_warnings(
            refined_role,
            use_decision,
            temporal_signals,
            speech_acts,
            incidental_conflict=conflict_scope["raw_signal"] and not conflict_signal,
        ),
    }


def infer_ontological_links(query_entities: Dict[str, List[str]], chunk_entities: Dict[str, List[str]], text: str) -> List[str]:
    links: List[str] = []
    for label, q_values in query_entities.items():
        c_values = chunk_entities.get(label, [])
        overlap = set(q_values).intersection(c_values)
        if overlap:
            links.append(f"same_{label}:" + ",".join(sorted(overlap)))
    relation_keywords = ["manual", "invoice", "warranty", "document", "course", "candidate", "trip", "email", "owner", "project", "codename"]
    for keyword in relation_keywords:
        if keyword in text.lower() and keyword not in links:
            links.append(keyword)
    return links[:8]


def infer_pragmatic_match(task_intent: str, genres: List[str], speech_acts: List[str], temporal_signals: List[str]) -> bool:
    if task_intent == "current_action_list":
        return bool(set(speech_acts).intersection({"request", "assignment", "commitment", "reminder"}) or set(temporal_signals).intersection({"explicit_deadline", "open"}))
    if task_intent == "deadline_or_status":
        return bool(set(temporal_signals).intersection({"explicit_deadline", "open", "closed", "recent"}))
    if task_intent == "governance_question":
        return "policy" in genres or any(act in speech_acts for act in ["assignment", "request"])
    if task_intent == "comparison":
        return True
    return True


def refine_source_role(base_role: str, use_decision: str, genres: List[str], speech_acts: List[str], temporal_signals: List[str], pragmatic_match: bool, task_intent: str = "general_document_question", conflict_signal: bool = False) -> str:
    if use_decision == USE_DENY:
        return SOURCE_ROLE_GOVERNANCE_EXCLUDED
    if use_decision == USE_AGGREGATE:
        return SOURCE_ROLE_AGGREGATE_ONLY
    if use_decision == USE_METADATA:
        return SOURCE_ROLE_CONTEXTUAL

    if conflict_signal:
        return SOURCE_ROLE_CONTRASTIVE

    # For ordinary grounded/factual document QA, a full-access owned source remains
    # primary even if the chunk also contains incidental closed/completed/activity
    # text. Contrastive/contextual downgrades are task-relevant mainly for action
    # reconstruction, status checking, and governance reasoning.
    factual_qa = task_intent in {"general_document_question", "document_question_answering"}
    if factual_qa and base_role == SOURCE_ROLE_PRIMARY and use_decision == USE_FULL and pragmatic_match:
        return SOURCE_ROLE_PRIMARY

    if any(sig in temporal_signals for sig in ["closed"]) or any(act in speech_acts for act in ["completion", "cancellation"]):
        return SOURCE_ROLE_CONTRASTIVE
    if "activity_trace" in genres or not pragmatic_match:
        return SOURCE_ROLE_CONTEXTUAL
    if "manual" in genres and base_role != SOURCE_ROLE_PRIMARY:
        return SOURCE_ROLE_ANALOGICAL
    return base_role


def evidential_score(role: str) -> float:
    return {
        SOURCE_ROLE_PRIMARY: 1.0,
        SOURCE_ROLE_CONTRASTIVE: 0.85,
        SOURCE_ROLE_AGGREGATE_ONLY: 0.65,
        SOURCE_ROLE_CONTEXTUAL: 0.45,
        SOURCE_ROLE_ANALOGICAL: 0.35,
        SOURCE_ROLE_GOVERNANCE_EXCLUDED: 0.0,
    }.get(role, 0.25)


def evidence_warnings(
    role: str,
    use_decision: str,
    temporal_signals: List[str],
    speech_acts: List[str],
    incidental_conflict: bool = False,
) -> List[str]:
    warnings: List[str] = []
    if role == SOURCE_ROLE_AGGREGATE_ONLY:
        warnings.append("aggregate_only_do_not_quote_individual_content")
    if role == SOURCE_ROLE_CONTEXTUAL:
        warnings.append("contextual_support_not_direct_proof")
    if role == SOURCE_ROLE_ANALOGICAL:
        warnings.append("analogical_support_not_direct_proof")
    if role == SOURCE_ROLE_CONTRASTIVE:
        warnings.append("may_close_cancel_or_contradict_an_item")
    if incidental_conflict:
        warnings.append("conflict_marker_outside_query_scope_context_only")
    if use_decision == USE_DENY:
        warnings.append("governance_denied_do_not_use")
    if "closed" in temporal_signals or "completion" in speech_acts or "cancellation" in speech_acts:
        warnings.append("closed_or_cancelled_status_detected")
    return warnings


def make_context_block(source_profile: Dict[str, Any], file_name: str, chunk_text: str) -> str:
    return (
        f"[Source role: {source_profile.get('role')} ]\n"
        f"[Use decision: {source_profile.get('use_decision')}]\n"
        f"[Relevance levels: {source_profile.get('levels')}]\n"
        f"[Genre: {source_profile.get('genre')}]\n"
        f"[Speech acts: {source_profile.get('speech_acts')}]\n"
        f"[Temporal/status: {source_profile.get('temporal_status')}]\n"
        f"[Evidence warnings: {source_profile.get('evidence_warnings')}]\n"
        f"[Source name: {file_name}]\n"
        f"{chunk_text}"
    )


def public_source_text(source_role: str, chunk_text: str) -> str:
    """Return source text that may be shown in the UI."""

    if source_role == SOURCE_ROLE_AGGREGATE_ONLY:
        return "[Aggregate-only source: individual content is hidden; used only as governed aggregate/contextual support.]"
    if source_role == SOURCE_ROLE_GOVERNANCE_EXCLUDED:
        return "[Governance-excluded source: content was not used.]"
    return chunk_text


def summarize_source_roles(sources: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    summary: Dict[str, int] = {}
    for src in sources:
        role = src.get("role", "unknown")
        summary[role] = summary.get(role, 0) + 1
    return summary


def summarize_relevance_levels(sources: Iterable[Dict[str, Any]]) -> Dict[str, float]:
    totals: Dict[str, float] = {level: 0.0 for level in RELEVANCE_LEVELS}
    count = 0
    for src in sources:
        profile = src.get("usable_relevance", {})
        levels = profile.get("levels", {})
        if not levels:
            continue
        count += 1
        for level in RELEVANCE_LEVELS:
            totals[level] += float(levels.get(level, 0.0))
    if count == 0:
        return totals
    return {level: round(value / count, 3) for level, value in totals.items()}
