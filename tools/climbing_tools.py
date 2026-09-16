"""Climbing-domain helpers and HTTP handlers used by site_editor.py."""

import json
import base64
import csv
import io
import re
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
CONTENT = ROOT / "content" / "climbing"
IMAGE_ROOT = ROOT / "static" / "route-images"
LOCATIONS = ROOT / "data" / "climbing" / "locations.yaml"
IMPORT_OVERRIDES = ROOT / "data" / "climbing" / "import-overrides.json"
PORT = 8000
FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*\.md$")
LOCATION_SEPARATOR = re.compile(r"\s*>\s*")
USER_AGENT = "Mozilla/5.0 (compatible; KevinReissClimbingImporter/1.0)"


def slugify(value):
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")


def clean_location_name(value):
    # Mountain Project prefixes starred/favorited areas with "*" in exports.
    return str(value or "").strip().lstrip("*").strip()


UNSENT_ASCENT_TYPES = {"fell/hung", "attempt"}


def is_unsent_ascent(ascent_type):
    return str(ascent_type or "").strip().casefold() in UNSENT_ASCENT_TYPES


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
        elif current and line.strip().startswith("level:"):
            current["level"] = line.split(":", 1)[1].strip().strip('"')
    if current:
        locations.append(current)
    return locations


LOCATIONS_HEADER = "# Shared state, location, and crag records. Route files reference these by exact name."


def write_locations(blocks):
    lines = [LOCATIONS_HEADER]
    for block in blocks:
        lines.append(f'- name: "{block["name"]}"')
        if block.get("parent"):
            lines.append(f'  parent: "{block["parent"]}"')
        lines.append(f'  latitude: {block["latitude"]}')
        lines.append(f'  longitude: {block["longitude"]}')
        lines.append(f'  level: "{block.get("level", "crag")}"')
    LOCATIONS.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def add_registry_entry(name, parent, coordinates, level="crag"):
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


def ensure_state(name, coordinates):
    if not name or any(location["name"].casefold() == name.casefold() for location in read_locations()):
        return False
    return add_registry_entry(name, "", coordinates, "state")


def ensure_location(name, coordinates, parent=""):
    if not name or any(location["name"].casefold() == name.casefold() for location in read_locations()):
        return False
    return add_registry_entry(name, parent, coordinates, "location")


def state_for_location(location_name, blocks=None):
    """Return the state parent for a registered location, if it has one."""
    if not location_name:
        return ""
    blocks = blocks if blocks is not None else read_locations()
    location = next(
        (block for block in blocks if block["name"].casefold() == location_name.casefold()),
        None,
    )
    return location.get("parent", "") if location and location.get("level") == "location" else ""


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


def existing_route_urls():
    urls = set()
    for path in CONTENT.glob("*.md"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("mountain_project_url:"):
                value = line.split(":", 1)[1].strip().strip('"')
                if value:
                    urls.add(value.split("?")[0].rstrip("/"))
                break
    return urls


def normalize_url(url):
    return str(url or "").strip().split("?")[0].rstrip("/")


def parse_climb_date(value):
    value = str(value or "").strip()
    for fmt in ("%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def hierarchy_key(location, crag):
    return " > ".join(clean_location_name(value).casefold() for value in (location, crag))


def read_import_overrides():
    if not IMPORT_OVERRIDES.exists():
        return {}
    try:
        data = json.loads(IMPORT_OVERRIDES.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def write_import_overrides(overrides):
    IMPORT_OVERRIDES.write_text(json.dumps(overrides, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def known_route_hierarchies():
    return {
        hierarchy_key(location.get("parent", ""), location["name"])
        for location in read_locations()
        if location.get("level") == "crag" and location.get("parent")
    }


def resolve_tick_hierarchy(info, overrides=None, locations=None, route_hierarchies=None):
    source_location = info.get("location", "")
    source_crag = info.get("crag", "")
    key = hierarchy_key(source_location, source_crag)
    result = {"key": key, "source_location": source_location, "source_crag": source_crag}
    if not source_location or not source_crag:
        return result | {"status": "unresolved", "location": source_location, "crag": source_crag}
    override = (overrides or {}).get(key)
    if isinstance(override, dict) and override.get("location") and override.get("crag"):
        return result | {"status": "override", "location": clean_location_name(override["location"]), "crag": clean_location_name(override["crag"])}
    locations = locations if locations is not None else read_locations()
    route_hierarchies = route_hierarchies if route_hierarchies is not None else known_route_hierarchies()
    known_crag = any(
        location["name"].casefold() == source_crag.casefold()
        and location.get("parent", "").casefold() == source_location.casefold()
        for location in locations
    )
    if known_crag or key in route_hierarchies:
        return result | {"status": "matched", "location": source_location, "crag": source_crag}
    return result | {"status": "unresolved", "location": source_location, "crag": source_crag}


def parse_tick_row(row):
    normalized = {str(key).strip().lower(): value for key, value in row.items() if key}

    def get(*names):
        for name in names:
            value = normalized.get(name)
            if value:
                return str(value).strip()
        return ""

    location_raw = get("location")
    segments = [clean_location_name(segment) for segment in LOCATION_SEPARATOR.split(location_raw) if clean_location_name(segment)] if location_raw else []
    # The leading state/country is geographic context, not the climbing destination.
    state = segments[0] if len(segments) >= 3 else ""
    if state:
        segments = segments[1:]
    route_type = get("route type")
    return {
        "title": get("route"),
        "mountain_project_url": get("url"),
        "grade": get("rating", "your rating"),
        "personal_note": get("notes"),
        "climb_date": parse_climb_date(get("date")),
        "ascent_type": get("lead style") or get("style") or "Send",
        "discipline": route_type.split(",")[0].strip() if route_type else "Sport",
        "setting": "Outdoor",
        "state": state,
        "location": segments[0] if len(segments) > 0 else "",
        "crag": segments[1] if len(segments) > 1 else "",
        "wall": " / ".join(segments[2:]) if len(segments) > 2 else "",
    }


def fetch_route_coordinates(url):
    try:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=10) as response:
            html = response.read().decode("utf-8", errors="ignore")
        # The GPS label and its value sit in separate table cells, e.g. "GPS:</td><td>43.8, -71.8".
        match = re.search(r"GPS:\s*(?:<[^>]*>\s*)*(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)", html)
        if match:
            return {"latitude": match.group(1), "longitude": match.group(2)}
    except (urllib.error.URLError, OSError, TimeoutError):
        pass
    return None


def fetch_route_breadcrumb(url):
    """Return Mountain Project's ordered area breadcrumb for a route page."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=10) as response:
        html = response.read().decode("utf-8", errors="ignore")
    crumbs = []
    for label in re.findall(r'href="/area/[^\"]+"[^>]*>(.*?)</a>', html, re.DOTALL):
        name = clean_location_name(re.sub(r"<[^>]+>", "", label))
        if name and name not in crumbs:
            crumbs.append(name)
    return crumbs


def read_frontmatter_value(text, name):
    match = re.search(rf'(?m)^{re.escape(name)}:\s*(.*)$', text)
    if not match:
        return ""
    raw = match.group(1).strip()
    if raw.startswith('"'):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw.strip('"')
    return raw


def clean_route_frontmatter_names(path):
    """Return route text with stray '*' prefixes cleaned without writing the route."""
    text = path.read_text(encoding="utf-8")
    updated = text
    for field in ("state", "location", "crag", "wall"):
        match = re.search(rf'(?m)^{field}:\s*"([^"]*)"\s*$', updated)
        if not match:
            continue
        cleaned = clean_location_name(match.group(1))
        if cleaned != match.group(1):
            updated = updated[: match.start(1)] + cleaned + updated[match.end(1) :]
    return updated


def rebuild_location_registry():
    """Scan every saved route, clean up stray naming issues, and add any missing crags/locations to locations.yaml."""
    crags = {}
    for path in sorted(CONTENT.glob("*.md")):
        text = clean_route_frontmatter_names(path)
        crag = clean_location_name(read_frontmatter_value(text, "crag"))
        url = read_frontmatter_value(text, "mountain_project_url").strip()
        if not crag or not url:
            continue
        registry_crag = next((entry for entry in read_locations() if entry["name"].casefold() == crag.casefold()), None)
        location = registry_crag.get("parent", "") if registry_crag else ""
        state = state_for_location(location)
        crags.setdefault(crag.casefold(), {"name": crag, "state": state, "location": location, "url": url})
    known_names = {location["name"].casefold() for location in read_locations()}
    added, failed = [], []
    for crag in crags.values():
        if crag["name"].casefold() in known_names:
            continue
        if not crag["location"] or not crag["state"]:
            failed.append(f'{crag["name"]} (parent location/state must be verified in the editor)')
            continue
        coordinates = fetch_route_coordinates(crag["url"])
        if not coordinates:
            failed.append(crag["name"])
            continue
        if crag["state"] and crag["state"].casefold() not in known_names:
            if ensure_state(crag["state"], coordinates):
                known_names.add(crag["state"].casefold())
        if crag["location"] and crag["location"].casefold() not in known_names:
            if ensure_location(crag["location"], coordinates, crag["state"]):
                known_names.add(crag["location"].casefold())
        if add_registry_entry(crag["name"], crag["location"], coordinates):
            known_names.add(crag["name"].casefold())
            added.append(crag["name"])
        time.sleep(0.4)
    return added, failed


ROUTE_SUMMARY_FIELDS = ("title", "crag", "wall", "grade")
ROUTE_EDIT_FIELDS = (
    "title", "climb_date", "crag", "wall", "discipline", "setting",
    "grade", "ascent_type", "mountain_project_url", "youtube_url", "personal_note",
)


def route_summary(path):
    text = path.read_text(encoding="utf-8")
    summary = {name: read_frontmatter_value(text, name) for name in ROUTE_SUMMARY_FIELDS}
    summary["filename"] = path.name
    return summary


def route_detail(path):
    text = path.read_text(encoding="utf-8")
    detail = {name: read_frontmatter_value(text, name) for name in ROUTE_EDIT_FIELDS}
    detail["draft"] = read_frontmatter_value(text, "draft") == "true"
    detail["filename"] = path.name
    parts = text.split("---", 2)
    detail["body"] = parts[2].strip() if len(parts) >= 3 else ""
    return detail


def crag_usage(name):
    """Count how many routes use a crag, broken down by their "wall" value, to help decide a split."""
    walls = {}
    total = 0
    for path in sorted(CONTENT.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        crag = clean_location_name(read_frontmatter_value(text, "crag"))
        if crag.casefold() != name.casefold():
            continue
        total += 1
        wall = clean_location_name(read_frontmatter_value(text, "wall")) or "(no wall set)"
        walls[wall] = walls.get(wall, 0) + 1
    ranked = sorted(walls.items(), key=lambda item: -item[1])
    return {"total": total, "walls": [{"value": value, "count": count} for value, count in ranked]}


def relocate_routes(payload):
    """Rename or split a crag: point every matching route at a new/renamed crag, keeping locations.yaml in sync.

    Matching routes are those with the given old_crag, optionally narrowed to
    ones whose "wall" contains wall_filter — this is what lets a lumped-together
    crag (all "wall" values distinct, "crag" identical) be split apart one
    real sub-crag at a time.
    """
    old_crag = clean_location_name(payload.get("old_crag"))
    new_crag = clean_location_name(payload.get("new_crag"))
    wall_filter = clean_location_name(payload.get("wall_filter", "")).casefold()
    parent_override = clean_location_name(payload.get("parent", ""))
    latitude = str(payload.get("latitude") or "").strip()
    longitude = str(payload.get("longitude") or "").strip()
    if not old_crag or not new_crag:
        raise ValueError("Old and new crag names are required.")

    matched_paths, all_old_paths = [], []
    for path in sorted(CONTENT.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        crag = clean_location_name(read_frontmatter_value(text, "crag"))
        if crag.casefold() != old_crag.casefold():
            continue
        all_old_paths.append(path)
        wall = clean_location_name(read_frontmatter_value(text, "wall"))
        if wall_filter and wall_filter not in wall.casefold():
            continue
        matched_paths.append(path)

    if not matched_paths:
        suffix = f' matching wall "{payload.get("wall_filter")}"' if wall_filter else ""
        raise ValueError(f'No routes found at "{old_crag}"{suffix}.')

    blocks = read_locations()
    by_name = {block["name"].casefold(): block for block in blocks}
    old_block = by_name.get(old_crag.casefold())
    new_block = by_name.get(new_crag.casefold())
    is_full_move = len(matched_paths) == len(all_old_paths)

    resolved_parent = parent_override or (new_block or {}).get("parent") or (old_block or {}).get("parent", "")
    resolved_latitude = latitude or (new_block or {}).get("latitude") or (old_block or {}).get("latitude")
    resolved_longitude = longitude or (new_block or {}).get("longitude") or (old_block or {}).get("longitude")
    if not resolved_latitude or not resolved_longitude:
        raise ValueError("Provide latitude/longitude for the new crag; there are no existing coordinates to reuse.")

    if is_full_move and old_block and not new_block:
        old_block["name"] = new_crag
        if resolved_parent:
            old_block["parent"] = resolved_parent
        old_block["latitude"] = resolved_latitude
        old_block["longitude"] = resolved_longitude
        old_block.setdefault("level", "crag")
    elif new_block:
        if resolved_parent:
            new_block["parent"] = resolved_parent
        new_block["latitude"] = resolved_latitude
        new_block["longitude"] = resolved_longitude
    else:
        blocks.append({
            "name": new_crag,
            "parent": resolved_parent,
            "latitude": resolved_latitude,
            "longitude": resolved_longitude,
            "level": "crag",
        })
    write_locations(blocks)

    resolved_state = state_for_location(resolved_parent, blocks)

    for path in matched_paths:
        text = path.read_text(encoding="utf-8")
        text = re.sub(r'(?m)^crag: "([^"]*)"', f'crag: "{new_crag}"', text, count=1)
        wall_match = re.search(r'(?m)^wall: "([^"]*)"', text)
        if wall_match and wall_match.group(1).casefold() == new_crag.casefold():
            text = re.sub(r'(?m)^wall: "([^"]*)"', 'wall: ""', text, count=1)
        path.write_text(text, encoding="utf-8", newline="\n")

    return {
        "routes_updated": len(matched_paths),
        "remaining_at_old_crag": len(all_old_paths) - len(matched_paths),
        "crag_name": new_crag,
    }


def update_hierarchy_node(payload):
    old_name = clean_location_name(payload.get("old_name"))
    new_name = clean_location_name(payload.get("name"))
    parent = clean_location_name(payload.get("parent", ""))
    latitude = str(payload.get("latitude", "")).strip()
    longitude = str(payload.get("longitude", "")).strip()
    if not old_name or not new_name:
        raise ValueError("Choose a hierarchy node and give it a name.")

    blocks = read_locations()
    node = next((block for block in blocks if block["name"].casefold() == old_name.casefold()), None)
    if not node:
        raise ValueError(f'Location "{old_name}" is not in the registry.')
    level = node.get("level", "crag")
    if level not in {"state", "location", "crag"}:
        raise ValueError("Only state, location, and crag nodes can be edited.")
    if any(block["name"].casefold() == new_name.casefold() and block is not node for block in blocks):
        raise ValueError(f'A location named "{new_name}" already exists.')
    parent_node = next((block for block in blocks if block["name"].casefold() == parent.casefold()), None) if parent else None
    if parent and not parent_node:
        raise ValueError(f'Parent "{parent}" is not in the registry.')
    if parent and parent_node is node:
        raise ValueError("A location cannot be its own parent.")
    if level == "state" and parent:
        raise ValueError("A state cannot have a parent location.")
    if level == "location" and (not parent_node or parent_node.get("level", "crag") != "state"):
        raise ValueError("Every location must have a state as its parent.")
    if level == "crag" and (not parent_node or parent_node.get("level", "crag") != "location"):
        raise ValueError("Every crag must have a location as its parent.")
    if latitude or longitude:
        if not latitude or not longitude:
            raise ValueError("Latitude and longitude must be provided together.")
        try:
            latitude_value = float(latitude)
            longitude_value = float(longitude)
        except ValueError as error:
            raise ValueError("Latitude and longitude must be numeric.") from error
        if not -90 <= latitude_value <= 90 or not -180 <= longitude_value <= 180:
            raise ValueError("Latitude must be between -90 and 90; longitude must be between -180 and 180.")
        node["latitude"] = latitude
        node["longitude"] = longitude

    # Walk upward from the proposed parent to prevent a hierarchy cycle.
    ancestor = parent_node
    while ancestor:
        if ancestor is node:
            raise ValueError("That parent would create a hierarchy cycle.")
        ancestor_name = ancestor.get("parent", "")
        ancestor = next((block for block in blocks if block["name"].casefold() == ancestor_name.casefold()), None) if ancestor_name else None

    old_name_lower = old_name.casefold()
    node["name"] = new_name
    if level != "state":
        node["parent"] = parent
    else:
        node.pop("parent", None)
    for block in blocks:
        if block is not node and block.get("parent", "").casefold() == old_name_lower:
            block["parent"] = new_name

    route_updates = []
    descendant_names = {new_name.casefold()}
    changed = True
    while changed:
        changed = False
        for block in blocks:
            if block.get("parent", "").casefold() in descendant_names and block["name"].casefold() not in descendant_names:
                descendant_names.add(block["name"].casefold())
                changed = True
    for path in sorted(CONTENT.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        original_crag = read_frontmatter_value(text, "crag")
        uses_crag = original_crag.casefold() == old_name_lower
        in_branch = original_crag.casefold() in descendant_names
        if not (uses_crag or in_branch):
            continue
        updated = text
        if uses_crag:
            updated = re.sub(r'(?m)^crag: "[^"]*"', f'crag: "{new_name}"', updated, count=1)
        route_updates.append((path, updated))

    write_locations(blocks)
    for path, text in route_updates:
        path.write_text(text, encoding="utf-8", newline="\n")
    return {"node": new_name, "level": level, "routes_updated": len(route_updates)}


def delete_hierarchy_node(payload):
    name = clean_location_name(payload.get("name"))
    if not name:
        raise ValueError("Choose a hierarchy node to delete.")

    blocks = read_locations()
    node = next((block for block in blocks if block["name"].casefold() == name.casefold()), None)
    if not node:
        raise ValueError(f'Location "{name}" is not in the registry.')
    children = [block for block in blocks if block.get("parent", "").casefold() == name.casefold()]
    route_files = []
    for path in sorted(CONTENT.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if read_frontmatter_value(text, "crag").casefold() == name.casefold():
            route_files.append(path.name)
    if children:
        raise ValueError(f'Cannot delete "{name}" because it has {len(children)} child record(s).')
    if route_files:
        raise ValueError(f'Cannot delete "{name}" because {len(route_files)} route(s) still use it.')

    write_locations([block for block in blocks if block is not node])
    return {"node": name, "level": node.get("level", "crag")}


def refresh_location_coordinates(payload):
    location_name = clean_location_name(payload.get("name"))
    if not location_name:
        raise ValueError("Choose a location to refresh.")
    blocks = read_locations()
    location = next((block for block in blocks if block["name"].casefold() == location_name.casefold()), None)
    if not location or location.get("level") != "location":
        raise ValueError("Coordinate refresh is available for locations only.")
    crags = [block for block in blocks if block.get("parent", "").casefold() == location["name"].casefold() and block.get("level") == "crag"]
    route_urls = {}
    for path in CONTENT.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        crag = read_frontmatter_value(text, "crag").casefold()
        url = normalize_url(read_frontmatter_value(text, "mountain_project_url"))
        if crag and url and crag not in route_urls:
            route_urls[crag] = url
    updated, failed = [], []
    for crag in crags:
        url = route_urls.get(crag["name"].casefold())
        coordinates = fetch_route_coordinates(url) if url else None
        if not coordinates:
            failed.append(crag["name"])
            continue
        crag["latitude"] = coordinates["latitude"]
        crag["longitude"] = coordinates["longitude"]
        updated.append(crag["name"])
        time.sleep(0.4)
    if updated:
        write_locations(blocks)
    return {"location": location["name"], "updated": updated, "failed": failed}


def create_hierarchy_node(payload):
    name = clean_location_name(payload.get("name"))
    level = clean_location_name(payload.get("level"))
    parent = clean_location_name(payload.get("parent", ""))
    latitude = str(payload.get("latitude", "")).strip()
    longitude = str(payload.get("longitude", "")).strip()
    if level not in {"state", "location", "crag"} or not name:
        raise ValueError("Choose a valid hierarchy level and name.")
    if level != "state" and not parent:
        raise ValueError("A location or crag must have a parent.")
    if level == "state" and parent:
        raise ValueError("A state cannot have a parent.")
    try:
        latitude_value = float(latitude)
        longitude_value = float(longitude)
    except ValueError as error:
        raise ValueError("Latitude and longitude are required and must be numeric.") from error
    if not -90 <= latitude_value <= 90 or not -180 <= longitude_value <= 180:
        raise ValueError("Latitude must be between -90 and 90; longitude must be between -180 and 180.")
    blocks = read_locations()
    if any(block["name"].casefold() == name.casefold() for block in blocks):
        raise ValueError(f'A hierarchy node named "{name}" already exists.')
    parent_node = next((block for block in blocks if block["name"].casefold() == parent.casefold()), None) if parent else None
    expected_parent = {"location": "state", "crag": "location"}.get(level)
    if expected_parent and (not parent_node or parent_node.get("level") != expected_parent):
        raise ValueError(f"A {level} must have a {expected_parent} parent.")
    blocks.append({"name": name, "parent": parent, "latitude": latitude, "longitude": longitude, "level": level})
    write_locations(blocks)
    return {"node": name, "level": level}


def build_route_markdown(fields):
    def q(value):
        return json.dumps(str(value or ""))

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    draft = "true" if is_unsent_ascent(fields.get("ascent_type")) else "false"
    lines = [
        "---",
        f'title: {q(fields.get("title"))}',
        f"date: {stamp}",
        f'climb_date: {q(fields.get("climb_date"))}',
        f'crag: {q(fields.get("crag"))}',
        f'wall: {q(fields.get("wall"))}',
        f'discipline: {q(fields.get("discipline"))}',
        f'setting: {q(fields.get("setting", "Outdoor"))}',
        f'grade: {q(fields.get("grade"))}',
        f'ascent_type: {q(fields.get("ascent_type"))}',
        f'mountain_project_url: {q(fields.get("mountain_project_url"))}',
        'youtube_url: ""',
        'thumbnail: ""',
        "photos: []",
        f'personal_note: {q(fields.get("personal_note"))}',
        "tags:",
        '  - "Climbing"',
        f"draft: {draft}",
        "---",
        "",
        "",
    ]
    return "\n".join(lines)


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
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}:
            self.send_json(403, {"error": "Cross-origin editor requests are not allowed."})
            return
        if self.path == "/api/climbing/routes":
            self.handle_save_route()
        elif self.path == "/api/climbing/preview-ticks":
            self.handle_preview_ticks()
        elif self.path == "/api/climbing/import-ticks":
            self.handle_import_ticks()
        elif self.path == "/api/climbing/rebuild-locations":
            self.handle_rebuild_locations()
        elif self.path == "/api/climbing/relocate-routes":
            self.handle_relocate_routes()
        elif self.path == "/api/climbing/hierarchy-node":
            self.handle_hierarchy_node()
        elif self.path == "/api/climbing/delete-hierarchy-node":
            self.handle_delete_hierarchy_node()
        elif self.path == "/api/climbing/create-hierarchy-node":
            self.handle_create_hierarchy_node()
        elif self.path == "/api/climbing/refresh-location-coordinates":
            self.handle_refresh_location_coordinates()
        else:
            self.send_json(404, {"error": "Not found"})

    def handle_save_route(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            filename = normalize_filename(payload.get("filename"))
            markdown = payload.get("markdown", "")
            original_filename = payload.get("original_filename")
            overwrite = bool(payload.get("overwrite")) or bool(original_filename)
            if not FILENAME.fullmatch(filename):
                raise ValueError("Filename must contain only letters, numbers, hyphens, or underscores and end in .md.")
            if not isinstance(markdown, str) or not markdown.startswith("---"):
                raise ValueError("Generated Markdown is invalid.")
            frontmatter_match = re.match(r"\A---\s*\n(.*?)\n---(?:\s|$)", markdown, re.DOTALL)
            if not frontmatter_match:
                raise ValueError("Generated Markdown front matter is invalid.")
            frontmatter = frontmatter_match.group(1)
            frontmatter = re.sub(r'(?m)^(state|location|region|area):.*\r?\n', "", frontmatter)
            markdown = markdown[: frontmatter_match.start(1)] + frontmatter + markdown[frontmatter_match.end(1) :]
            if not re.search(r'(?m)^crag:\s*"[^"]+"\s*$', frontmatter):
                raise ValueError("A crag is required for every route.")
            crag_match = re.search(r'(?m)^crag:\s*"([^"]+)"\s*$', frontmatter)
            registered_crag = next((entry for entry in read_locations() if entry.get("name", "").casefold() == crag_match.group(1).casefold()), None)
            if not registered_crag or registered_crag.get("level") != "crag":
                if not payload.get("add_crag"):
                    raise ValueError("This crag is not in the shared registry. Verify its parent state and location, then enable adding it.")
            target = CONTENT / filename
            if target.exists() and not overwrite:
                raise FileExistsError(f"{filename} already exists. Enable overwrite to replace it.")
            if payload.get("add_crag"):
                coordinates = payload.get("coordinates")
                state_name = str(payload.get("state_name", "")).strip()
                location_name = str(payload.get("location_name", "")).strip()
                parent = str(payload.get("parent", "")).strip()
                crag_name = str(payload.get("crag_name", "")).strip()
                if not state_name or not location_name or not parent or not crag_name or not coordinates:
                    raise ValueError("Verify the imported state, location, crag, and coordinates before adding them to the registry.")
                registry = read_locations()
                state = next((entry for entry in registry if entry["name"].casefold() == state_name.casefold()), None)
                location = next((entry for entry in registry if entry["name"].casefold() == location_name.casefold()), None)
                if not state or state.get("level") != "state" or not location or location.get("level") != "location" or location.get("parent", "").casefold() != state["name"].casefold():
                    raise ValueError("Create and verify the state and parent location in the hierarchy editor before saving this route.")
                existing_crag = next((entry for entry in registry if entry["name"].casefold() == crag_name.casefold()), None)
                if existing_crag:
                    if existing_crag.get("level") != "crag" or existing_crag.get("parent", "").casefold() != parent.casefold():
                        raise ValueError("The approved crag has a different parent. Check the hierarchy editor before saving.")
                elif not add_registry_entry(crag_name, parent, coordinates):
                    raise ValueError("The crag could not be added. Verify its name and parent in the hierarchy editor first.")
            save_route_photos(Path(filename).stem, payload.get("photos", []))
            target.write_text(markdown, encoding="utf-8", newline="\n")
            if original_filename:
                original_filename = normalize_filename(original_filename)
                if FILENAME.fullmatch(original_filename):
                    original_path = CONTENT / original_filename
                    if original_path.exists() and original_path != target:
                        original_path.unlink()
            build_site()
            self.send_json(200, {"path": f"content/climbing/{filename}"})
        except FileExistsError as error:
            self.send_json(409, {"error": str(error)})
        except (ValueError, json.JSONDecodeError, OSError, RuntimeError) as error:
            self.send_json(400, {"error": str(error)})

    def handle_relocate_routes(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            result = relocate_routes(payload)
            build_site()
            self.send_json(200, result)
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(400, {"error": str(error)})
        except RuntimeError as error:
            self.send_json(500, {"error": str(error)})

    def handle_hierarchy_node(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            result = update_hierarchy_node(json.loads(self.rfile.read(length)))
            build_site()
            self.send_json(200, result)
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(400, {"error": str(error)})
        except RuntimeError as error:
            self.send_json(500, {"error": str(error)})

    def handle_delete_hierarchy_node(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            result = delete_hierarchy_node(json.loads(self.rfile.read(length)))
            build_site()
            self.send_json(200, result)
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(400, {"error": str(error)})
        except RuntimeError as error:
            self.send_json(500, {"error": str(error)})

    def handle_create_hierarchy_node(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            result = create_hierarchy_node(json.loads(self.rfile.read(length)))
            build_site()
            self.send_json(200, result)
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(400, {"error": str(error)})
        except RuntimeError as error:
            self.send_json(500, {"error": str(error)})

    def handle_refresh_location_coordinates(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            result = refresh_location_coordinates(json.loads(self.rfile.read(length)))
            build_site()
            self.send_json(200, result)
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(400, {"error": str(error)})
        except RuntimeError as error:
            self.send_json(500, {"error": str(error)})

    def handle_import_ticks(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            csv_text = payload.get("csv", "")
            overwrite = bool(payload.get("overwrite"))
            fetch_gps = payload.get("fetch_gps", True)
            if not isinstance(csv_text, str) or not csv_text.strip():
                raise ValueError("Paste the exported tick list CSV first.")
            resolutions = payload.get("resolutions", {})
            if not isinstance(resolutions, dict):
                raise ValueError("Import resolutions must be a mapping.")
            overrides = read_import_overrides()
            for key, resolution in resolutions.items():
                if not isinstance(resolution, dict):
                    continue
                location = clean_location_name(resolution.get("location"))
                crag = clean_location_name(resolution.get("crag"))
                if location and crag:
                    overrides[str(key)] = {"location": location, "crag": crag}
            locations = read_locations()
            infos = [parse_tick_row(row) for row in csv.DictReader(io.StringIO(csv_text))]
            route_hierarchies = known_route_hierarchies()
            resolved = [resolve_tick_hierarchy(info, overrides, locations, route_hierarchies) for info in infos]
            unresolved = [item for item in resolved if item["status"] == "unresolved"]
            if unresolved:
                unique = {item["key"]: item for item in unresolved}
                self.send_json(422, {"error": "Choose a location and crag for each new source hierarchy before importing.", "unresolved": list(unique.values())})
                return
            if resolutions:
                write_import_overrides(overrides)
            known_urls = existing_route_urls()
            created, skipped, errors = [], [], []
            for info, hierarchy in zip(infos, resolved):
                info["location"] = hierarchy["location"]
                info["crag"] = hierarchy["crag"]
                info["state"] = info.get("state") or state_for_location(info["location"], locations)
                if not any(
                    entry.get("level") == "crag"
                    and entry["name"].casefold() == info["crag"].casefold()
                    and entry.get("parent", "").casefold() == info["location"].casefold()
                    for entry in locations
                ):
                    errors.append(f'{info["title"]}: create and verify "{info["location"]} / {info["crag"]}" in the hierarchy editor first')
                    continue
                if not info["title"] or not info["mountain_project_url"]:
                    continue
                try:
                    normalized_url = normalize_url(info["mountain_project_url"])
                    filename = normalize_filename(slugify(info["title"]))
                    target = CONTENT / filename
                    if not overwrite and (normalized_url in known_urls or target.exists()):
                        skipped.append(info["title"])
                        continue
                    coordinates = fetch_route_coordinates(info["mountain_project_url"]) if fetch_gps else None
                    if coordinates and info.get("state"):
                        ensure_state(info["state"], coordinates)
                    if coordinates and info["location"]:
                        ensure_location(info["location"], coordinates, info.get("state", ""))
                    if coordinates and info["crag"]:
                        add_registry_entry(info["crag"], info["location"], coordinates)
                    target.write_text(build_route_markdown(info), encoding="utf-8", newline="\n")
                    known_urls.add(normalized_url)
                    created.append(filename)
                    if fetch_gps:
                        time.sleep(0.4)
                except (OSError, ValueError) as error:
                    errors.append(f'{info["title"]}: {error}')
            if created:
                build_site()
            self.send_json(200, {"created": created, "skipped": skipped, "errors": errors})
        except (ValueError, json.JSONDecodeError, RuntimeError) as error:
            self.send_json(400, {"error": str(error)})

    def handle_preview_ticks(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            csv_text = payload.get("csv", "")
            if not isinstance(csv_text, str) or not csv_text.strip():
                raise ValueError("Paste the exported tick list CSV first.")
            locations = read_locations()
            route_hierarchies = known_route_hierarchies()
            resolutions = [resolve_tick_hierarchy(info, read_import_overrides(), locations, route_hierarchies) for info in (parse_tick_row(row) for row in csv.DictReader(io.StringIO(csv_text)))]
            unresolved = {}
            for resolution in resolutions:
                if resolution["status"] == "unresolved":
                    unresolved.setdefault(resolution["key"], resolution | {"routes": 0})["routes"] += 1
            self.send_json(200, {"matched": sum(item["status"] != "unresolved" for item in resolutions), "unresolved": list(unresolved.values())})
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(400, {"error": str(error)})

    def handle_rebuild_locations(self):
        try:
            added, failed = rebuild_location_registry()
            build_site()
            self.send_json(200, {"added": added, "failed": failed})
        except RuntimeError as error:
            self.send_json(400, {"error": str(error)})

    def do_GET(self):
        if self.path == "/api/climbing/locations":
            locations = read_locations()
            for location in locations:
                location["route_count"] = sum(
                    read_frontmatter_value(path.read_text(encoding="utf-8"), "crag").casefold() == location["name"].casefold()
                    for path in CONTENT.glob("*.md")
                )
            self.send_json(200, locations)
            return
        if self.path.startswith("/api/climbing/routes/") and self.path.endswith("/markdown"):
            filename = normalize_filename(unquote(self.path[len("/api/climbing/routes/"):-len("/markdown")].rstrip("/")))
            target = CONTENT / filename
            if not FILENAME.fullmatch(filename) or not target.exists():
                self.send_json(404, {"error": "Route not found"})
                return
            self.send_json(200, {"filename": filename, "markdown": target.read_text(encoding="utf-8")})
            return
        if self.path == "/api/climbing/routes":
            self.send_json(200, [route_summary(path) for path in sorted(CONTENT.glob("*.md"))])
            return
        if self.path.startswith("/api/climbing/routes/"):
            filename = normalize_filename(unquote(self.path[len("/api/climbing/routes/"):]))
            target = CONTENT / filename
            if not FILENAME.fullmatch(filename) or not target.exists():
                self.send_json(404, {"error": "Route not found"})
                return
            self.send_json(200, route_detail(target))
            return
        if self.path.startswith("/api/climbing/crag-usage"):
            name = clean_location_name((parse_qs(urlparse(self.path).query).get("name") or [""])[0])
            if not name:
                self.send_json(400, {"error": "Missing name"})
                return
            self.send_json(200, crag_usage(name))
            return
        super().do_GET()


