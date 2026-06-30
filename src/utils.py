from __future__ import annotations

import json
import os
from pathlib import Path

import tiktoken

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
OUTPUT_DIR = PROJECT_ROOT / "output"

DEFAULT_MODEL = "claude-sonnet-4-6"


def load_principles(path: Path | None = None) -> dict:
    path = path or CONFIG_DIR / "principles.json"
    with open(path) as f:
        return json.load(f)


def count_tokens(text: str, model: str = "cl100k_base") -> int:
    enc = tiktoken.get_encoding(model)
    return len(enc.encode(text))


def parse_file(filepath: str | Path) -> str:
    filepath = Path(filepath)
    suffix = filepath.suffix.lower()

    if suffix in (".md", ".txt"):
        return filepath.read_text(encoding="utf-8")

    if suffix == ".pdf":
        import fitz
        doc = fitz.open(str(filepath))
        pages = [page.get_text() for page in doc]
        doc.close()
        return "\n\n".join(pages)

    if suffix == ".docx":
        from docx import Document
        doc = Document(str(filepath))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())

    if suffix == ".json":
        with open(filepath) as f:
            return json.dumps(json.load(f), indent=2)

    return filepath.read_text(encoding="utf-8")


def get_anthropic_client():
    from anthropic import Anthropic
    from dotenv import load_dotenv

    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set. Copy .env.example to .env and add your key.")
    return Anthropic(api_key=api_key)


def guess_source_type(filename: str) -> str:
    name = filename.lower()
    if "transcript" in name:
        return "transcript"
    if "debrief" in name:
        return "debrief"
    if "ba_notes" in name or "ba-notes" in name:
        return "ba_notes"
    if "notes" in name or "interviewer" in name:
        return "interviewer_notes"
    if "pre_interview" in name or "pre-interview" in name:
        return "pre_interview"
    return "client_doc"
