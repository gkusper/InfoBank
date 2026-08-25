"""Generate privacy-safe synthetic A-GATE Phase A1 owned-object PDFs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import fitz


SOURCES = {
    "synthetic-tv-user-guide.pdf": [
        "SYNTHETIC TEST DOCUMENT\nTelevision setup guide\nConnect the display cable, select the input source, and run channel setup.",
        "SYNTHETIC TEST DOCUMENT\nPicture settings\nUse cinema mode for a dim room and standard mode for a bright room.",
    ],
    "synthetic-quick-start-specification.pdf": [
        "SYNTHETIC TEST DOCUMENT\nQuick start specification\nThe sample device supports two display inputs and one network port.",
    ],
    "synthetic-warranty-record.pdf": [
        "SYNTHETIC TEST DOCUMENT\nWarranty record\nThis fictional device has a twenty-four month demonstration warranty. No real purchase or invoice is represented.",
    ],
}


def build_pdf(pages: list[str]) -> bytes:
    document = fitz.open()
    document.set_metadata(
        {
            "title": "Synthetic InfoBank A-GATE Demonstration",
            "author": "InfoBank deterministic generator",
            "subject": "Privacy-safe generated test data",
            "keywords": "synthetic, test, infobank",
            "creationDate": "D:20260819000000Z",
            "modDate": "D:20260819000000Z",
        }
    )
    for text in pages:
        page = document.new_page(width=595, height=842)
        page.insert_textbox(fitz.Rect(72, 72, 523, 770), text, fontsize=11, fontname="helv")
    try:
        payload = document.tobytes(garbage=4, deflate=True, no_new_id=True)
    except TypeError:
        payload = document.tobytes(garbage=4, deflate=True)
    document.close()
    return payload


def generate(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": "a-gate-owned-object-demo-v1",
        "synthetic": True,
        "final_reviewer_dataset": False,
        "files": [],
    }
    for filename, pages in sorted(SOURCES.items()):
        payload = build_pdf(pages)
        path = output_dir / filename
        path.write_bytes(payload)
        manifest["files"].append(
            {
                "filename": filename,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "byte_size": len(payload),
                "page_count": len(pages),
            }
        )
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/a_gate_demo"))
    args = parser.parse_args()
    manifest = generate(args.output)
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
