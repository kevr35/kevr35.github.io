#!/usr/bin/env python3
"""Clear area field when it's the same as location."""

import os
import re

CONTENT_DIR = "content/climbing"

def process_route_file(filepath):
    """Clear area field if it matches location."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract location and area from frontmatter
    location_match = re.search(r'^location: "([^"]*)"', content, re.MULTILINE)
    area_match = re.search(r'^area: "([^"]*)"', content, re.MULTILINE)
    
    if not location_match or not area_match:
        return False
    
    location = location_match.group(1)
    area = area_match.group(1)
    
    if location != area:
        return False
    
    # Clear the area field
    new_content = re.sub(
        r'^area: "([^"]*)"',
        'area: ""',
        content,
        count=1,
        flags=re.MULTILINE
    )
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"✓ {os.path.basename(filepath)}: cleared duplicate area")
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
    
    print(f"\nCleared {count} duplicate area fields")

if __name__ == '__main__':
    main()
