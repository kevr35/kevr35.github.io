"""Run the local climbing editor and save routes directly into the Hugo repo."""

import json
import base64
import io
import re
import subprocess
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
CONTENT = ROOT / "content" / "climbing"
IMAGE_ROOT = ROOT / "static" / "route-images"
LOCATIONS = ROOT / "data" / "climbing" / "locations.yaml"
PORT = 8000
FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*\.md$")


def normalize_filename(value):
    filename = str(value or "").strip()
    if not filename.lower().endswith(".md"):
        filename += ".md"
    return filename


def read_locations():
    locations = []
    current = None
    for line in LOCATIONS.read_text(encoding="utf-8").splitlines():
        if line.startswith("- name:"):
            if current:
                locations.append(current)
            current = {"name": line.split(":", 1)[1].strip().strip('"')}
        elif current and line.strip().startswith("parent:"):
            current["parent"] = line.split(":", 1)[1].strip().strip('"')
        elif current and line.strip().startswith("latitude:"):
            current["latitude"] = line.split(":", 1)[1].strip()
        elif current and line.strip().startswith("longitude:"):
            current["longitude"] = line.split(":", 1)[1].strip()
    if current:
        locations.append(current)
    return locations


def add_location(name, parent, coordinates, level="crag"):
    if not name or not coordinates or not coordinates.get("latitude") or not coordinates.get("longitude"):
        return False
    if any(location["name"].casefold() == name.casefold() for location in read_locations()):
        return False
    with LOCATIONS.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(f'- name: "{name.replace(chr(34), "")}"\n')
        if parent:
            stream.write(f'  parent: "{parent.replace(chr(34), "")}"\n')
        stream.write(f'  latitude: {coordinates["latitude"]}\n  longitude: {coordinates["longitude"]}\n  level: "{level}"\n')
    return True


def ensure_region(name, coordinates):
    if not name or any(location["name"].casefold() == name.casefold() for location in read_locations()):
        return False
    return add_location(name, "", coordinates, "region")


def build_site():
    result = subprocess.run(["hugo", "--minify"], cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout or "Hugo build failed")


def save_route_photos(route_slug, photos):
    if not photos:
        return
    destination = IMAGE_ROOT / route_slug
    destination.mkdir(parents=True, exist_ok=True)
    for index, photo in enumerate(photos, start=1):
        data_url = str(photo.get("data", ""))
        if not data_url.startswith("data:image/") or "," not in data_url:
            raise ValueError("Each route photo must be a browser image upload.")
        _, encoded = data_url.split(",", 1)
        image = Image.open(io.BytesIO(base64.b64decode(encoded)))
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        image.save(destination / f"{index:02d}.jpg", format="JPEG", quality=82, optimize=True)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC), **kwargs)

    def send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/api/climbing/routes":
            self.send_json(404, {"error": "Not found"})
            return
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
            target = CONTENT / filename
            if target.exists() and not overwrite:
                raise FileExistsError(f"{filename} already exists. Enable overwrite to replace it.")
            if payload.get("add_location"):
                coordinates = payload.get("coordinates")
                region_name = str(payload.get("region_name", "")).strip()
                parent = str(payload.get("parent", "")).strip()
                ensure_region(region_name, coordinates)
                add_location(str(payload.get("crag_name", "")).strip(), parent, coordinates)
            save_route_photos(Path(filename).stem, payload.get("photos", []))
            target.write_text(markdown, encoding="utf-8", newline="\n")
            build_site()
            self.send_json(200, {"path": f"content/climbing/{filename}"})
        except FileExistsError as error:
            self.send_json(409, {"error": str(error)})
        except (ValueError, json.JSONDecodeError, OSError, RuntimeError) as error:
            self.send_json(400, {"error": str(error)})

    def do_GET(self):
        if self.path == "/api/climbing/locations":
            self.send_json(200, read_locations())
            return
        super().do_GET()


def main():
    try:
        build_site()
    except RuntimeError as error:
        print(f"Initial Hugo build failed: {error}", file=sys.stderr)
        raise SystemExit(1)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Climbing editor: http://127.0.0.1:{PORT}/admin/climbing/")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping climbing editor.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()