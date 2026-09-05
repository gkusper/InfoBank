from __future__ import annotations

import argparse
import hashlib
import json
import re
import textwrap
from pathlib import Path
from typing import Any

from .fixture_schema import EvaluationFixture, load_fixture


GENERATOR_VERSION = "deterministic-minimal-pdf-v1"


def generate_documents(fixture: EvaluationFixture, output_dir: str | Path) -> dict[str, Any]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    documents: list[dict[str, Any]] = []
    for document in sorted(fixture.documents, key=lambda item: item.alias):
        pdf_name = Path(document.file_name).with_suffix(".pdf").name
        pdf_path = output_dir / pdf_name
        source_hash = sha256_text(document.content)
        pdf_bytes = build_minimal_pdf(document.content, title=document.alias)
        pdf_path.write_bytes(pdf_bytes)
        documents.append(
            {
                "document_alias": document.alias,
                "generated_filename": pdf_name,
                "sha256": sha256_bytes(pdf_bytes),
                "source_text_sha256": source_hash,
                "byte_length": len(pdf_bytes),
            }
        )
    return {
        "fixture_id": fixture.fixture_id,
        "schema_version": fixture.schema_version,
        "generator_version": GENERATOR_VERSION,
        "documents": documents,
    }


def build_minimal_pdf(text: str, title: str = "fixture") -> bytes:
    escaped_title = _pdf_literal(title)
    lines = _wrap_text(text)
    content_lines = ["BT", "/F1 10 Tf", "50 780 Td", "14 TL"]
    for index, line in enumerate(lines):
        if index == 0:
            content_lines.append(f"({_pdf_literal(line)}) Tj")
        else:
            content_lines.append("T*")
            content_lines.append(f"({_pdf_literal(line)}) Tj")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        f"<< /Title ({escaped_title}) /Creator (InfoBank deterministic fixture generator) /CreationDate (D:20260101000000Z) /ModDate (D:20260101000000Z) >>".encode("latin-1"),
    ]
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for obj_num, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{obj_num} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info 6 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(output)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _wrap_text(text: str) -> list[str]:
    clean = re.sub(r"\s+", " ", text).strip()
    return textwrap.wrap(clean, width=86) or [""]


def _pdf_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_manifest(path: str | Path, manifest: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic PDFs for a fixture")
    parser.add_argument("fixture")
    parser.add_argument("--output-dir", default="evaluation/generated_fixtures")
    parser.add_argument("--manifest", default=None)
    args = parser.parse_args(argv)
    manifest = generate_documents(load_fixture(args.fixture), args.output_dir)
    manifest_path = args.manifest or str(Path(args.output_dir) / f"{manifest['fixture_id']}_manifest.json")
    write_manifest(manifest_path, manifest)
    print(f"GENERATED: {len(manifest['documents'])} documents -> {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
