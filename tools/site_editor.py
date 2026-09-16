"""Unified local editor: run this one script to get direct-save Hugo editing
for climbing, publications, and notebooks all from a single local server.

Usage: python tools/site_editor.py
Then open http://127.0.0.1:8000/admin/climbing/, /admin/publications/, or
/admin/notebooks/.
"""

import json
import re
import sys
from http.server import ThreadingHTTPServer

from climbing_editor import Handler as ClimbingHandler, ROOT, PORT, build_site

PUBLICATIONS = ROOT / "content" / "publications"
NOTEBOOKS = ROOT / "content" / "notebooks"
FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*\.md$")


def normalize_filename(value):
    filename = str(value or "").strip()
    if not filename.lower().endswith(".md"):
        filename += ".md"
    return filename


class Handler(ClimbingHandler):
    """Adds direct-save endpoints for publications and notebooks on top of the climbing editor's routes."""

    def do_POST(self):
        if self.path == "/api/publications/entries":
            self.save_markdown_entry(PUBLICATIONS, "publications")
        elif self.path == "/api/notebooks/entries":
            self.save_markdown_entry(NOTEBOOKS, "notebooks")
        else:
            super().do_POST()

    def save_markdown_entry(self, directory, label):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            filename = normalize_filename(payload.get("filename"))
            markdown = payload.get("markdown", "")
            overwrite = bool(payload.get("overwrite"))
            if not FILENAME.fullmatch(filename):
                raise ValueError("Filename must contain only letters, numbers, hyphens, or underscores and end in .md.")
            if not isinstance(markdown, str) or not markdown.startswith("---"):
                raise ValueError("Generated Markdown is invalid.")
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / filename
            if target.exists() and not overwrite:
                raise FileExistsError(f"{filename} already exists. Enable overwrite to replace it.")
            target.write_text(markdown, encoding="utf-8", newline="\n")
            build_site()
            self.send_json(200, {"path": f"content/{label}/{filename}"})
        except FileExistsError as error:
            self.send_json(409, {"error": str(error)})
        except (ValueError, json.JSONDecodeError, OSError, RuntimeError) as error:
            self.send_json(400, {"error": str(error)})


def main():
    try:
        build_site()
    except RuntimeError as error:
        print(f"Initial Hugo build failed: {error}", file=sys.stderr)
        raise SystemExit(1)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Site editor running at http://127.0.0.1:{PORT}/")
    print(f"  Climbing:     http://127.0.0.1:{PORT}/admin/climbing/")
    print(f"  Publications: http://127.0.0.1:{PORT}/admin/publications/")
    print(f"  Notebooks:    http://127.0.0.1:{PORT}/admin/notebooks/")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping site editor.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
