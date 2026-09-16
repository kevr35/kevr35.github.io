"""Publication editor helpers shared by the unified local site editor."""

import json
import re

FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*\.md$")


def normalize_filename(value):
    filename = str(value or "").strip()
    return filename if filename.lower().endswith(".md") else f"{filename}.md"


def validate_markdown_payload(payload):
    filename = normalize_filename(payload.get("filename"))
    markdown = payload.get("markdown", "")
    if not FILENAME.fullmatch(filename):
        raise ValueError("Filename must contain only letters, numbers, hyphens, or underscores and end in .md.")
    if not isinstance(markdown, str) or not markdown.startswith("---"):
        raise ValueError("Generated Markdown is invalid.")
    return filename, markdown, bool(payload.get("overwrite"))


def parse_json_body(raw):
    return json.loads(raw)
