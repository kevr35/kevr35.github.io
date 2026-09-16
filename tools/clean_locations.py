#!/usr/bin/env python3
"""Check the climbing route and location registry hierarchy."""

import os
import re
import sys

CONTENT_DIR = "content/climbing"
LOCATIONS_FILE = "data/climbing/locations.yaml"


def load_locations():
    entries = []
    current = None
    with open(LOCATIONS_FILE, "r", encoding="utf-8") as stream:
        for line in stream:
            line = line.rstrip("\n")
            if line.startswith("- name:"):
                if current:
                    entries.append(current)
                current = {"name": line.split(":", 1)[1].strip().strip('"')}
            elif current:
                match = re.match(r'^\s+(parent|latitude|longitude|level):\s*"?([^"\n]*)"?\s*$', line)
                if match:
                    current[match.group(1)] = match.group(2)
    if current:
        entries.append(current)
    return {entry["name"].casefold(): entry for entry in entries if "name" in entry}


def route_field(content, name):
    match = re.search(rf'(?m)^{name}:\s*"([^"]*)"', content)
    return match.group(1).strip() if match else ""


def report_routes(locations):
    warnings = 0
    for filename in sorted(os.listdir(CONTENT_DIR)):
        if not filename.endswith(".md") or filename == "_index.md":
            continue
        filepath = os.path.join(CONTENT_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as stream:
            content = stream.read()
        crag_name = route_field(content, "crag")
        if not crag_name:
            print(f"WARNING {filename}: missing crag")
            warnings += 1
            continue
        if any(re.search(rf'(?m)^{field}:', content) for field in ("state", "location", "region", "area")):
            print(f"WARNING {filename}: inherited hierarchy fields must be removed; keep only crag and wall")
            warnings += 1
        crag = locations.get(crag_name.casefold())
        if not crag or crag.get("level") != "crag":
            print(f"WARNING {filename}: crag \"{crag_name}\" is not a registered crag")
            warnings += 1
            continue
        parent = locations.get(crag.get("parent", "").casefold())
        if not parent or parent.get("level") != "location":
            print(f"WARNING {filename}: crag \"{crag_name}\" has no registered location parent")
            warnings += 1
    return warnings


def report_duplicate_coordinates(locations):
    warnings = 0
    for entry in locations.values():
        parent = locations.get(entry.get("parent", "").casefold())
        if parent and entry.get("latitude") == parent.get("latitude") and entry.get("longitude") == parent.get("longitude"):
            print(f"WARNING \"{entry['name']}\" shares exact coordinates with parent \"{parent['name']}\" - verify real coordinates")
            warnings += 1
    return warnings


def main():
    if not os.path.isdir(CONTENT_DIR) or not os.path.isfile(LOCATIONS_FILE):
        print("Error: expected to run from the repo root")
        sys.exit(1)
    locations = load_locations()
    route_warnings = report_routes(locations)
    coordinate_warnings = report_duplicate_coordinates(locations)
    print(f"\n{route_warnings} route warnings, {coordinate_warnings} coordinate warnings")
    sys.exit(1 if route_warnings else 0)


if __name__ == "__main__":
    main()
