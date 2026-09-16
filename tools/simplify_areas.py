#!/usr/bin/env python3
"""Simplify area fields in route files by extracting meaningful hierarchy levels."""

import os
import re
import sys

CONTENT_DIR = "content/climbing"

def simplify_area(area_str):
    """
    Simplify an area string by removing redundant hierarchy levels.
    
    Strategy:
    1. Split on " / "
    2. If multiple parts, skip the first (often duplicate of location) and the last (often boulder name)
    3. Take the remaining parts, or if that's empty, take parts 1-2
    """
    if not area_str:
        return area_str
    
    parts = [p.strip() for p in area_str.split(" / ") if p.strip()]
    
    if len(parts) <= 2:
        return area_str
    
    # Skip first (location duplicate) and last (boulder name)
    middle_parts = parts[1:-1]
    
    if middle_parts:
        # If we have meaningful middle parts, use them
        simplified = " / ".join(middle_parts)
    else:
        # If middle is empty, use parts 1-2 (location category and sector)
        simplified = " / ".join(parts[1:2]) if len(parts) > 1 else parts[0]
    
    return simplified

def process_route_file(filepath):
    """Process a single route file, simplifying its area field."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the area field in the frontmatter
    match = re.search(r'^area: "([^"]*)"', content, re.MULTILINE)
    if not match:
        return False
    
    old_area = match.group(1)
    new_area = simplify_area(old_area)
    
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
    
    print(f"\nSimplified {count} area fields")

if __name__ == '__main__':
    main()
