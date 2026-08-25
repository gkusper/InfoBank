"""Deterministic, page-aware document processing for A-GATE Phase A1."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import statistics
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import fitz


PROCESSING_CONFIG_VERSION = "infocom-a1-v1"
EXTRACTION_METHOD = "PyMuPDF"
EXTRACTION_VERSION = fitz.VersionBind
CHUNKING_STRATEGY = "fixed-characters-within-page"
KEYWORD_PROMPT_VERSION = "keyword-v1"
KEYWORD_PROMPT = (
    "Extract 3 to 5 important English concepts as lowercase single words. "
    "Return only a comma-separated list without commentary."
)
TOKEN_FALLBACK_VERSION = "token-frequency-v1"

STOP_WORDS = {
    "about", "after", "again", "also", "and", "are", "been", "before", "being",
    "between", "can", "document", "for", "from", "has", "have", "into", "its",
    "more", "not", "only", "page", "that", "the", "their", "then", "there", "these",
    "this", "through", "use", "used", "using", "was", "were", "which", "with", "you",
}

RULE_KEYWORDS = {
    "project": [r"\bproject\b"],
    "codename": [r"\bcodename\b", r"\bcode\s*name\b"],
    "action": [r"\baction\b", r"\baction item\b"],
    "deadline": [r"\bdeadline\b", r"\bdue\b", r"\bby\s+20\d{2}-\d{2}-\d{2}\b"],
    "approval": [r"\bapproval\b"],
    "average": [r"\baverage\b", r"\bmean\b"],
    "metadata": [r"\bmetadata\b"],
    "aggregate": [r"\baggregate\b"],
    "browser": [r"\bbrowser\b"],
    "history": [r"\bhistory\b"],
    "ownership": [r"\bownership\b", r"\bowner\b"],
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


@dataclass(frozen=True)
class ProcessingConfig:
    extraction_method: str = EXTRACTION_METHOD
    extraction_version: str = EXTRACTION_VERSION
    page_policy: str = "preserve-pages-skip-empty-chunks"
    chunking_strategy: str = CHUNKING_STRATEGY
    chunk_size: int = 1000
    overlap: int = 200
    separator_policy: str = "character-offsets-no-cross-page"
    keyword_extractor_type: str = "ai-with-deterministic-fallback"
    keyword_prompt_version: str = KEYWORD_PROMPT_VERSION
    keyword_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    config_version: str = PROCESSING_CONFIG_VERSION

    def __post_init__(self) -> None:
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero")
        if self.overlap < 0:
            raise ValueError("overlap must not be negative")
        if self.overlap >= self.chunk_size:
            raise ValueError("overlap must be smaller than chunk_size")
        for name in ("extraction_method", "page_policy", "chunking_strategy", "config_version"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @property
    def config_hash(self) -> str:
        payload = json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return sha256_text(payload)


DEFAULT_PROCESSING_CONFIG = ProcessingConfig()


@dataclass(frozen=True)
class TextBlock:
    block_index: int
    char_start: int
    char_end: int
    text: str


@dataclass(frozen=True)
class PageText:
    page_number: int
    text: str
    blocks: tuple[TextBlock, ...] = ()


@dataclass(frozen=True)
class ExtractedDocument:
    pages: tuple[PageText, ...]
    page_count: int
    empty_page_count: int
    extracted_character_count: int
    pdf_metadata: dict[str, str]


@dataclass(frozen=True)
class StructuredChunk:
    id: str
    document_id: str
    chunk_index: int
    page_number: int
    block_index: int | None
    char_start: int
    char_end: int
    text: str
    content_hash: str
    config_version: str
    config_hash: str

    def chroma_metadata(self) -> dict[str, str | int]:
        metadata: dict[str, str | int] = {
            "document_id": self.document_id,
            "chunk_id": self.id,
            "chunk_index": self.chunk_index,
            "page_number": self.page_number,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "config_hash": self.config_hash,
            "content_hash": self.content_hash,
        }
        if self.block_index is not None:
            metadata["block_index"] = self.block_index
        return metadata


@dataclass(frozen=True)
class KeywordAssignment:
    value: str
    provenance: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class KeywordExtractionResult:
    assignments: tuple[KeywordAssignment, ...]
    mode: str
    model: str | None
    prompt_version: str
    warnings: tuple[str, ...] = ()

    @property
    def keywords(self) -> list[str]:
        return [assignment.value for assignment in self.assignments]


def extract_pdf_pages(content: bytes) -> ExtractedDocument:
    if not content:
        raise ValueError("PDF content must not be empty")
    try:
        pdf = fitz.open(stream=content, filetype="pdf")
    except Exception as exc:
        raise ValueError("The uploaded source is not a readable PDF") from exc
    try:
        pages: list[PageText] = []
        empty_pages = 0
        total_characters = 0
        for page_index, page in enumerate(pdf):
            text = page.get_text("text") or ""
            total_characters += len(text)
            if not text.strip():
                empty_pages += 1
            raw_blocks = sorted(page.get_text("blocks") or [], key=lambda item: (item[1], item[0], item[5]))
            blocks: list[TextBlock] = []
            cursor = 0
            for block_index, block in enumerate(raw_blocks):
                block_text = str(block[4] or "")
                if not block_text:
                    continue
                start = text.find(block_text, cursor)
                if start < 0:
                    start = text.find(block_text)
                if start < 0:
                    continue
                end = start + len(block_text)
                blocks.append(TextBlock(block_index=block_index, char_start=start, char_end=end, text=block_text))
                cursor = end
            pages.append(PageText(page_number=page_index + 1, text=text, blocks=tuple(blocks)))
        metadata = {
            key: str(value).strip()
            for key, value in (pdf.metadata or {}).items()
            if value is not None and str(value).strip()
        }
        return ExtractedDocument(
            pages=tuple(pages),
            page_count=len(pages),
            empty_page_count=empty_pages,
            extracted_character_count=total_characters,
            pdf_metadata=metadata,
        )
    finally:
        pdf.close()


def _block_for_offset(page: PageText, offset: int) -> int | None:
    for block in page.blocks:
        if block.char_start <= offset < block.char_end:
            return block.block_index
    return None


def chunk_pages(
    document_id: str,
    pages: tuple[PageText, ...] | list[PageText],
    config: ProcessingConfig = DEFAULT_PROCESSING_CONFIG,
) -> list[StructuredChunk]:
    config_hash = config.config_hash
    chunks: list[StructuredChunk] = []
    step = config.chunk_size - config.overlap
    for page in pages:
        if not page.text.strip():
            continue
        start = 0
        while start < len(page.text):
            end = min(start + config.chunk_size, len(page.text))
            text = page.text[start:end]
            content_hash = sha256_text(text)
            identity = f"{document_id}:{page.page_number}:{start}:{end}:{content_hash}:{config_hash}"
            chunk_id = str(uuid.uuid5(uuid.NAMESPACE_URL, identity))
            chunks.append(
                StructuredChunk(
                    id=chunk_id,
                    document_id=document_id,
                    chunk_index=len(chunks),
                    page_number=page.page_number,
                    block_index=_block_for_offset(page, start),
                    char_start=start,
                    char_end=end,
                    text=text,
                    content_hash=content_hash,
                    config_version=config.config_version,
                    config_hash=config_hash,
                )
            )
            if end == len(page.text):
                break
            start += step
    return chunks


def _normalize_keyword(value: str) -> str | None:
    normalized = re.sub(r"[^a-z0-9_-]", "", value.strip().lower())
    if not normalized or len(normalized) > 100:
        return None
    return normalized


def deterministic_keyword_candidates(text: str, limit: int = 5) -> list[tuple[str, dict[str, Any]]]:
    lowered = text.lower()
    candidates: list[tuple[str, dict[str, Any]]] = []
    for keyword, patterns in RULE_KEYWORDS.items():
        if any(re.search(pattern, lowered) for pattern in patterns):
            candidates.append((keyword, {"type": "RULE", "method": "routing-rules-v1"}))
    counts: dict[str, int] = {}
    for token in re.findall(r"\b[a-z][a-z0-9_-]{3,}\b", lowered):
        if token not in STOP_WORDS:
            counts[token] = counts.get(token, 0) + 1
    ranked = sorted(counts, key=lambda token: (-counts[token], token))
    existing = {keyword for keyword, _ in candidates}
    for token in ranked:
        if token in existing:
            continue
        candidates.append((token, {"type": "RULE", "method": TOKEN_FALLBACK_VERSION}))
        existing.add(token)
        if len(candidates) >= limit:
            break
    return candidates[:limit]


def merge_keyword_candidates(candidates: list[tuple[str, dict[str, Any]]]) -> tuple[KeywordAssignment, ...]:
    merged: dict[str, list[dict[str, Any]]] = {}
    for raw_value, provenance in candidates:
        value = _normalize_keyword(raw_value)
        if not value:
            continue
        entries = merged.setdefault(value, [])
        canonical = json.dumps(provenance, sort_keys=True, separators=(",", ":"))
        if all(json.dumps(item, sort_keys=True, separators=(",", ":")) != canonical for item in entries):
            entries.append(dict(provenance))
    return tuple(KeywordAssignment(value=value, provenance=tuple(merged[value])) for value in sorted(merged))


def extract_keywords(
    text: str,
    *,
    client: Any | None,
    model: str,
    prompt_version: str = KEYWORD_PROMPT_VERSION,
) -> KeywordExtractionResult:
    rules = deterministic_keyword_candidates(text)
    warnings: list[str] = []
    ai_candidates: list[tuple[str, dict[str, Any]]] = []
    if client is not None:
        try:
            provider_name = str(getattr(client, "provider_name", "compatible-chat"))
            if hasattr(client, "extract_keywords"):
                raw_values = client.extract_keywords(
                    text,
                    model=model,
                    prompt=KEYWORD_PROMPT,
                    prompt_version=prompt_version,
                    limit=5,
                )
            else:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": KEYWORD_PROMPT},
                        {"role": "user", "content": text[:10000]},
                    ],
                    temperature=0.0,
                )
                raw_values = str(response.choices[0].message.content or "").split(",")
            for value in raw_values:
                normalized = _normalize_keyword(value)
                if normalized:
                    ai_candidates.append(
                        (normalized, {"type": "AI", "method": provider_name, "model": model, "prompt_version": prompt_version})
                    )
            if not ai_candidates:
                raise ValueError("AI keyword output contained no valid keywords")
        except Exception as exc:
            warnings.append(f"keyword_ai_fallback:{type(exc).__name__}")
    else:
        warnings.append("keyword_ai_fallback:client_unavailable")
    candidates = ai_candidates + rules
    mode = "ai_with_rules" if ai_candidates else "deterministic_fallback"
    return KeywordExtractionResult(
        assignments=merge_keyword_candidates(candidates),
        mode=mode,
        model=model if ai_candidates else None,
        prompt_version=prompt_version,
        warnings=tuple(warnings),
    )


def processing_statistics(
    *,
    document_id: str,
    source_sha256: str,
    extraction: ExtractedDocument,
    chunks: list[StructuredChunk],
    keywords: KeywordExtractionResult,
    config: ProcessingConfig,
    started_at: float,
) -> dict[str, Any]:
    lengths = [len(chunk.text) for chunk in chunks]
    provenance_counts: dict[str, int] = {}
    for assignment in keywords.assignments:
        for item in assignment.provenance:
            provenance = str(item.get("type", "UNKNOWN"))
            provenance_counts[provenance] = provenance_counts.get(provenance, 0) + 1
    duplicate_count = len(chunks) - len({chunk.content_hash for chunk in chunks})
    return {
        "document_id": document_id,
        "source_sha256": source_sha256,
        "page_count": extraction.page_count,
        "empty_page_count": extraction.empty_page_count,
        "extracted_character_count": extraction.extracted_character_count,
        "keyword_count": len(keywords.assignments),
        "keyword_count_by_provenance": provenance_counts,
        "chunk_count": len(chunks),
        "chunk_length": {
            "mean": statistics.fmean(lengths) if lengths else 0,
            "median": statistics.median(lengths) if lengths else 0,
            "min": min(lengths) if lengths else 0,
            "max": max(lengths) if lengths else 0,
        },
        "duplicate_chunk_count": duplicate_count,
        "processing_config_version": config.config_version,
        "processing_config_hash": config.config_hash,
        "embedding_model": config.embedding_model,
        "keyword_method": keywords.mode,
        "keyword_model": keywords.model,
        "keyword_prompt_version": keywords.prompt_version if keywords.model else None,
        "configured_keyword_prompt_version": config.keyword_prompt_version,
        "processing_duration_ms": round((time.perf_counter() - started_at) * 1000, 3),
        "warnings": list(keywords.warnings),
        "failed_stages": [],
    }
