"""Tests for sheltermap.py — stdlib unittest, run with: python -m unittest test_sheltermap -v"""
import csv
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheltermap


class ValidateTests(unittest.TestCase):
    def test_valid_record_passes(self):
        rec = {"name": "X", "type": "emergency", "capacity": 10, "access": "wheelchair", "contact": "a@b.c"}
        self.assertEqual(sheltermap.validate([rec]), [])

    def test_missing_fields_flagged(self):
        problems = sheltermap.validate([{"name": "X"}])
        self.assertEqual(len(problems), 1)
        self.assertIn("missing", problems[0])

    def test_bad_type_flagged(self):
        rec = {"name": "X", "type": "hotel", "capacity": 10, "access": "a", "contact": "a@b.c"}
        self.assertIn("unknown type", sheltermap.validate([rec])[0])

    def test_negative_capacity_flagged(self):
        rec = {"name": "X", "type": "emergency", "capacity": -1, "access": "a", "contact": "a@b.c"}
        self.assertIn("capacity", sheltermap.validate([rec])[0])


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.records = sheltermap.load_city("berlin")

    def test_search_matches_any_field(self):
        hits = sheltermap.search(self.records, "wheelchair")
        self.assertTrue(len(hits) >= 2)

    def test_search_case_insensitive(self):
        self.assertEqual(
            sheltermap.search(self.records, "KREUZBERG"),
            sheltermap.search(self.records, "kreuzberg"),
        )

    def test_search_no_hits(self):
        self.assertEqual(sheltermap.search(self.records, "zzz-nothing"), [])


class FilterTests(unittest.TestCase):
    def setUp(self):
        self.records = sheltermap.load_city("berlin")

    def test_filter_by_type(self):
        hits = sheltermap.filter_by(self.records, ["type=emergency"])
        self.assertTrue(hits)
        self.assertTrue(all(r["type"] == "emergency" for r in hits))

    def test_multi_value_field_match(self):
        hits = sheltermap.filter_by(self.records, ["access=screen-reader"])
        self.assertTrue(all("screen-reader" in r["access"] for r in hits))

    def test_and_semantics(self):
        hits = sheltermap.filter_by(self.records, ["type=emergency", "access=wheelchair"])
        self.assertTrue(all(r["type"] == "emergency" for r in hits))
        self.assertTrue(all("wheelchair" in r["access"] for r in hits))

    def test_bad_filter_raises(self):
        with self.assertRaises(ValueError):
            sheltermap.filter_by(self.records, ["noequalsign"])


class StatsTests(unittest.TestCase):
    def test_stats_shape(self):
        records = sheltermap.load_city("berlin")
        s = sheltermap.stats(records)
        self.assertEqual(s["records"], len(records))
        self.assertEqual(s["total_capacity"], sum(r["capacity"] for r in records))
        self.assertIn("emergency", s["capacity_by_type"])

    def test_wheelchair_count(self):
        records = sheltermap.load_city("berlin")
        expected = sum(1 for r in records if "wheelchair" in [t.strip() for t in r["access"].split(",")])
        self.assertEqual(sheltermap.stats(records)["wheelchair_accessible"], expected)


class CliTests(unittest.TestCase):
    def test_list_cities(self):
        out = self._run(["--list-cities"])
        self.assertIn("berlin", out)
        self.assertIn("delhi", out)

    def test_city_json_output(self):
        out = self._run(["--city", "berlin"])
        data = json.loads(out)
        self.assertEqual(data["format"], "sheltermap-open-dataset/v1")

    def test_search_then_csv(self):
        out = self._run(["--city", "berlin", "--search", "wheelchair", "--format", "csv"])
        rows = list(csv.DictReader(io.StringIO(out)))
        self.assertTrue(len(rows) >= 2)
        self.assertIn("wheelchair", rows[0]["access"])

    def test_out_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "out.json"
            self._run(["--city", "delhi", "--out", str(dest)])
            self.assertEqual(json.loads(dest.read_text())["record_count"], 5)

    def test_missing_city_errors(self):
        rc, out, err = self._run_rc(["--city", "atlantis"])
        self.assertEqual(rc, 1)
        self.assertIn("no dataset", err)

    def test_requires_city_or_data(self):
        rc, out, err = self._run_rc([])
        self.assertEqual(rc, 2)  # argparse error

    def _run(self, argv):
        rc, out, _ = self._run_rc(argv)
        self.assertEqual(rc, 0)
        return out

    def _run_rc(self, argv):
        import contextlib
        buf_out, buf_err = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
                rc = sheltermap.main(argv)
        except SystemExit as exc:  # argparse exits with 2 on usage errors
            rc = exc.code
        return rc, buf_out.getvalue(), buf_err.getvalue()


class DataFileTests(unittest.TestCase):
    """The bundled datasets themselves must validate."""

    def test_bundled_datasets_valid(self):
        for city in sheltermap.list_cities():
            records = sheltermap.load_city(city)
            self.assertTrue(records, f"{city} dataset is empty")


if __name__ == "__main__":
    unittest.main()
