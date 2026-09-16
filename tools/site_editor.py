"""Unified local editor: run this one script to get direct-save Hugo editing
for climbing, publications, and notebooks all from a single local server.

Usage: python tools/site_editor.py
Then open http://127.0.0.1:8000/admin/climbing/, /admin/publications/, or
/admin/notebooks/.
"""

import json
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path

from climbing_tools import Handler as ClimbingHandler, ROOT, PORT, build_site
from notebook_tools import validate_markdown_payload as validate_notebook_payload
from publication_tools import validate_markdown_payload as validate_publication_payload

PUBLICATIONS = ROOT / "content" / "publications"
NOTEBOOKS = ROOT / "content" / "notebooks"


class Handler(ClimbingHandler):
    """Unified local server for climbing, publications, and notebooks."""

    def do_POST(self):
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}:
            self.send_json(403, {"error": "Cross-origin editor requests are not allowed."})
            return
        if self.path == "/api/publications/entries":
            self.save_markdown_entry(PUBLICATIONS, "publications", validate_publication_payload)
        elif self.path == "/api/notebooks/entries":
            self.save_markdown_entry(NOTEBOOKS, "notebooks", validate_notebook_payload)
        else:
            super().do_POST()

    def save_markdown_entry(self, directory: Path, label, validate_payload):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            filename, markdown, overwrite = validate_payload(payload)
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
