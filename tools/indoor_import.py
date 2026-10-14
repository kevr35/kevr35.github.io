"""Generate indoor/board climb Markdown from a YouTube or Instagram link.

Usage (from the repository root):
    python tools/indoor_import.py URL [--gym NAME] [--board NAME] [--grade V4]
                                  [--date YYYY-MM-DD] [--title TEXT] [--angle 40]
                                  [--board-url URL] [--save] [--overwrite]

Without --save the generated Markdown is only printed. Everything that can be
detected (title, upload date, grade, gym, board, angle) is scraped from the
video page; flags override whatever was detected.
"""

import argparse
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDOOR_CONTENT = ROOT / "content" / "climbing" / "indoor"
GYMS = ROOT / "data" / "climbing" / "gyms.yaml"
BOARDS = ROOT / "data" / "climbing" / "boards.yaml"
USER_AGENT = "Mozilla/5.0 (compatible; KevinReissClimbingImporter/1.0)"

BOULDER_GRADE = re.compile(r"(?<![A-Za-z0-9.])V\s?(\d{1,2})(?:\s?[-+])?(?![A-Za-z0-9])", re.I)
FONT_GRADE = re.compile(r"(?<![A-Za-z0-9.])([3-9][abc]\+?)(?![A-Za-z0-9])", re.I)
ROUTE_GRADE = re.compile(r"(?<![A-Za-z0-9])(5\.\d{1,2}[abcd]?(?:/[abcd])?[-+]?)(?![A-Za-z0-9])", re.I)
ANGLE = re.compile(r"(\d{2})\s?(?:°|º|deg(?:rees?)?)", re.I)


def fetch(url, accept_json=False):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError(f"Could not fetch {url}: {error}") from error


def registry_names(path):
    if not path.exists():
        return []
    names = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = re.match(r"^\s*-\s+name:\s*(.*)$", line)
        if not match:
            continue
        raw_name = match.group(1).strip()
        if raw_name.startswith('"'):
            try:
                name, end = json.JSONDecoder().raw_decode(raw_name)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid quoted name in {path.name} on line {line_number}.") from error
            trailing = raw_name[end:].strip()
            if trailing and not trailing.startswith("#"):
                raise ValueError(f"Invalid name entry in {path.name} on line {line_number}.")
        elif raw_name.startswith("'"):
            single_quoted = re.fullmatch(r"'((?:[^']|'')*)'\s*(?:#.*)?", raw_name)
            if not single_quoted:
                raise ValueError(f"Invalid quoted name in {path.name} on line {line_number}.")
            name = single_quoted.group(1).replace("''", "'")
        else:
            name = re.split(r"\s+#", raw_name, maxsplit=1)[0].strip()
        if not name:
            raise ValueError(f"Missing name in {path.name} on line {line_number}.")
        names.append(name)
    return names


def add_gym(payload):
    if not isinstance(payload, dict):
        raise ValueError("Gym details must be an object.")

    name = str(payload.get("name", "")).strip()
    if not name:
        raise ValueError("Enter a gym name.")

    values = {
        key: str(payload.get(key, "") or "").strip()
        for key in ("city", "state", "url")
    }
    if any(any(ord(character) < 32 for character in value) for value in (name, *values.values())):
        raise ValueError("Gym details cannot contain line breaks or control characters.")

    existing = registry_names(GYMS)
    if any(current.casefold() == name.casefold() for current in existing):
        raise FileExistsError(f'Gym "{name}" is already in gyms.yaml.')

    if values["url"]:
        parsed_url = urllib.parse.urlparse(values["url"])
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("Gym website must be an HTTP or HTTPS URL.")

    def quote(value):
        return json.dumps(value, ensure_ascii=False)

    lines = [f"- name: {quote(name)}"]
    lines.extend(f"  {key}: {quote(value)}" for key, value in values.items() if value)
    entry = "\n".join(lines)

    existing_text = GYMS.read_text(encoding="utf-8") if GYMS.exists() else ""
    if existing_text and not existing_text.endswith("\n\n"):
        separator = "\n" if existing_text.endswith("\n") else "\n\n"
    else:
        separator = ""
    GYMS.parent.mkdir(parents=True, exist_ok=True)
    GYMS.write_text(existing_text + separator + entry + "\n", encoding="utf-8", newline="\n")
    return {"gym": name, "gyms": registry_names(GYMS)}


def youtube_id(url):
    match = re.search(r"(?:youtube\.com/(?:shorts/|embed/|live/)|youtu\.be/|[?&]v=)([A-Za-z0-9_-]{11})", url)
    return match.group(1) if match else ""


def meta(page, prop):
    for pattern in (
        rf'<meta[^>]+(?:property|name|itemprop)=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']*)["\']',
        rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name|itemprop)=["\']{re.escape(prop)}["\']',
    ):
        match = re.search(pattern, page, re.I)
        if match:
            return html.unescape(match.group(1)).strip()
    return ""


def scrape_youtube(url):
    video_id = youtube_id(url)
    if not video_id:
        raise ValueError("That does not look like a YouTube video link.")
    info = {"youtube_url": f"https://youtube.com/shorts/{video_id}" if "/shorts/" in url else url, "text": "", "video_title": "", "video_date": ""}
    try:
        oembed = json.loads(fetch("https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(f"https://www.youtube.com/watch?v={video_id}", safe="")))
        info["video_title"] = oembed.get("title", "")
    except (RuntimeError, ValueError):
        pass
    try:
        page = fetch(f"https://www.youtube.com/watch?v={video_id}")
        info["video_date"] = meta(page, "uploadDate")[:10] or meta(page, "datePublished")[:10]
        description = re.search(r'"shortDescription":("(?:[^"\\]|\\.)*")', page)
        if description:
            info["text"] = json.loads(description.group(1))
        info["video_title"] = info["video_title"] or meta(page, "og:title")
    except RuntimeError:
        pass
    if not info["video_title"] and not info["text"]:
        raise RuntimeError("Could not read any details from that YouTube link (is it private or unavailable?).")
    return info


def scrape_instagram(url):
    info = {"instagram_url": url, "text": "", "video_title": "", "video_date": ""}
    try:
        page = fetch(url)
        info["text"] = meta(page, "og:description") or meta(page, "description")
        info["video_title"] = meta(page, "og:title")
    except RuntimeError:
        pass
    return info


def detect_grade(text):
    match = BOULDER_GRADE.search(text)
    if match:
        return f"V{match.group(1)}", "Boulder"
    match = ROUTE_GRADE.search(text)
    if match:
        return match.group(1), "Sport"
    match = FONT_GRADE.search(text)
    if match:
        grade = match.group(1)
        return grade[0] + grade[1:].upper(), "Boulder"
    return "", ""


def find_name(text, names):
    lowered = text.casefold()
    return next((name for name in names if name.casefold() in lowered), "")


def derive_title(video_title, *remove):
    """Return a name only if something meaningful is left once grade/gym/board words are removed."""
    text = video_title
    for pattern in (BOULDER_GRADE, ROUTE_GRADE, ANGLE):
        text = pattern.sub(" ", text)
    for word in remove:
        if word:
            text = re.sub(re.escape(word), " ", text, flags=re.I)
    text = re.sub(r"#\w+|\[\s*\]|\(\s*\)", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -–—|:,·")
    leftover = re.sub(r"\b(?:at|on|the|board|gym|indoor|climb|climbing|send|sent|flash)\b", " ", text, flags=re.I)
    return text if re.search(r"[A-Za-z]{2,}", leftover) else ""

def scrape_indoor(url, overrides=None):
    overrides = {key: value for key, value in (overrides or {}).items() if value}
    if "instagram.com" in url:
        info = scrape_instagram(url)
    else:
        info = scrape_youtube(url)
    haystack = f'{info["video_title"]}\n{info["text"]}'
    grade, discipline = detect_grade(info["video_title"]) if info["video_title"] else ("", "")
    if not grade:
        grade, discipline = detect_grade(haystack)
    board = find_name(haystack, registry_names(BOARDS))
    gym = "" if board else find_name(haystack, registry_names(GYMS))
    angle_match = ANGLE.search(haystack) if board else None
    fields = {
        "title": derive_title(info["video_title"], board, gym) if info["video_title"] else "",
        "climb_date": info["video_date"] or date.today().isoformat(),
        "gym": gym,
        "board": board,
        "board_angle": angle_match.group(1) if angle_match else "",
        "board_url": "",
        "discipline": discipline or "Boulder",
        "grade": grade,
        "youtube_url": info.get("youtube_url", ""),
        "instagram_url": info.get("instagram_url", ""),
    }
    fields.update(overrides)
    fields["detected"] = {key: bool(fields[key]) for key in ("title", "grade", "gym", "board", "board_angle")}
    return fields


def suggest_filename(fields):
    place = fields.get("board") or fields.get("gym") or "indoor"
    parts = [fields.get("climb_date", ""), place + ("-board" if fields.get("board") else ""), fields.get("grade", ""), fields.get("title", "")]
    stem = re.sub(r"[^a-z0-9]+", "-", "-".join(part for part in parts if part).lower()).strip("-")
    return stem[:80].strip("-") or "indoor-climb"


def unique_filename(stem):
    candidate, number = stem, 2
    while (INDOOR_CONTENT / f"{candidate}.md").exists():
        candidate, number = f"{stem}-{number}", number + 1
    return candidate


def build_indoor_markdown(fields, slug):
    def q(value):
        return json.dumps(str(value or ""), ensure_ascii=False)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    lines = ["---"]
    if fields.get("title"):
        lines.append(f'title: {q(fields["title"])}')
    lines += [f"slug: {q(slug)}", f"date: {stamp}", f'climb_date: {q(fields.get("climb_date"))}', 'setting: "Indoor"']
    if fields.get("board"):
        lines.append(f'board: {q(fields["board"])}')
        if fields.get("board_angle"):
            lines.append(f'board_angle: {q(fields["board_angle"])}')
        lines.append(f'board_url: {q(fields.get("board_url"))}')
    else:
        lines.append(f'gym: {q(fields.get("gym"))}')
    lines += [
        f'discipline: {q(fields.get("discipline"))}',
        f'grade: {q(fields.get("grade"))}',
        f'youtube_url: {q(fields.get("youtube_url"))}',
        f'instagram_url: {q(fields.get("instagram_url"))}',
        'thumbnail: ""',
        "tags:",
        '  - "Climbing"',
        "draft: false",
        "---",
        "",
        "",
    ]
    return "\n".join(lines)


def problems(fields):
    issues = []
    if not fields.get("grade"):
        issues.append("no grade detected")
    if not fields.get("board") and not fields.get("gym"):
        issues.append("no registered gym or board detected (select a gym or add it to data/climbing/gyms.yaml)")
    if fields.get("gym") and fields["gym"].casefold() not in {name.casefold() for name in registry_names(GYMS)}:
        issues.append(f'gym "{fields["gym"]}" is not in data/climbing/gyms.yaml')
    if fields.get("board") and fields["board"] not in registry_names(BOARDS):
        issues.append(f'board "{fields["board"]}" is not in data/climbing/boards.yaml')
    return issues


def preview_indoor(payload):
    url = str(payload.get("url", "")).strip()
    if not url:
        raise ValueError("Paste a YouTube or Instagram link.")
    fields = scrape_indoor(url, payload.get("overrides"))
    slug = unique_filename(suggest_filename(fields))
    return {"fields": fields, "filename": f"{slug}.md", "markdown": build_indoor_markdown(fields, slug), "issues": problems(fields), "gyms": registry_names(GYMS), "boards": registry_names(BOARDS)}


def save_indoor(payload):
    fields = payload.get("fields") or {}
    if fields.get("gym") and not fields.get("board"):
        registered_gym = next(
            (name for name in registry_names(GYMS) if name.casefold() == str(fields["gym"]).strip().casefold()),
            None,
        )
        if not registered_gym:
            raise ValueError(f'Gym "{fields["gym"]}" is not in gyms.yaml. Add it to the gym list before saving.')
        fields["gym"] = registered_gym

    filename = re.sub(r"\.md$", "", str(payload.get("filename", "")).strip())
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", filename):
        raise ValueError("Filename must contain only letters, numbers, hyphens, or underscores.")
    target = INDOOR_CONTENT / f"{filename}.md"
    if target.exists() and not payload.get("overwrite"):
        raise FileExistsError(f"{filename}.md already exists. Enable overwrite to replace it.")
    INDOOR_CONTENT.mkdir(parents=True, exist_ok=True)
    target.write_text(build_indoor_markdown(fields, filename), encoding="utf-8", newline="\n")
    return f"content/climbing/indoor/{filename}.md"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("url")
    parser.add_argument("--gym")
    parser.add_argument("--board")
    parser.add_argument("--angle", dest="board_angle")
    parser.add_argument("--board-url")
    parser.add_argument("--grade")
    parser.add_argument("--date", dest="climb_date")
    parser.add_argument("--title")
    parser.add_argument("--save", action="store_true", help="write the file into content/climbing/indoor/")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    overrides = {key: getattr(args, key) for key in ("gym", "board", "board_angle", "board_url", "grade", "climb_date", "title")}
    try:
        result = preview_indoor({"url": args.url, "overrides": overrides})
        for issue in result["issues"]:
            print(f"warning: {issue}", file=sys.stderr)
        if args.save:
            print("saved", save_indoor({"fields": result["fields"], "filename": result["filename"], "overwrite": args.overwrite}))
        else:
            print(result["markdown"])
    except (ValueError, RuntimeError, FileExistsError) as error:
        sys.exit(f"error: {error}")


if __name__ == "__main__":
    main()
