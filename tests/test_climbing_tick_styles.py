import csv
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import climbing_tools


class FakeResponse:
    def __init__(self, body=b"", url="https://www.mountainproject.com"):
        self.body = body
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def geturl(self):
        return self.url

    def read(self):
        return self.body


def tick_row(route_url, date, style):
    return (
        '<tr class="route-row"><td><a href="'
        + route_url
        + '"><i>'
        + date
        + " &middot; "
        + style
        + ".</i></a></td></tr>"
    )


class ClimbingTickStyleTests(unittest.TestCase):
    def test_public_tick_rows_provide_route_date_and_normalized_style(self):
        page = (
            '<table class="table route-table hidden-sm-up">'
            + tick_row(
                "https://www.mountainproject.com/route/105908757/apocalypse-later",
                "Oct 4, 2026",
                "Lead / Fell/Hung. Fell on the last hold",
            )
            + tick_row(
                "https://www.mountainproject.com/route/105898433/espresso",
                "Oct 4, 2026",
                "Lead",
            )
            + "</table>"
        )

        parser = climbing_tools.MountainProjectTickPageParser()
        parser.feed(page)

        self.assertEqual(
            parser.tick_rows(),
            [{
                "url": "https://www.mountainproject.com/route/105908757/apocalypse-later",
                "date": "2026-10-04",
                "ascent_type": "Fell/Hung",
            }, {
                "url": "https://www.mountainproject.com/route/105898433/espresso",
                "date": "2026-10-04",
                "ascent_type": "",
            }],
        )

    def test_rss_import_matches_multiple_same_day_ticks_without_collapsing(self):
        route_url = "https://www.mountainproject.com/route/105908757/apocalypse-later"
        feed = f"""<rss><channel>
            <item><title>Tick: Apocalypse Later (5.11d)</title><link>{route_url}</link>
                <guid>MPObject_203950583</guid><pubDate>Sun, 04 Oct 2026 21:12:00 GMT</pubDate></item>
            <item><title>Tick: Apocalypse Later (5.11d)</title><link>{route_url}</link>
                <guid>MPObject_203949240</guid><pubDate>Sun, 04 Oct 2026 19:32:00 GMT</pubDate></item>
        </channel></rss>""".encode()
        page_one = (
            '<a href="https://www.mountainproject.com/user/123/kevin-reiss/ticks?page=2">Last</a>'
            '<table class="table route-table hidden-sm-up">'
            + tick_row(route_url, "Oct 4, 2026", "Lead / Redpoint")
            + tick_row(route_url, "Oct 4, 2026", "Lead / Fell/Hung")
            + "</table>"
        ).encode()
        page_two = (
            '<table class="table route-table hidden-sm-up">'
            + tick_row(route_url, "Sep 30, 2026", "Lead / Onsight")
            + "</table>"
        ).encode()
        responses = [
            FakeResponse(feed),
            FakeResponse(url="https://www.mountainproject.com/user/123/kevin-reiss"),
            FakeResponse(page_one),
            FakeResponse(page_two),
        ]

        with patch.object(climbing_tools.urllib.request, "urlopen", side_effect=responses):
            with patch.object(climbing_tools, "fetch_route_breadcrumb", return_value=[]):
                with patch.object(climbing_tools.time, "sleep"):
                    result = climbing_tools.build_rss_tick_csv(
                        "https://www.mountainproject.com/rss/user-ticks/123"
                    )

        rows = list(csv.DictReader(io.StringIO(result["csv"])))
        self.assertEqual(result["count"], 2)
        self.assertEqual([row["Lead Style"] for row in rows], ["Redpoint", "Fell/Hung"])
        self.assertEqual([row["Tick ID"] for row in rows], ["MPObject_203950583", "MPObject_203949240"])
        self.assertEqual(result["warnings"], [])

    def test_repeat_import_enriches_existing_blank_style_without_adding_tick(self):
        route_url = "https://www.mountainproject.com/route/105908757/apocalypse-later"
        text = """---
climb_date: "2026-10-04"
ascent_type: ""
personal_note: ""
mountain_project_url: "https://www.mountainproject.com/route/105908757/apocalypse-later"
ascents: [{"id":"MPObject_203950583","date":"2026-10-04","ascent_type":"","personal_note":""}]
draft: false
---
"""

        updated, added, changed = climbing_tools.merge_ascent_history(
            text,
            [{
                "id": "MPObject_203950583",
                "date": "2026-10-04",
                "ascent_type": "Redpoint",
                "personal_note": "",
            }],
            route_url,
        )

        self.assertTrue(changed)
        self.assertEqual(added, 0)
        self.assertEqual(
            climbing_tools.read_ascent_history(updated, route_url)[0]["ascent_type"],
            "Redpoint",
        )
        self.assertEqual(
            climbing_tools.read_frontmatter_value(updated, "ascent_type"),
            "Redpoint",
        )

    def test_ambiguous_route_date_match_leaves_styles_blank(self):
        route_url = "https://www.mountainproject.com/route/105908757/apocalypse-later"
        rows = [[""] * 17, [""] * 17]
        warnings = []

        climbing_tools.apply_public_tick_styles(
            rows,
            [(0, route_url, "2026-10-04"), (1, route_url, "2026-10-04")],
            [{
                "url": route_url,
                "date": "2026-10-04",
                "ascent_type": "Redpoint",
            }],
            warnings,
        )

        self.assertEqual([row[10] for row in rows], ["", ""])
        self.assertTrue(warnings)


if __name__ == "__main__":
    unittest.main()
