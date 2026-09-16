#!/usr/bin/env python3
"""Further simplify area fields to single-level display."""

import os
import re
import sys

CONTENT_DIR = "content/climbing"

def reduce_area_to_first_level(area_str):
    """
    Reduce area to just the first meaningful level.
    Split on " / " and take only the first part (the main sector/area name).
    """
    if not area_str:
        return area_str
    
    parts = [p.strip() for p in area_str.split(" / ") if p.strip()]
    
    if not parts:
        return area_str
    
    # Return just the first level
    return parts[0]

def process_route_file(filepath):
    """Process a single route file, reducing its area field to first level only."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the area field in the frontmatter
    match = re.search(r'^area: "([^"]*)"', content, re.MULTILINE)
    if not match:
        return False
    
    old_area = match.group(1)
    new_area = reduce_area_to_first_level(old_area)
    
    if old_area == new_area:
        return False
    
    # Replace the area field
    new_content = re.sub(
        r'^area: "([^"]*)"',
        f'area: "{new_area}"',
        content,
        count=1,
        flags=re.MULTILINE
    )
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"✓ {os.path.basename(filepath)}")
    print(f"  Old: {old_area}")
    print(f"  New: {new_area}")
    return True

def main():
    if not os.path.isdir(CONTENT_DIR):
        print(f"Error: {CONTENT_DIR} directory not found")
        sys.exit(1)
    
    count = 0
    for filename in sorted(os.listdir(CONTENT_DIR)):
        if filename.endswith('.md'):
            filepath = os.path.join(CONTENT_DIR, filename)
            if process_route_file(filepath):
                count += 1
    
    print(f"\nReduced {count} area fields to first level only")

if __name__ == '__main__':
    main()
