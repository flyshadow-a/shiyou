# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _ensure_project_root_on_path() -> None:
    here = Path(__file__).resolve()
    root = here.parents[1] if here.parent.name == "services" else here.parent
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export DOCX to PDF using Word COM.")
    parser.add_argument("--docx", required=True, help="Input docx path")
    parser.add_argument("--pdf", required=True, help="Output pdf path")
    args = parser.parse_args()

    _ensure_project_root_on_path()

    docx_path = Path(args.docx).expanduser().resolve()
    pdf_path = Path(args.pdf).expanduser().resolve()

    if not docx_path.exists():
        print(f"[WordPDF] docx not found: {docx_path}", flush=True)
        return 2

    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from pages.output_special_strategy.report_jinja2_generator import (
            refresh_word_document_fields,
        )

        print(f"[WordPDF] start: {docx_path} -> {pdf_path}", flush=True)

        ok = refresh_word_document_fields(
            docx_path,
            pdf_output_path=pdf_path,
        )

        if not ok:
            print("[WordPDF] refresh_word_document_fields returned False", flush=True)
            return 3

        if not pdf_path.exists():
            print(f"[WordPDF] pdf not created: {pdf_path}", flush=True)
            return 4

        print(f"[WordPDF] success: {pdf_path}", flush=True)
        return 0

    except Exception as exc:
        print(f"[WordPDF] failed: {exc}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())