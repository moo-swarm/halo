"""Unit tests for scripts/moo-export-data.py — halo-hardening AC4/AC5.

Stdlib only by design (host has no pytest — tech-plan DR-2). The module
filename contains hyphens, so it is loaded via importlib; all file paths are
redirected to temp dirs so no test touches the real data/swarm.json or the
 Align-Rail project tree.
"""

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HALO_DIR = Path(__file__).resolve().parent.parent
SCRIPT = HALO_DIR / "scripts" / "moo-export-data.py"


def load_module():
    spec = importlib.util.spec_from_file_location("moo_export_data", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ComputeSpecsTest(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.proj = Path(self.tmp.name)
        moo = self.proj / ".moo-swarm"
        for sub, names in (
            ("features", ["2026-07-01-alpha", "2026-07-05-beta"]),
            ("archive", ["2026-06-01-old"]),
        ):
            for name in names:
                (moo / sub / name).mkdir(parents=True)

    def test_counts_features_and_archive_and_latest_date(self):
        specs = self.mod.compute_specs(self.proj)
        self.assertEqual(3, specs["total"])
        self.assertEqual(2, specs["active"])
        self.assertEqual("2026-07-05", specs["latest"])

    def test_empty_project_yields_zeroed_specs(self):
        empty = Path(self.tmp.name) / "bare"
        empty.mkdir()
        specs = self.mod.compute_specs(empty)
        self.assertEqual({"total": 0, "active": 0, "latest": None}, specs)


class InferPipelineOwnerTest(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.proj = Path(self.tmp.name)

    def _commit_as(self, email):
        subprocess.run(["git", "init", "-q"], cwd=self.proj, check=True)
        subprocess.run(["git", "config", "user.email", email], cwd=self.proj, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=self.proj, check=True)
        subprocess.run(
            ["git", "commit", "--allow-empty", "-q", "-m", "x"],
            cwd=self.proj,
            check=True,
        )

    def test_maps_lex_commit_to_moo_alias(self):
        self._commit_as("lex@example.com")
        self.assertEqual("moo", self.mod.infer_pipeline_owner(self.proj))

    def test_unknown_author_returns_none(self):
        self._commit_as("stranger@example.com")
        self.assertIsNone(self.mod.infer_pipeline_owner(self.proj))


class FetchIssuesTest(unittest.TestCase):
    def test_returns_zero_when_gh_fails(self):
        mod = load_module()
        failed = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
        with mock.patch.object(mod.subprocess, "run", return_value=failed):
            self.assertEqual(0, mod.fetch_issues("halo"))


class MainEnrichmentTest(unittest.TestCase):
    def test_enriches_defaults_preserving_existing_fields(self):
        mod = load_module()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        data = {
            "projects": [{"name": "halo", "open_issues": 7, "custom": "keep"}],
            "agents": [{"name": "moo"}],
        }
        data_file = root / "swarm.json"
        data_file.write_text(json.dumps(data))
        projects_dir = root / "projects"
        projects_dir.mkdir()

        with mock.patch.object(mod, "DATA_FILE", data_file), mock.patch.object(
            mod, "PROJECTS_DIR", projects_dir
        ):
            mod.main()

        out = json.loads(data_file.read_text())
        project = out["projects"][0]
        self.assertEqual("2.0", out["schema_version"])
        self.assertEqual(7, project["open_issues"])  # preset value untouched
        self.assertEqual("keep", project["custom"])
        self.assertEqual({"total": 0, "active": 0, "latest": None}, project["specs"])
        self.assertEqual(
            {
                "tokens": 0,
                "cost": 0.0,
                "pricing_configured": False,
                "limit_tokens": 200000,
                "limit_cost": 0.60,
            },
            project["budget_daily"],
        )
        self.assertEqual(200000, out["agents"][0]["budget_daily"]["limit_tokens"])
        self.assertIn("updated_at", out)
        self.assertIn("generated_by", out["meta"])


class MissingDataFileTest(unittest.TestCase):
    def test_missing_data_file_exits_cleanly(self):
        """AC4: clean SystemExit(1), not NameError (tech-plan finding #4)."""
        mod = load_module()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        missing = Path(tmp.name) / "nope.json"
        with mock.patch.object(mod, "DATA_FILE", missing):
            with self.assertRaises(SystemExit) as ctx:
                mod.main()
        self.assertEqual(1, ctx.exception.code)


if __name__ == "__main__":
    unittest.main()
