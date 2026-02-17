import sys
from pathlib import Path
import unittest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import build_publications as bp


class PublicationFormattingTests(unittest.TestCase):
    def test_author_list_truncates_with_et_al(self):
        item = {
            "author": [
                {"given": "A", "family": "One"},
                {"given": "B", "family": "Two"},
                {"given": "C", "family": "Three"},
                {"given": "D", "family": "Four"},
                {"given": "E", "family": "Five"},
                {"given": "F", "family": "Six"},
                {"given": "G", "family": "Seven"},
                {"given": "H", "family": "Eight"},
                {"given": "I", "family": "Nine"},
            ]
        }
        result = bp._author_list(item)
        self.assertEqual(
            result,
            "A One, B Two, C Three, D Four, E Five, F Six, G Seven, H Eight, et al.",
        )

    def test_pick_year_prefers_published_print(self):
        item = {
            "published-print": {"date-parts": [[2021, 6, 1]]},
            "published-online": {"date-parts": [[2020, 1, 1]]},
            "created": {"date-parts": [[2019, 1, 1]]},
            "issued": {"date-parts": [[2018, 1, 1]]},
        }
        self.assertEqual(bp._pick_year(item), "2021")

    def test_description_omits_missing_parts(self):
        item = {
            "title": ["Test Title"],
            "author": [{"given": "A", "family": "One"}],
            "published-online": {"date-parts": [[2022]]},
            "container-title": [],
        }
        title = bp._title(item)
        authors = bp._author_list(item)
        year = bp._pick_year(item)
        venue = bp._venue(item)
        description_parts = [part for part in (authors, year, venue) if part]
        description = " — ".join(description_parts)
        self.assertEqual(title, "Test Title")
        self.assertEqual(description, "A One — 2022")

    def test_link_prefers_doi(self):
        item = {"DOI": "10.1000/xyz", "URL": "https://example.com"}
        self.assertEqual(bp._link(item), "https://doi.org/10.1000/xyz")


if __name__ == "__main__":
    unittest.main()
