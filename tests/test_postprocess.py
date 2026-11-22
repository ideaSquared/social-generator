import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import postprocess  # noqa: E402


def make_png(path, size, colour):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, colour).save(path)


class PostprocessTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.out = Path(self._tmp.name)
        car = "Brand/T-C01_demo"
        for i in range(1, 4):
            make_png(self.out / car / f"slide_{i:02d}.png", (108, 135), (i * 40, 90, 200))
        vid = "Brand/T-V01_clip"
        make_png(self.out / vid / "frames" / "frame_01.png", (108, 192), (9, 9, 9))
        (self.out / vid / "video.mp4").write_bytes(b"x")
        manifest = [
            {"asset": "T-C01", "brand": "Brand", "title": "Demo", "folder": car,
             "frames": 3, "video": False,
             "text": ["Big title / A short body.", "Middle / More words.", "Follow Along"],
             "footnote": "Source: somewhere."},
            {"asset": "T-V01", "brand": "Brand", "title": "Clip", "folder": vid,
             "frames": 4, "video": True,
             "text": ["Hook line.", "Beat one", "Beat two", "Call to action."],
             "footnote": ""},
            {"asset": "T-C02", "brand": "Brand", "title": "Ghost", "folder": "Brand/T-C02_gone",
             "frames": 2, "video": False, "text": ["a", "b"], "footnote": ""},
        ]
        (self.out / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def test_pdf_page_count_and_aspect(self):
        pdfs, _, skipped = postprocess.run(self.out, "pdf")
        self.assertEqual((pdfs, skipped), (1, 1))
        pdf = self.out / "Brand/T-C01_demo/carousel.pdf"
        self.assertTrue(pdf.is_file())
        data = pdf.read_bytes()
        self.assertIn(b"/Count 3", data)
        self.assertEqual(data.count(b"/MediaBox [ 0 0 108.0 135.0 ]"), 3)
        self.assertFalse((self.out / "Brand/T-V01_clip/carousel.pdf").exists())

    def test_alt_text(self):
        postprocess.run(self.out, "alt")
        car = (self.out / "Brand/T-C01_demo/alt.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual(car[0], "Slide 1 of 3: Big title: A short body.")
        self.assertEqual(car[2], "Slide 3 of 3: Follow Along")
        self.assertEqual(car[-1], "Source: somewhere.")
        vid = (self.out / "Brand/T-V01_clip/alt.txt").read_text(encoding="utf-8").strip()
        self.assertEqual(vid, "Text video. Hook line. Then: Beat one; Beat two. "
                              "Ends with: Call to action.")

    def test_alt_short_limit(self):
        long_text = " ".join(f"Sentence number {i} goes here." for i in range(60))
        short = postprocess.shorten(long_text)
        self.assertLessEqual(len(short), 420)
        self.assertTrue(short.endswith("."))
        words = ("word " * 200).strip()
        short = postprocess.shorten(words)
        self.assertLessEqual(len(short), 420)
        self.assertTrue(short.endswith("word…"))

    def test_only_and_cli(self):
        rc = postprocess.main(["all", str(self.out), "--only", "T-V01"])
        self.assertEqual(rc, 0)
        self.assertTrue((self.out / "Brand/T-V01_clip/alt_short.txt").is_file())
        self.assertFalse((self.out / "Brand/T-C01_demo/alt.txt").exists())

    def test_missing_manifest_is_error(self):
        (self.out / "manifest.json").unlink()
        self.assertEqual(postprocess.main(["all", str(self.out)]), 1)


if __name__ == "__main__":
    unittest.main()
