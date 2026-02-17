import sys
from pathlib import Path
import unittest
from unittest import mock

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import build_publications as bp


class PublicationFormattingTests(unittest.TestCase):
    def test_author_list_from_crossref_truncates_with_et_al(self):
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
        result = bp._author_list_from_crossref(item)
        self.assertEqual(
            result,
            "A One, B Two, C Three, D Four, E Five, F Six, G Seven, H Eight, et al.",
        )

    def test_pick_year_from_crossref_prefers_published_print(self):
        item = {
            "published-print": {"date-parts": [[2021, 6, 1]]},
            "published-online": {"date-parts": [[2020, 1, 1]]},
            "created": {"date-parts": [[2019, 1, 1]]},
            "issued": {"date-parts": [[2018, 1, 1]]},
        }
        self.assertEqual(bp._pick_year_from_crossref(item), "2021")

    def test_description_omits_missing_parts(self):
        item = {
            "title": ["Test Title"],
            "author": [{"given": "A", "family": "One"}],
            "published-online": {"date-parts": [[2022]]},
            "container-title": [],
        }
        title = bp._title_from_crossref(item)
        authors = bp._author_list_from_crossref(item)
        year = bp._pick_year_from_crossref(item)
        venue = bp._venue_from_crossref(item)
        description = bp._join_nonempty([authors, year, venue])
        self.assertEqual(title, "Test Title")
        self.assertEqual(description, bp._join_nonempty(["A One", "2022"]))

    def test_extract_doi_from_orcid_work(self):
        work = {
            "external-ids": {
                "external-id": [
                    {"external-id-type": "doi", "external-id-value": "10.1000/XYZ"}
                ]
            }
        }
        self.assertEqual(bp._extract_doi_from_orcid_work(work), "10.1000/xyz")

    def test_is_real_doi_link(self):
        self.assertTrue(bp._is_real_doi_link("https://doi.org/10.1000/xyz"))
        self.assertFalse(bp._is_real_doi_link("https://doi.org/"))
        self.assertFalse(bp._is_real_doi_link("https://example.com/paper"))
        self.assertFalse(bp._is_real_doi_link("#"))

    def test_title_key_normalizes_case_and_whitespace(self):
        self.assertEqual(
            bp._title_key("  A   Study   On EEG  "),
            bp._title_key("a study on eeg"),
        )


class PublicationBuildTests(unittest.TestCase):
    @mock.patch("build_publications._crossref_lookup_by_doi")
    @mock.patch("build_publications._orcid_get_work")
    @mock.patch("build_publications._orcid_get_one_putcode_per_group")
    def test_build_publications_skips_item_without_doi(
        self, mock_putcodes, mock_get_work, mock_crossref
    ):
        mock_putcodes.return_value = [1]
        mock_get_work.side_effect = [
            {
                "title": {"title": {"value": "No DOI Title"}},
                "publication-date": {"year": {"value": "2024"}},
                "type": "journal-article",
                "external-ids": {"external-id": []},
                "url": {"value": "https://example.com/no-doi"},
            }
        ]
        mock_crossref.return_value = None

        publications = bp.build_publications()
        self.assertEqual(len(publications), 0)

    @mock.patch("build_publications._crossref_lookup_by_doi")
    @mock.patch("build_publications._orcid_get_work")
    @mock.patch("build_publications._orcid_get_one_putcode_per_group")
    def test_build_publications_skips_item_when_crossref_missing_or_journal_missing(
        self, mock_putcodes, mock_get_work, mock_crossref
    ):
        mock_putcodes.return_value = [1, 2]
        mock_get_work.side_effect = [
            {
                "title": {"title": {"value": "No Crossref Title"}},
                "publication-date": {"year": {"value": "2024"}},
                "type": "journal-article",
                "external-ids": {
                    "external-id": [
                        {"external-id-type": "doi", "external-id-value": "10.1000/no-cr"}
                    ]
                },
            },
            {
                "title": {"title": {"value": "No Journal Title"}},
                "publication-date": {"year": {"value": "2022"}},
                "type": "journal-article",
                "external-ids": {
                    "external-id": [
                        {"external-id-type": "doi", "external-id-value": "10.1000/no-journal"}
                    ]
                },
            },
        ]
        mock_crossref.side_effect = [
            None,
            {
                "title": ["No Journal Title"],
                "author": [{"given": "A", "family": "One"}],
                "published-online": {"date-parts": [[2022]]},
                "container-title": [],
            },
        ]

        publications = bp.build_publications()
        self.assertEqual(len(publications), 0)

    @mock.patch("build_publications._crossref_lookup_by_doi")
    @mock.patch("build_publications._orcid_get_work")
    @mock.patch("build_publications._orcid_get_one_putcode_per_group")
    def test_build_publications_dedups_same_title_keeps_first_sorted_entry(
        self, mock_putcodes, mock_get_work, mock_crossref
    ):
        mock_putcodes.return_value = [1, 2]
        mock_get_work.side_effect = [
            {
                "title": {"title": {"value": "Shared Title"}},
                "publication-date": {"year": {"value": "2024"}},
                "type": "journal-article",
                "external-ids": {
                    "external-id": [
                        {"external-id-type": "doi", "external-id-value": "10.1000/newer"}
                    ]
                },
            },
            {
                "title": {"title": {"value": "Shared Title"}},
                "publication-date": {"year": {"value": "2022"}},
                "type": "journal-article",
                "external-ids": {
                    "external-id": [
                        {"external-id-type": "doi", "external-id-value": "10.1000/older"}
                    ]
                },
            },
        ]
        mock_crossref.side_effect = [
            {
                "title": ["Shared Title"],
                "author": [{"given": "A", "family": "One"}],
                "published-online": {"date-parts": [[2024]]},
                "container-title": ["Journal X"],
            },
            {
                "title": ["Shared Title"],
                "author": [{"given": "B", "family": "Two"}],
                "published-online": {"date-parts": [[2022]]},
                "container-title": ["Journal X"],
            },
        ]

        publications = bp.build_publications()
        self.assertEqual(len(publications), 1)
        self.assertEqual(publications[0]["name"], "Shared Title")
        self.assertEqual(publications[0]["link"], "https://doi.org/10.1000/newer")


if __name__ == "__main__":
    unittest.main()
