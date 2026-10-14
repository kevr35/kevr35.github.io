"""Climbing-domain helpers and HTTP handlers used by site_editor.py."""

import json
import base64
import csv
import hashlib
import html as html_lib
import io
import re
import subprocess
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from http.server import SimpleHTTPRequestHandler
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, unquote, urljoin, urlparse
from PIL import Image, ImageOps
import indoor_import

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
CONTENT = ROOT / "content" / "climbing" / "outdoor"
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


def existing_route_files_by_url():
    routes = {}
    for path in CONTENT.glob("*.md"):
        route_url = normalize_url(read_frontmatter_value(path.read_text(encoding="utf-8"), "mountain_project_url"))
        if route_url:
            routes.setdefault(route_url, path)
    return routes


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


def hierarchy_name_key(value):
    name = clean_location_name(value).casefold()
    name = re.sub(r"^\d+[.)]\s*", "", name)
    name = re.sub(r"^(?:the|a|an)\s+", "", name)
    return re.sub(r"[^a-z0-9]+", "", name)


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
        segments = info.get("location_segments") or []
        if not segments:
            return result | {"status": "unresolved", "location": source_location, "crag": source_crag}
    locations = locations if locations is not None else read_locations()
    route_hierarchies = route_hierarchies if route_hierarchies is not None else known_route_hierarchies()

    segments = info.get("location_segments") or [source_location, source_crag]
    pairs = [
        (segments[index], segments[index + 1])
        for index in range(len(segments) - 1)
    ]
    override_map = overrides or {}
    for location_name, crag_name in pairs:
        pair_key = hierarchy_key(location_name, crag_name)
        override = override_map.get(pair_key)
        if isinstance(override, dict) and override.get("location") and override.get("crag"):
            return result | {"status": "override", "location": clean_location_name(override["location"]), "crag": clean_location_name(override["crag"])}
    override = override_map.get(key)
    if isinstance(override, dict) and override.get("location") and override.get("crag"):
        return result | {"status": "override", "location": clean_location_name(override["location"]), "crag": clean_location_name(override["crag"])}

    normalized_segments = {hierarchy_name_key(segment) for segment in segments}
    known_crags = [location for location in locations if location.get("level") == "crag"]
    for known_crag in known_crags:
        parent = known_crag.get("parent", "")
        if hierarchy_name_key(known_crag["name"]) not in normalized_segments:
            continue
        if hierarchy_name_key(parent) in normalized_segments:
            return result | {"status": "matched", "location": parent, "crag": known_crag["name"]}

    named_crags = [crag for crag in known_crags if hierarchy_name_key(crag["name"]) in normalized_segments]
    if len(named_crags) == 1:
        known_crag = named_crags[0]
        return result | {"status": "matched", "location": known_crag.get("parent", ""), "crag": known_crag["name"]}

    for location_name, crag_name in pairs:
        known_crag = next(
            (
                location for location in known_crags
                if hierarchy_name_key(location["name"]) == hierarchy_name_key(crag_name)
                and hierarchy_name_key(location.get("parent", "")) == hierarchy_name_key(location_name)
            ),
            None,
        )
        pair_key = hierarchy_key(location_name, crag_name)
        if known_crag or pair_key in route_hierarchies:
            canonical_location = known_crag.get("parent", location_name) if known_crag else location_name
            canonical_crag = known_crag["name"] if known_crag else crag_name
            return result | {"status": "matched", "location": canonical_location, "crag": canonical_crag}

    known_crag = any(
        location["name"].casefold() == source_crag.casefold()
        and location.get("parent", "").casefold() == source_location.casefold()
        and location.get("level") == "crag"
        for location in locations
    )
    if known_crag or key in route_hierarchies:
        return result | {"status": "matched", "location": source_location, "crag": source_crag}
    return result | {"status": "unresolved", "location": source_location, "crag": source_crag}


def parse_tick_row(row):
    normalized = {str(key).strip().lstrip("\ufeff").lower(): value for key, value in row.items() if key}

    def get(*names):
        for name in names:
            value = normalized.get(name)
            if value:
                return str(value).strip()
        return ""

    location_raw = get("location")
    segments = [
        re.sub(r"^\d+[.)]\s*", "", clean_location_name(segment))
        for segment in LOCATION_SEPARATOR.split(location_raw)
        if clean_location_name(segment)
    ] if location_raw else []
    location_segments = segments.copy()
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
        "ascent_type": get("lead style") or get("style") or ("" if get("import source").casefold() == "rss" else "Send"),
        "discipline": route_type.split(",")[0].strip() if route_type else "Sport",
        "setting": "Outdoor",
        "tick_id": get("tick id"),
        "state": state,
        "location": segments[0] if len(segments) > 0 else "",
        "crag": segments[1] if len(segments) > 1 else "",
        "location_segments": location_segments,
        "wall": " / ".join(segments[2:]) if len(segments) > 2 else "",
    }


def parse_tick_rows(csv_text):
    first_line = next((line for line in csv_text.splitlines() if line.strip()), "")
    if not first_line:
        return []
    delimiters = (",", "\t", ";")
    delimiter = max(delimiters, key=lambda candidate: len(next(csv.reader([first_line], delimiter=candidate))))
    if len(next(csv.reader([first_line], delimiter=delimiter))) < 2:
        raise ValueError("Could not detect columns in the tick list. Paste a comma- or tab-separated export.")
    return list(csv.DictReader(io.StringIO(csv_text), delimiter=delimiter))


def assign_tick_ids(infos):
    occurrences = {}
    for info in infos:
        if info.get("tick_id"):
            continue
        identity = json.dumps(
            [
                normalize_url(info.get("mountain_project_url")),
                info.get("climb_date", ""),
                info.get("ascent_type", "").casefold(),
                info.get("personal_note", ""),
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        occurrences[identity] = occurrences.get(identity, 0) + 1
        digest = hashlib.sha256(f"{identity}:{occurrences[identity]}".encode("utf-8")).hexdigest()
        info["tick_id"] = f"csv-{digest}"
    return infos


def ascent_record(info):
    return {
        "id": info["tick_id"],
        "date": info.get("climb_date", ""),
        "ascent_type": info.get("ascent_type", ""),
        "personal_note": info.get("personal_note", ""),
    }


def read_ascent_history(text, route_url):
    raw = read_frontmatter_value(text, "ascents")
    if raw:
        try:
            ascents = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ValueError("Existing route has invalid ascents front matter.") from error
        if not isinstance(ascents, list) or any(not isinstance(item, dict) for item in ascents):
            raise ValueError("Existing route ascents front matter must be a list of records.")
        return ascents

    climb_date = read_frontmatter_value(text, "climb_date")
    ascent_type = read_frontmatter_value(text, "ascent_type")
    personal_note = read_frontmatter_value(text, "personal_note")
    if not any((climb_date, ascent_type, personal_note)):
        return []
    identity = json.dumps([normalize_url(route_url), climb_date, ascent_type.casefold(), personal_note], separators=(",", ":"))
    return [{
        "id": "legacy-" + hashlib.sha256(identity.encode("utf-8")).hexdigest(),
        "date": climb_date,
        "ascent_type": ascent_type,
        "personal_note": personal_note,
    }]


def reconcile_legacy_rss_ascents(ascents):
    normalized = []
    seen_ids = set()
    changed = False
    for ascent in ascents:
        record = dict(ascent)
        ascent_id = str(record.get("id", ""))
        if ascent_id and ascent_id in seen_ids:
            changed = True
            continue
        if ascent_id:
            seen_ids.add(ascent_id)
        normalized.append(record)

    removed = set()
    for legacy_index, legacy in enumerate(normalized):
        if not str(legacy.get("id", "")).startswith("legacy-"):
            continue
        legacy_date = str(legacy.get("date", ""))
        if not legacy_date:
            continue
        legacy_style = str(legacy.get("ascent_type", "")).casefold()
        for rss_index, rss in enumerate(normalized):
            if rss_index == legacy_index or rss_index in removed:
                continue
            if not str(rss.get("id", "")).startswith("MPObject_") or str(rss.get("date", "")) != legacy_date:
                continue
            rss_style = str(rss.get("ascent_type", "")).casefold()
            if legacy_style and rss_style and legacy_style != rss_style:
                continue
            rss["ascent_type"] = rss.get("ascent_type") or legacy.get("ascent_type", "")
            rss["personal_note"] = legacy.get("personal_note", "")
            removed.add(legacy_index)
            changed = True
            break

    if removed:
        normalized = [record for index, record in enumerate(normalized) if index not in removed]
    return normalized, changed


def merge_ascent_history(text, incoming, route_url):
    ascents, changed = reconcile_legacy_rss_ascents(read_ascent_history(text, route_url))
    seen = {str(item.get("id", "")) for item in ascents if item.get("id")}
    added = 0
    for ascent in incoming:
        if ascent["id"] in seen:
            existing_index = next(
                (
                    index for index, existing in enumerate(ascents)
                    if str(existing.get("id", "")) == str(ascent["id"])
                ),
                None,
            )
            if existing_index is not None and not ascents[existing_index].get("ascent_type") and ascent.get("ascent_type"):
                ascents[existing_index] = {
                    **ascents[existing_index],
                    "ascent_type": ascent["ascent_type"],
                }
                changed = True
            continue
        if str(ascent["id"]).startswith("MPObject_") and ascent.get("date"):
            matching_legacy = next(
                (
                    index for index, existing in enumerate(ascents)
                    if str(existing.get("id", "")).startswith("legacy-")
                    and str(existing.get("date", "")) == str(ascent.get("date", ""))
                    and (
                        not existing.get("ascent_type")
                        or not ascent.get("ascent_type")
                        or str(existing.get("ascent_type", "")).casefold()
                        == str(ascent.get("ascent_type", "")).casefold()
                    )
                ),
                None,
            )
            if matching_legacy is not None:
                legacy = ascents[matching_legacy]
                ascent = dict(ascent)
                ascent["ascent_type"] = ascent.get("ascent_type") or legacy.get("ascent_type", "")
                ascent["personal_note"] = legacy.get("personal_note", "")
                ascents[matching_legacy] = ascent
                seen.add(ascent["id"])
                changed = True
                continue
        ascents.append(ascent)
        seen.add(ascent["id"])
        added += 1
        changed = True

    if not changed:
        return text, 0, False

    def sort_key(item):
        return (str(item.get("date", "")), str(item.get("id", "")))

    latest = max(ascents, key=sort_key) if ascents else {}
    replacements = {
        "climb_date": json.dumps(str(latest.get("date", ""))),
        "ascent_type": json.dumps(str(latest.get("ascent_type", ""))),
        "personal_note": json.dumps(str(latest.get("personal_note", ""))),
        "ascents": json.dumps(ascents, ensure_ascii=False, separators=(",", ":")),
        "draft": "true" if ascents and all(is_unsent_ascent(item.get("ascent_type")) for item in ascents) else "false",
    }
    for name, value in replacements.items():
        pattern = re.compile(rf"(?m)^{re.escape(name)}:\s*.*$")
        line = f"{name}: {value}"
        if pattern.search(text):
            text = pattern.sub(lambda _: line, text, count=1)
        else:
            insert_before = re.search(r"(?m)^tags:\s*$", text)
            if insert_before:
                text = text[:insert_before.start()] + line + "\n" + text[insert_before.start():]
            else:
                closing = text.find("\n---", text.find("---") + 3)
                if closing < 0:
                    raise ValueError("Existing route has malformed front matter.")
                text = text[:closing] + "\n" + line + text[closing:]
    return text, added, changed


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
        page_html = response.read().decode("utf-8", errors="ignore")
    crumbs = []
    pattern = r'''<a\s+href=["']((?:https?://(?:www\.)?mountainproject\.com)?/area/[^"']+)["'][^>]*>(.*?)</a>'''
    locations = read_locations()
    for area_url, label in re.findall(pattern, page_html, re.DOTALL | re.IGNORECASE):
        raw_label = re.sub(r"<[^>]+>", "", label)
        name = clean_location_name(html_lib.unescape(raw_label))
        if re.search(r"(?:&hellip;|&#8230;|…|\.\.\.)", raw_label, re.IGNORECASE):
            area_slug = urlparse(area_url).path.rstrip("/").rsplit("/", 1)[-1]
            registered_name = next(
                (area["name"] for area in locations if slugify(area["name"]) == area_slug),
                "",
            )
            name = registered_name or name
        if name and name.casefold() != "all locations" and name not in crumbs:
            crumbs.append(name)
    return crumbs


TICK_CSV_HEADERS = [
    "Date", "Route", "Rating", "Notes", "URL", "Pitches", "Location",
    "Avg Stars", "Your Stars", "Style", "Lead Style", "Route Type",
    "Your Rating", "Length", "Rating Code", "Import Source", "Tick ID",
]


class MountainProjectTickPageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.current_table = None
        self.current_row = None
        self.reading_ascent = False
        self.max_page = 1

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "table":
            classes = set(attributes.get("class", "").split())
            if "route-table" in classes:
                self.current_table = {
                    "preferred": "hidden-sm-up" in classes,
                    "rows": [],
                }
                self.tables.append(self.current_table)
        elif tag == "tr" and self.current_table:
            classes = set(attributes.get("class", "").split())
            if "route-row" in classes:
                self.current_row = {"url": "", "ascent_text": ""}
        elif tag == "a":
            href = attributes.get("href", "")
            parsed_href = urlparse(href)
            if parsed_href.path.rstrip("/").endswith("/ticks"):
                page_values = parse_qs(parsed_href.query).get("page", [])
                for page_value in page_values:
                    if page_value.isdigit():
                        self.max_page = max(self.max_page, int(page_value))
            if self.current_row and href:
                absolute_url = urljoin("https://www.mountainproject.com", href)
                if re.match(r"^https://(?:www\.)?mountainproject\.com/route/\d+/", absolute_url):
                    self.current_row["url"] = absolute_url
        elif tag == "i" and self.current_row:
            self.reading_ascent = True

    def handle_data(self, data):
        if self.reading_ascent and self.current_row:
            self.current_row["ascent_text"] += data

    def handle_endtag(self, tag):
        if tag == "i":
            self.reading_ascent = False
        elif tag == "tr" and self.current_row:
            date_text, separator, style_text = self.current_row["ascent_text"].partition("·")
            climb_date = parse_climb_date(date_text.strip()) if separator else ""
            style_text = re.split(r"\.\s", style_text.strip(), maxsplit=1)[0].rstrip(". ")
            ascent_type = style_text.rsplit("/", 1)[-1].strip()
            if ascent_type.casefold() in {"lead", "tr", "top rope", "boulder", "aid"}:
                ascent_type = ""
            if self.current_row["url"] and climb_date:
                self.current_table["rows"].append({
                    "url": normalize_url(self.current_row["url"]),
                    "date": climb_date,
                    "ascent_type": ascent_type,
                })
            self.current_row = None
        elif tag == "table" and self.current_table:
            self.current_table = None

    def tick_rows(self):
        preferred = next((table["rows"] for table in self.tables if table["preferred"]), None)
        if preferred is not None:
            return preferred
        return next((table["rows"] for table in self.tables if table["rows"]), [])


def fetch_public_tick_history(user_id, oldest_date):
    profile_request = urllib.request.Request(
        f"https://www.mountainproject.com/user/{user_id}",
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(profile_request, timeout=20) as response:
        profile_url = response.geturl().rstrip("/")

    profile_parts = urlparse(profile_url)
    if (
        profile_parts.hostname not in {"www.mountainproject.com", "mountainproject.com"}
        or not re.fullmatch(rf"/user/{re.escape(user_id)}(?:/[^/]+)?", profile_parts.path)
    ):
        raise ValueError("Mountain Project did not resolve the RSS user to a public profile.")

    ticks_url = profile_url + "/ticks"
    max_pages = 1
    ticks = []
    page = 1
    while page <= 20:
        page_url = ticks_url if page == 1 else f"{ticks_url}?page={page}"
        request = urllib.request.Request(page_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=20) as response:
            page_html = response.read().decode("utf-8", errors="ignore")

        parser = MountainProjectTickPageParser()
        parser.feed(page_html)
        page_ticks = parser.tick_rows()
        max_pages = max(max_pages, parser.max_page)
        if page == 1 and not page_ticks:
            raise ValueError("Mountain Project's public tick list contained no readable tick rows.")
        ticks.extend(page_ticks)
        if any(tick["date"] < oldest_date for tick in page_ticks):
            break
        if page >= max_pages:
            break
        page += 1
        time.sleep(0.2)
    return ticks, max_pages


def apply_public_tick_styles(rows, tick_targets, public_ticks, warnings):
    rss_by_route_date = {}
    for row_index, route_url, climb_date in tick_targets:
        key = (route_url, climb_date)
        rss_by_route_date.setdefault(key, []).append(row_index)

    public_by_route_date = {}
    for tick in public_ticks:
        key = (tick["url"], tick["date"])
        public_by_route_date.setdefault(key, []).append(tick)

    unmatched = 0
    for key, row_indices in rss_by_route_date.items():
        matching_ticks = public_by_route_date.get(key, [])
        if len(matching_ticks) != len(row_indices):
            unmatched += len(row_indices)
            continue
        for row_index, tick in zip(row_indices, matching_ticks):
            if tick["ascent_type"]:
                rows[row_index][10] = tick["ascent_type"]
            else:
                unmatched += 1

    if unmatched:
        warnings.append(
            f"Could not uniquely match public tick-list styles for {unmatched} RSS tick(s); those styles remain blank."
        )


def build_rss_tick_csv(feed_url):
    parsed_url = urlparse(str(feed_url or "").strip())
    if (
        parsed_url.scheme != "https"
        or parsed_url.hostname not in {"www.mountainproject.com", "mountainproject.com"}
        or not re.fullmatch(r"/rss/user-ticks/\d+/?", parsed_url.path)
    ):
        raise ValueError("Use a Mountain Project user tick feed URL, such as https://www.mountainproject.com/rss/user-ticks/123456789.")

    request = urllib.request.Request(parsed_url.geturl(), headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            root = ET.fromstring(response.read())
    except (urllib.error.URLError, OSError, TimeoutError, ET.ParseError) as error:
        raise RuntimeError(f"Could not read the Mountain Project RSS feed: {error}") from error
    channel = root.find("channel")
    items = channel.findall("item") if channel is not None else []
    if not items:
        raise ValueError("The RSS feed contains no tick entries.")
    if len(items) > 100:
        raise ValueError("The RSS feed contains more than 100 entries; refusing an unexpectedly large import.")

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(TICK_CSV_HEADERS)
    warnings = []
    breadcrumb_cache = {}
    seen_tick_ids = set()
    rss_rows = []
    tick_targets = []
    count = 0
    for item in items:
        title = html_lib.unescape(item.findtext("title", default="")).strip()
        route_url = item.findtext("link", default="").strip()
        route_url_parts = urlparse(route_url)
        if (
            route_url_parts.scheme != "https"
            or route_url_parts.hostname not in {"www.mountainproject.com", "mountainproject.com"}
            or not re.match(r"^/route/\d+/", route_url_parts.path)
        ):
            warnings.append(f"Skipped an RSS item with an invalid route link: {title or '(untitled)'}")
            continue
        normalized_url = normalize_url(route_url)
        tick_id = item.findtext("guid", default="").strip()
        if not tick_id:
            tick_id = "rss-" + hashlib.sha256(
                f"{normalized_url}|{item.findtext('pubDate', default='')}|{title}".encode("utf-8")
            ).hexdigest()
        if tick_id in seen_tick_ids:
            continue
        seen_tick_ids.add(tick_id)
        count += 1

        route_title = re.sub(r"^Tick:\s*", "", title, flags=re.IGNORECASE)
        grade = ""
        grade_match = re.search(r"\(([^()]*)\)\s*$", route_title)
        if grade_match:
            grade = grade_match.group(1).strip()
            route_title = route_title[:grade_match.start()].strip()

        pub_date = item.findtext("pubDate", default="").strip()
        try:
            climb_date = parsedate_to_datetime(pub_date).date().isoformat()
        except (TypeError, ValueError, OverflowError):
            climb_date = ""
            warnings.append(f"Could not read the RSS date for {route_title or route_url}.")

        if normalized_url not in breadcrumb_cache:
            try:
                breadcrumb_cache[normalized_url] = fetch_route_breadcrumb(route_url)
            except (urllib.error.URLError, OSError, TimeoutError) as error:
                breadcrumb_cache[normalized_url] = []
                warnings.append(f"Could not fetch location details for {route_title or route_url}: {error}")
            time.sleep(0.2)
        location = " > ".join(breadcrumb_cache[normalized_url])
        route_type = "Boulder" if grade.upper().startswith("V") or re.fullmatch(r"[3-9][abc][+-]?", grade, re.IGNORECASE) else "Sport"
        row_index = len(rss_rows)
        rss_rows.append([
            climb_date, route_title, grade, "", route_url, "1", location,
            "", "", "", "", route_type, "", "", "", "RSS", tick_id,
        ])
        if climb_date:
            tick_targets.append((row_index, normalized_url, climb_date))

    if tick_targets:
        try:
            public_ticks, max_pages = fetch_public_tick_history(
                re.fullmatch(r"/rss/user-ticks/(\d+)/?", parsed_url.path).group(1),
                min(target[2] for target in tick_targets),
            )
        except (urllib.error.URLError, OSError, TimeoutError, ValueError) as error:
            warnings.append(f"Could not retrieve public Mountain Project tick styles: {error}")
        else:
            apply_public_tick_styles(rss_rows, tick_targets, public_ticks, warnings)
            if max_pages > 20 and not any(
                tick["date"] < min(target[2] for target in tick_targets)
                for tick in public_ticks
            ):
                warnings.append("Stopped public tick-list lookup after 20 pages; older RSS styles may remain blank.")

    writer.writerows(rss_rows)

    return {"csv": output.getvalue(), "count": count, "warnings": warnings}


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
    ascents = fields.get("ascents") or ([ascent_record(fields)] if fields.get("tick_id") else [])
    draft = "true" if (
        all(is_unsent_ascent(item.get("ascent_type")) for item in ascents)
        if ascents else is_unsent_ascent(fields.get("ascent_type"))
    ) else "false"
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
        *([f"ascents: {json.dumps(ascents, ensure_ascii=False, separators=(',', ':'))}"] if ascents else []),
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
        elif self.path == "/api/climbing/preview-indoor":
            self.handle_indoor("preview")
        elif self.path == "/api/climbing/save-indoor":
            self.handle_indoor("save")
        elif self.path == "/api/climbing/gyms":
            self.handle_add_gym()
        elif self.path == "/api/climbing/preview-ticks":
            self.handle_preview_ticks()
        elif self.path == "/api/climbing/import-ticks":
            self.handle_import_ticks()
        elif self.path == "/api/climbing/tick-rss":
            self.handle_tick_rss()
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
            self.send_json(200, {"path": f"content/climbing/outdoor/{filename}"})
        except FileExistsError as error:
            self.send_json(409, {"error": str(error)})
        except (ValueError, json.JSONDecodeError, OSError, RuntimeError) as error:
            self.send_json(400, {"error": str(error)})

    def handle_indoor(self, action):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            if action == "preview":
                self.send_json(200, indoor_import.preview_indoor(payload))
            else:
                path = indoor_import.save_indoor(payload)
                build_site()
                self.send_json(200, {"path": path})
        except FileExistsError as error:
            self.send_json(409, {"error": str(error)})
        except (ValueError, json.JSONDecodeError, OSError, RuntimeError) as error:
            self.send_json(400, {"error": str(error)})

    def handle_add_gym(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            result = indoor_import.add_gym(payload)
            build_site()
            self.send_json(200, result)
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
            infos = assign_tick_ids([parse_tick_row(row) for row in parse_tick_rows(csv_text)])
            route_hierarchies = known_route_hierarchies()
            resolved = [resolve_tick_hierarchy(info, overrides, locations, route_hierarchies) for info in infos]
            unresolved = [item for item in resolved if item["status"] == "unresolved"]
            if unresolved:
                unique = {item["key"]: item for item in unresolved}
                self.send_json(422, {"error": "Choose a location and crag for each new source hierarchy before importing.", "unresolved": list(unique.values())})
                return
            if resolutions:
                write_import_overrides(overrides)
            existing_routes = existing_route_files_by_url()
            created, updated, skipped, errors = [], [], [], []
            warnings = []
            valid_infos = []
            for info, hierarchy in zip(infos, resolved):
                info["location"] = hierarchy["location"]
                info["crag"] = hierarchy["crag"]
                info["state"] = info.get("state") or state_for_location(info["location"], locations)
                if not info["title"] or not info["mountain_project_url"]:
                    continue
                parent = next(
                    (
                        entry for entry in locations
                        if entry.get("level") == "location"
                        and entry["name"].casefold() == info["location"].casefold()
                    ),
                    None,
                )
                if not parent:
                    errors.append(f'{info["title"]}: "{info["location"]}" is not a registered location; verify its hierarchy first')
                    continue
                named_node = next(
                    (entry for entry in locations if entry["name"].casefold() == info["crag"].casefold()),
                    None,
                )
                if named_node and (
                    named_node.get("level") != "crag"
                    or named_node.get("parent", "").casefold() != info["location"].casefold()
                ):
                    errors.append(f'{info["title"]}: "{info["crag"]}" is already registered under a different hierarchy')
                    continue
                valid_infos.append(info)
            grouped = {}
            for info in valid_infos:
                grouped.setdefault(normalize_url(info["mountain_project_url"]), []).append(info)

            for normalized_url, route_ticks in grouped.items():
                info = route_ticks[0]
                incoming = []
                incoming_ids = set()
                for tick in route_ticks:
                    ascent = ascent_record(tick)
                    if ascent["id"] not in incoming_ids:
                        incoming.append(ascent)
                        incoming_ids.add(ascent["id"])
                try:
                    parent = next(
                        entry for entry in locations
                        if entry.get("level") == "location"
                        and entry["name"].casefold() == info["location"].casefold()
                    )
                    registered_crag = next(
                        (
                            entry for entry in locations
                            if entry.get("level") == "crag"
                            and entry["name"].casefold() == info["crag"].casefold()
                            and entry.get("parent", "").casefold() == info["location"].casefold()
                        ),
                        None,
                    )
                    coordinates = None
                    if not registered_crag:
                        coordinates = fetch_route_coordinates(info["mountain_project_url"]) if fetch_gps else None
                        approximate = not coordinates
                        if approximate:
                            coordinates = {
                                "latitude": parent.get("latitude", ""),
                                "longitude": parent.get("longitude", ""),
                            }
                        if not coordinates["latitude"] or not coordinates["longitude"]:
                            raise ValueError(f'Cannot register "{info["crag"]}" without coordinates for its parent location.')
                        if not add_registry_entry(info["crag"], info["location"], coordinates):
                            raise ValueError(f'Could not register new crag "{info["crag"]}" under "{info["location"]}".')
                        locations.append({
                            "name": info["crag"],
                            "parent": info["location"],
                            "latitude": str(coordinates["latitude"]),
                            "longitude": str(coordinates["longitude"]),
                            "level": "crag",
                        })
                        warnings.append(
                            f'Added "{info["crag"]}" under "{info["location"]}"'
                            + (" using the parent location's approximate coordinates." if approximate else ".")
                        )

                    target = existing_routes.get(normalized_url)
                    if target:
                        text = target.read_text(encoding="utf-8")
                        merged, added, changed = merge_ascent_history(text, incoming, normalized_url)
                        if changed:
                            target.write_text(merged, encoding="utf-8", newline="\n")
                            updated.append({"title": info["title"], "ticks_added": added})
                        else:
                            skipped.append(info["title"])
                        continue

                    filename = normalize_filename(slugify(info["title"]))
                    target = CONTENT / filename
                    if target.exists():
                        skipped.append(info["title"])
                        continue
                    info["ascents"] = incoming
                    latest = max(incoming, key=lambda item: (str(item.get("date", "")), str(item.get("id", ""))))
                    info.update({
                        "climb_date": latest.get("date", ""),
                        "ascent_type": latest.get("ascent_type", ""),
                        "personal_note": latest.get("personal_note", ""),
                    })
                    if coordinates and info.get("state"):
                        ensure_state(info["state"], coordinates)
                    if coordinates and info["location"]:
                        ensure_location(info["location"], coordinates, info.get("state", ""))
                    if coordinates and info["crag"]:
                        add_registry_entry(info["crag"], info["location"], coordinates)
                    target.write_text(build_route_markdown(info), encoding="utf-8", newline="\n")
                    existing_routes[normalized_url] = target
                    created.append(filename)
                    if fetch_gps:
                        time.sleep(0.4)
                except (OSError, ValueError) as error:
                    errors.append(f'{info["title"]}: {error}')
            if created or updated or warnings:
                build_site()
            self.send_json(200, {"created": created, "updated": updated, "skipped": skipped, "errors": errors, "warnings": warnings})
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
            resolutions = [resolve_tick_hierarchy(info, read_import_overrides(), locations, route_hierarchies) for info in (parse_tick_row(row) for row in parse_tick_rows(csv_text))]
            unresolved = {}
            for resolution in resolutions:
                if resolution["status"] == "unresolved":
                    unresolved.setdefault(resolution["key"], resolution | {"routes": 0})["routes"] += 1
            self.send_json(200, {"matched": sum(item["status"] != "unresolved" for item in resolutions), "unresolved": list(unresolved.values())})
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(400, {"error": str(error)})

    def handle_tick_rss(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            result = build_rss_tick_csv(payload.get("url", ""))
            self.send_json(200, result)
        except (ValueError, json.JSONDecodeError, RuntimeError) as error:
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
