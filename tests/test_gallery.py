import csv
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import gallery  # noqa: E402

FIELDS = ["Brand", "Platform", "Title", "Content", "Week / day", "Asset ID", "Pillar",
          "Link", "Format", "Check before posting", "Also post to", "Status"]


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


class ParsingTests(unittest.TestCase):
    def test_week_day(self):
        self.assertEqual(gallery.parse_week_day("Week 3 · Tue"), (3, 1))
        self.assertEqual(gallery.parse_week_day("Week 12 · Sun"), (12, 6))
        self.assertEqual(gallery.parse_week_day("nonsense"), gallery.UNSCHEDULED)

    def test_ordering_is_numeric_then_calendar(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.csv")
            write_csv(p, [
                {"Title": "a", "Week / day": "Week 10 · Mon"},
                {"Title": "b", "Week / day": "Week 2 · Fri"},
                {"Title": "c", "Week / day": "Week 2 · Mon"},
                {"Title": "d", "Week / day": "Week 2 · Wed"},
            ])
            titles = [x["title"] for x in gallery.load_posts(p)]
        self.assertEqual(titles, ["c", "d", "b", "a"])

    def test_caption_extraction(self):
        content = "Hook: x\nCaption: Hello there.\nMore.\n\n#tag"
        self.assertEqual(gallery.extract_caption(content, "Graphic / carousel", "ADS-C01"),
                         "Hello there.\nMore.\n\n#tag")
        self.assertEqual(gallery.extract_caption("No marker", "Graphic / carousel", "X-1"), "")
        self.assertEqual(gallery.extract_caption("Whole post\nCaption: kept", "Text post", "Text only"),
                         "Whole post\nCaption: kept")

    def test_note_level(self):
        self.assertEqual(gallery.note_level("CONFLICT: homepage"), "conflict")
        self.assertEqual(gallery.note_level("Please confirm"), "flag")
        self.assertEqual(gallery.note_level("Per decision log"), "")
        self.assertEqual(gallery.note_level("Checked against creatrgrid.com"), "")
        self.assertEqual(gallery.note_level("Re-check the figure"), "flag")


class HtmlTests(unittest.TestCase):
    def test_page_contains_assets_and_escapes(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "out")
            os.makedirs(os.path.join(out, "B", "T-C01_x"))
            open(os.path.join(out, "B", "T-C01_x", "slide_01.png"), "wb").close()
            manifest = [{"asset": "T-C01", "brand": "B", "title": "T", "folder": "B/T-C01_x",
                         "frames": 1, "video": False, "text": ["Slide <one> & \"two\""], "footnote": ""}]
            with open(os.path.join(out, "manifest.json"), "w") as fh:
                json.dump(manifest, fh)
            p = os.path.join(d, "s.csv")
            write_csv(p, [
                {"Brand": "B", "Platform": "Instagram", "Title": "Tom & Jerry's <b>",
                 "Content": "Caption: It's \"quoted\" & <script>alert(1)</script>",
                 "Week / day": "Week 1 · Tue", "Asset ID": "T-C01", "Format": "Graphic / carousel",
                 "Check before posting": "CONFLICT: fix", "Also post to": "Facebook"},
                {"Brand": "B", "Platform": "X", "Title": "Plain", "Content": "Text body",
                 "Week / day": "Week 1 · Mon", "Asset ID": "Text only", "Format": "Text post"},
                {"Brand": "B", "Platform": "X", "Title": "Late", "Content": "Caption: c",
                 "Week / day": "Week 2 · Mon", "Asset ID": "T-C99", "Format": "Graphic / carousel"},
            ])
            out_file = os.path.join(d, "site", "index.html")
            page = gallery.build_html(gallery.load_posts(p), gallery.load_manifest(out), out, out_file)
            self.assertIn("T-C01", page)
            self.assertIn("../out/B/T-C01_x/slide_01.png", page)
            self.assertIn("Not rendered yet", page)
            self.assertIn("Tom &amp; Jerry&#x27;s &lt;b&gt;", page)
            self.assertNotIn("<script>alert(1)", page)
            self.assertLess(page.index("Plain"), page.index("Tom &amp;"))
            only = gallery.build_html(gallery.load_posts(p), gallery.load_manifest(out), out, out_file, week=2)
            self.assertIn("Late", only)
            self.assertNotIn("Plain", only)


if __name__ == "__main__":
    unittest.main()
