from __future__ import annotations

from types import SimpleNamespace

import fitz
import pytest

from document_processing import (
    KEYWORD_PROMPT_VERSION,
    PageText,
    ProcessingConfig,
    chunk_pages,
    extract_keywords,
    extract_pdf_pages,
    sha256_text,
)


def make_pdf(*pages: str, metadata: dict[str, str] | None = None) -> bytes:
    document = fitz.open()
    for text in pages:
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text)
    if metadata:
        document.set_metadata(metadata)
    payload = document.tobytes()
    document.close()
    return payload


def test_processing_config_hash_is_stable_and_serializable() -> None:
    first = ProcessingConfig()
    second = ProcessingConfig()
    assert first.to_dict() == second.to_dict()
    assert first.config_hash == second.config_hash
    assert len(first.config_hash) == 64
    changed = ProcessingConfig(chunk_size=800, overlap=100)
    assert changed.config_hash != first.config_hash


@pytest.mark.parametrize(
    ("chunk_size", "overlap"),
    [(0, 0), (-1, 0), (100, -1), (100, 100), (100, 101)],
)
def test_processing_config_rejects_non_progressing_values(chunk_size: int, overlap: int) -> None:
    with pytest.raises(ValueError):
        ProcessingConfig(chunk_size=chunk_size, overlap=overlap)


def test_pdf_extraction_preserves_pages_empty_page_and_metadata() -> None:
    payload = make_pdf("Synthetic television setup guide.", "", "Synthetic warranty summary.", metadata={"title": "Synthetic Guide"})
    extracted = extract_pdf_pages(payload)
    assert extracted.page_count == 3
    assert extracted.empty_page_count == 1
    assert [page.page_number for page in extracted.pages] == [1, 2, 3]
    assert "television" in extracted.pages[0].text.lower()
    assert extracted.pages[1].text == ""
    assert extracted.pdf_metadata["title"] == "Synthetic Guide"


def test_page_chunks_preserve_exact_offsets_overlap_and_never_cross_pages() -> None:
    pages = [PageText(1, "ABCDEFGHIJKLMNO"), PageText(2, "second-page")]
    config = ProcessingConfig(chunk_size=10, overlap=3)
    chunks = chunk_pages("00000000-0000-0000-0000-000000000010", pages, config)
    assert [(chunk.page_number, chunk.char_start, chunk.char_end) for chunk in chunks] == [
        (1, 0, 10),
        (1, 7, 15),
        (2, 0, 10),
        (2, 7, 11),
    ]
    for chunk in chunks:
        source = pages[chunk.page_number - 1].text
        assert chunk.text == source[chunk.char_start:chunk.char_end]
        assert chunk.content_hash == sha256_text(chunk.text)
        assert chunk.config_hash == config.config_hash
    assert chunks[0].text[-3:] == chunks[1].text[:3]


def test_chunk_ids_and_output_are_deterministic() -> None:
    pages = [PageText(1, "A deterministic source text " * 80)]
    first = chunk_pages("00000000-0000-0000-0000-000000000011", pages)
    second = chunk_pages("00000000-0000-0000-0000-000000000011", pages)
    assert first == second
    assert len({chunk.id for chunk in first}) == len(first)


class FailingKeywordClient:
    class Chat:
        class Completions:
            @staticmethod
            def create(**_kwargs):
                raise RuntimeError("synthetic provider failure")

        completions = Completions()

    chat = Chat()


class SuccessfulKeywordClient:
    class Chat:
        class Completions:
            @staticmethod
            def create(**_kwargs):
                message = SimpleNamespace(content="setup, warranty, setup")
                return SimpleNamespace(choices=[SimpleNamespace(message=message)])

        completions = Completions()

    chat = Chat()


def test_keyword_failure_has_reproducible_deterministic_fallback() -> None:
    text = "Synthetic setup setup warranty approval instructions."
    first = extract_keywords(text, client=FailingKeywordClient(), model="mock-model")
    second = extract_keywords(text, client=FailingKeywordClient(), model="mock-model")
    assert first == second
    assert first.mode == "deterministic_fallback"
    assert first.keywords
    assert first.prompt_version == KEYWORD_PROMPT_VERSION
    assert first.warnings == ("keyword_ai_fallback:RuntimeError",)


def test_ai_and_rule_keyword_duplicates_merge_without_losing_provenance() -> None:
    result = extract_keywords("Setup instructions and warranty approval.", client=SuccessfulKeywordClient(), model="mock-model")
    setup = next(item for item in result.assignments if item.value == "setup")
    provenance_types = {item["type"] for item in setup.provenance}
    assert result.mode == "ai_with_rules"
    assert "AI" in provenance_types
    assert "RULE" in provenance_types
