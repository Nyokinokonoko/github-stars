import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import stars  # noqa: E402


class StarsTimestampTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.data_dir = self.root / "data"
        self.data_dir.mkdir()
        self.stars_path = self.data_dir / "stars.json"
        self.categories_path = self.data_dir / "categories.json"
        self.categories_path.write_text(json.dumps({
            "categories": [{"name": "Developer Tools", "description": "Tools"}]
        }))
        self.repo = {
            "full_name": "owner/repo",
            "url": "https://github.com/owner/repo",
            "description": "A repository",
            "language": "Python",
            "stars": 10,
            "topics": ["tooling"],
            "starred_at": "2026-01-01T00:00:00Z",
            "category": "Developer Tools",
            "tags": ["tooling"],
            "summary": "A useful tool.",
            "categorized_at": "2026-01-01T00:00:00+00:00",
            "model": "test-model",
        }
        self.original_generated_at = "2026-01-02T00:00:00+00:00"
        self.write_database(self.repo)

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_database(self, repo):
        self.stars_path.write_text(json.dumps({
            "meta": {
                "user": "test-user",
                "generated_at": self.original_generated_at,
                "count": 1,
                "model": "test-model",
            },
            "repos": {repo["full_name"]: repo},
        }, indent=2) + "\n")

    def run_update(self, fetched_repo):
        env = {
            "GH_USER": "test-user",
            "GITHUB_TOKEN": "",
            "OPENROUTER_API_KEY": "",
            "OPENROUTER_MODEL": "test-model",
        }
        with (
            patch.object(stars, "ROOT", self.root),
            patch.object(stars, "DATA_DIR", self.data_dir),
            patch.object(stars, "STARS_PATH", self.stars_path),
            patch.object(stars, "CATEGORIES_PATH", self.categories_path),
            patch.object(stars, "CATALOG_DIR", self.root / "catalog"),
            patch.object(stars.github_mod, "fetch_starred", return_value=[fetched_repo]),
            patch.object(stars.catalog_mod, "generate") as generate_catalog,
            patch.object(stars.catalog_mod, "write_site_data"),
            patch.object(sys, "argv", ["stars.py"]),
            patch.dict(os.environ, env),
        ):
            self.assertEqual(stars.main(), 0)
        return json.loads(self.stars_path.read_text()), generate_catalog.call_args.args[4]

    def test_preserves_timestamp_when_visible_data_is_unchanged(self):
        original_database = self.stars_path.read_text()
        updated, catalog_timestamp = self.run_update({
            key: self.repo[key] for key in stars.META_FIELDS if key in self.repo
        } | {"full_name": self.repo["full_name"]})

        self.assertEqual(updated["meta"]["generated_at"], self.original_generated_at)
        self.assertEqual(catalog_timestamp, self.original_generated_at)
        self.assertEqual(self.stars_path.read_text(), original_database)

    def test_advances_timestamp_when_visible_data_changes(self):
        fetched = {key: self.repo[key] for key in stars.META_FIELDS if key in self.repo}
        fetched.update({"full_name": self.repo["full_name"], "stars": 11})

        updated, catalog_timestamp = self.run_update(fetched)

        self.assertNotEqual(updated["meta"]["generated_at"], self.original_generated_at)
        self.assertEqual(catalog_timestamp, updated["meta"]["generated_at"])
        self.assertEqual(updated["repos"]["owner/repo"]["stars"], 11)


if __name__ == "__main__":
    unittest.main()
