import csv
import unittest
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]


def read_rectangular_csv(name: str):
    path = ROOT / name
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    if not rows:
        raise AssertionError(f"empty CSV: {name}")
    width = len(rows[0])
    for line_number, row in enumerate(rows[1:], start=2):
        if len(row) != width:
            raise AssertionError(
                f"non-rectangular CSV {name} line {line_number}: "
                f"expected {width} fields, found {len(row)}"
            )
    header = rows[0]
    return [dict(zip(header, row)) for row in rows[1:]]


class EvidenceLedgerTests(unittest.TestCase):
    def test_evidence_ledgers_are_rectangular_complete_and_unique(self):
        references = read_rectangular_csv("reference_audit.csv")
        literature = read_rectangular_csv("literature_matrix.csv")
        resources = read_rectangular_csv("external_resources.csv")
        claims = read_rectangular_csv("claim_evidence_ledger.csv")

        self.assertEqual(len(references), 36)
        self.assertEqual(len(literature), 22)
        self.assertEqual(len(resources), 29)
        self.assertEqual(len(claims), 26)

        for collection in (references, literature, resources, claims):
            for row in collection:
                self.assertTrue(all(value.strip() for value in row.values()))

        self.assertEqual(len({row["bib_key"] for row in references}), len(references))
        self.assertEqual(
            len({row["doi_or_stable_url"] for row in references}), len(references)
        )
        for row in references:
            parsed = urlparse(row["doi_or_stable_url"])
            self.assertEqual(parsed.scheme, "https")
            self.assertTrue(parsed.netloc)
            self.assertTrue(row["metadata_status"].startswith("verified-"))

        self.assertEqual(
            Counter(row["quota"] for row in literature),
            {"same-venue": 12, "influential-or-award": 5, "adjacent-venue": 5},
        )
        self.assertTrue(all(row["full_text_checked"] == "YES" for row in literature))
        self.assertEqual(len({row["doi"] for row in literature}), len(literature))

        self.assertEqual(
            len({row["resource_id"] for row in resources}), len(resources)
        )
        self.assertTrue(all(row["internals_modified"] == "No" for row in resources))
        for row in resources:
            parsed = urlparse(row["scholarly_or_official_url"])
            self.assertEqual(parsed.scheme, "https")
            self.assertTrue(parsed.netloc)

        self.assertEqual(len({row["claim_id"] for row in claims}), len(claims))
        self.assertTrue(all("2026-09-19" in row["fresh_recheck"] for row in claims))


if __name__ == "__main__":
    unittest.main()
