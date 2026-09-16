#!/usr/bin/env python3
"""Migrate climbing routes to crag/wall-only front matter.

The registry remains the source of truth for each crag's location and state.
Legacy routes that stored a location as ``crag`` are resolved from their wall:
known child crags are promoted, a single shared wall becomes a missing crag,
and otherwise the location itself becomes the crag while its wall is retained.
"""

import re
from pathlib import Path

CONTENT = Path("content/climbing")
LOCATIONS = Path("data/climbing/locations.yaml")
LEGACY_LOCATION_NAMES = {"rumney", "pawtuckaway"}


def read_locations():
    entries = []
    current = None
    for line in LOCATIONS.read_text(encoding="utf-8").splitlines():
        if line.startswith("- name:"):
            if current:
                entries.append(current)
            current = {"name": line.split(":", 1)[1].strip().strip('"')}
        elif current:
            match = re.match(r'\s+(parent|latitude|longitude|level):\s*"?([^"\s]+(?:\s+[^"\n]+)?)"?\s*$', line)
            if match:
                current[match.group(1)] = match.group(2).strip('"')
    if current:
        entries.append(current)
    return entries


def write_locations(entries):
    lines = ["# Shared state, location, and crag records. Routes inherit parents from these records."]
    for entry in entries:
        lines.append(f'- name: "{entry["name"].replace(chr(34), "")}"')
        if entry.get("parent"):
            lines.append(f'  parent: "{entry["parent"].replace(chr(34), "")}"')
        lines.append(f'  latitude: {entry["latitude"]}')
        lines.append(f'  longitude: {entry["longitude"]}')
        lines.append(f'  level: "{entry.get("level", "crag")}"')
    LOCATIONS.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def field(text, name):
    match = re.search(rf'(?m)^{name}:\s*"([^"]*)"', text)
    return match.group(1) if match else ""


def replace_or_add(text, name, value):
    replacement = f'{name}: "{value.replace(chr(34), "")}"'
    pattern = rf'(?m)^{name}:\s*"[^"]*"\s*$'
    if re.search(pattern, text):
        return re.sub(pattern, replacement, text, count=1)
    return text.replace("---\n", f"---\n{replacement}\n", 1)


def remove_field(text, name):
    return re.sub(rf'(?m)^{name}:.*\n', "", text)


def main():
    entries = read_locations()
    for entry in entries:
        if entry["name"].casefold() in LEGACY_LOCATION_NAMES:
            entry["level"] = "location"
    by_name = {entry["name"].casefold(): entry for entry in entries}
    routes = []
    for path in sorted(CONTENT.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        crag = field(text, "crag")
        if not crag:
            continue
        registry = by_name.get(crag.casefold())
        if registry and registry.get("level") == "location":
            routes.append((path, text, registry))

    grouped = {}
    for path, text, registry in routes:
        grouped.setdefault(registry["name"].casefold(), []).append((path, text, registry))

    migrated = 0
    for path in sorted(CONTENT.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        updated = text
        for legacy in ("state", "location", "region", "area"):
            updated = remove_field(updated, legacy)
        if updated != text:
            path.write_text(updated, encoding="utf-8", newline="\n")
            migrated += 1

    for key, group in grouped.items():
        location = group[0][2]
        children = {entry["name"].casefold(): entry for entry in entries if entry.get("level") == "crag" and entry.get("parent", "").casefold() == location["name"].casefold()}
        walls = {field(text, "wall").strip() for _, text, _ in group if field(text, "wall").strip()}
        shared_wall = next(iter(walls)) if len(walls) == 1 else ""
        for path, text, _ in group:
            wall = field(text, "wall").strip()
            child = children.get(wall.casefold()) if wall else None
            if child:
                crag_name, wall_name = child["name"], ""
            elif wall:
                crag_name, wall_name = wall, ""
                if wall.casefold() not in by_name:
                    child = {
                        "name": wall,
                        "parent": location["name"],
                        "latitude": location["latitude"],
                        "longitude": location["longitude"],
                        "level": "crag",
                    }
                    entries.append(child)
                    by_name[wall.casefold()] = child
            elif shared_wall:
                crag_name, wall_name = shared_wall, ""
                if shared_wall.casefold() not in by_name:
                    child = {
                        "name": shared_wall,
                        "parent": location["name"],
                        "latitude": location["latitude"],
                        "longitude": location["longitude"],
                        "level": "crag",
                    }
                    entries.append(child)
                    by_name[shared_wall.casefold()] = child
            else:
                crag_name, wall_name = location["name"], wall
                location["level"] = "crag"
            updated = replace_or_add(text, "crag", crag_name)
            updated = replace_or_add(updated, "wall", wall_name)
            for legacy in ("state", "location", "region", "area"):
                updated = remove_field(updated, legacy)
            if updated != text:
                path.write_text(updated, encoding="utf-8", newline="\n")
                migrated += 1

    write_locations(entries)
    print(f"Migrated {migrated} routes and updated the location registry.")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""Update route locations from parent regions to sub-crags based on area field."""

import os
import re

CONTENT_DIR = "content/climbing"

# Mapping of (old_location, area) -> new_location
LOCATION_MAPPING = {
    ("Coopers Rock", "Rhododendron Trail Areas"): "Rhododendron Trail Areas",
    ("Coopers Rock", "Tilted Tree"): "Tilted Tree",
    ("Coopers Rock", "Upper Rock City"): "Upper Rock City",
    ("The New River Gorge Region", "Cotton Hill"): "Cotton Hill",
    ("The New River Gorge Region", "Endless Wall"): "Endless Wall",
    ("The New River Gorge Region", "Lower New River Gorge Bouldering"): "Lower New River Gorge Bouldering",
    ("The New River Gorge Region", "Interp Boulders"): "Interp Boulders",
    ("The New River Gorge Region", "Meadow Top Boulders"): "Meadow Top Boulders",
    ("The New River Gorge Region", "Summersville (Gauley River) Area"): "Summersville (Gauley River) Area",
    ("The New River Gorge Region", "Upper Meadow"): "Upper Meadow",
}

def process_route_file(filepath):
    """Update route file to use sub-crag location based on area."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract location and area from frontmatter
    location_match = re.search(r'^location: "([^"]*)"', content, re.MULTILINE)
    area_match = re.search(r'^area: "([^"]*)"', content, re.MULTILINE)
    
    if not location_match:
        return False
    
    location = location_match.group(1)
    area = area_match.group(1) if area_match else ""
    
    key = (location, area)
    new_location = LOCATION_MAPPING.get(key)
    
    if not new_location or new_location == location:
        return False
    
    # Replace the location field
    new_content = re.sub(
        r'^location: "([^"]*)"',
        f'location: "{new_location}"',
        content,
        count=1,
        flags=re.MULTILINE
    )
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"✓ {os.path.basename(filepath)}: '{location}' -> '{new_location}'")
    return True

def main():
    if not os.path.isdir(CONTENT_DIR):
        print(f"Error: {CONTENT_DIR} directory not found")
        return
    
    count = 0
    for filename in sorted(os.listdir(CONTENT_DIR)):
        if filename.endswith('.md'):
            filepath = os.path.join(CONTENT_DIR, filename)
            if process_route_file(filepath):
                count += 1
    
    print(f"\nUpdated {count} route locations")

if __name__ == '__main__':
    main()
