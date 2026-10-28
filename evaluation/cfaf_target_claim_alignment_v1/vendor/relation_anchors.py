"""Selected pure functions from InfoBank main 8079f29dc3a97273f51b55b2a22f9ff896a2e758. See reuse manifest."""
from __future__ import annotations
import re
from typing import Dict,List
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


def _pattern_hits(text: str, pattern_map: Dict[str, List[str]]) -> List[str]:
    hits: List[str] = []
    for label, patterns in pattern_map.items():
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
            hits.append(label)
    return hits


def claim_relation_signals(text: str) -> List[str]:
    """Return stable relation labels used by evidence and conflict gates."""

    return _pattern_hits(text or "", _CLAIM_RELATION_PATTERNS)

