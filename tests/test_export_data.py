"""Unit tests for scripts/moo-export-data.py — halo-hardening AC4/AC5.

Stdlib only by design (host has no pytest — tech-plan DR-2). The module
filename contains hyphens, so it is loaded via importlib; all file paths are
redirected to temp dirs so no test touches the real data/swarm.json or the
 Align-Rail project tree.
"""

import importlib.util
import json
import os
import sqlite3
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
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
        # Live-exporter note: main() now fetches real org issues via gh; a
        # unit test must not touch the network. Mocking subprocess.run to
        # fail puts the run on the documented last-good path, which is
        # exactly what this test's "preset value untouched" assertion covers.
        failed = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")

        with mock.patch.object(mod.subprocess, "run", return_value=failed), mock.patch.object(
            mod, "DATA_FILE", data_file
        ), mock.patch.object(mod, "PROJECTS_DIR", projects_dir):
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


# ───────────────────────────────────────────────────────────────────────────
# Live-exporter extensions (2026-08-23-live-exporter).
# Test names mirror the tech-plan §3 AC-to-test traceability table verbatim —
# Bagnik gates code QA against that table.
# ───────────────────────────────────────────────────────────────────────────

FROZEN_NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
LAST_MS = 1750000000000   # → 2025-06-15T15:06:40Z
NEXT_MS = 1760000000000   # → 2025-10-09T08:53:20Z


def make_gh_fake(responses, calls=None):
    """subprocess.run stand-in dispatching gh api paths → JSON bodies.

    `responses` maps the exact gh path argument to a JSON-serialisable body.
    Any unmatched path or non-gh command (e.g. infer_pipeline_owner's git)
    returns returncode 1. When `calls` list is given every invocation is
    appended so budget tests can count (AC19).
    """
    def fake_run(cmd, **kwargs):
        if calls is not None:
            calls.append(list(cmd))
        if cmd[:2] != ["gh", "api"]:
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="no")
        body = responses.get(cmd[2])
        if body is None:
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="no")
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout=json.dumps(body), stderr=""
        )
    return fake_run


def cron_row(**over):
    """A cron_jobs row shaped like the live table, private columns populated
    with PII so whitelist tests can prove they never leak."""
    row = {
        "name": "job-a",
        "enabled": 1,
        "schedule_kind": "cron",
        "schedule_expr": "0 2 * * 0",
        "schedule_tz": "Europe/Madrid",
        "every_ms": None,
        "next_run_at_ms": NEXT_MS,
        "last_run_at_ms": LAST_MS,
        "last_run_status": "ok",
        "consecutive_errors": 0,
        # private columns — must never appear in exported output:
        "payload_message": "wake up moo telegram:11122333",
        "delivery_to": "telegram:999888777",
        "job_json": '{"secret":"x"}',
        "state_json": '{"state":"y"}',
        "description": "private description text",
        "last_error": "boom at /home/lex/secret/path",
    }
    row.update(over)
    return row


def make_cron_db(path, rows):
    con = sqlite3.connect(str(path))
    cols = list(cron_row())
    con.execute(f"CREATE TABLE cron_jobs ({', '.join(cols)})")
    for r in rows:
        con.execute(
            f"INSERT INTO cron_jobs ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            [r[c] for c in cols],
        )
    con.commit()
    con.close()
    return path


class GhLayerTest(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()

    def test_org_repos_single_paged_call_respects_denylist(self):
        calls = []
        fake = make_gh_fake(
            {"orgs/moo-swarm/repos?per_page=100": [{"name": n} for n in
             [".github", "halo", "brain-runtime"]]},
            calls=calls,
        )
        with mock.patch.object(self.mod.subprocess, "run", side_effect=fake):
            repos = self.mod.fetch_org_repos((".github",))
        self.assertEqual(["halo", "brain-runtime"], repos)
        self.assertEqual(1, len(calls), "exactly one paged org-repos call")
        self.assertEqual("orgs/moo-swarm/repos?per_page=100", calls[0][2])

    def test_map_issue_fields_and_excludes_pull_request_items(self):
        issue = {
            "number": 7,
            "title": "Fix it",
            "labels": [{"name": "bug"}, {"name": "ui"}],
            "created_at": "2026-08-01T00:00:00Z",
            "html_url": "https://github.com/moo-swarm/halo/issues/7",
        }
        mapped = self.mod.map_issue("halo", issue)
        self.assertEqual(
            {
                "project": "halo",
                "number": 7,
                "title": "Fix it",
                "labels": ["bug", "ui"],
                "created_at": "2026-08-01T00:00:00Z",
                "url": "https://github.com/moo-swarm/halo/issues/7",
            },
            mapped,
        )
        pr_shaped = dict(issue, pull_request={"url": "x"})
        self.assertIsNone(self.mod.map_issue("halo", pr_shaped))

    def test_map_pr_draft_and_open_status(self):
        base = {
            "number": 3,
            "title": "Add thing",
            "user": {"login": "bthos"},
            "created_at": "2026-08-02T00:00:00Z",
            "html_url": "https://github.com/moo-swarm/halo/pull/3",
        }
        draft = self.mod.map_pr("halo", dict(base, draft=True))
        self.assertEqual("draft", draft["status"])
        self.assertEqual("bthos", draft["author"])
        opened = self.mod.map_pr("halo", dict(base, draft=False))
        self.assertEqual("open", opened["status"])

    def test_caps_50_newest_first_overall(self):
        def items(offset, count):
            return [
                {
                    "number": i,
                    "title": f"t{i}",
                    "labels": [],
                    "created_at": (
                        datetime(2026, 1, 1, tzinfo=timezone.utc)
                        + timedelta(minutes=offset + i)
                    ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "html_url": "u",
                }
                for i in range(count)
            ]

        responses = {"orgs/moo-swarm/repos?per_page=100": [{"name": "a"}, {"name": "b"}]}
        for repo in ("a", "b"):
            responses[f"repos/moo-swarm/{repo}/issues?state=open&per_page=100"] = items(
                0 if repo == "a" else 100, 55
            )
            responses[f"repos/moo-swarm/{repo}/pulls?state=open&per_page=100"] = items(
                200 if repo == "a" else 300, 30
            )
        fake = make_gh_fake(responses)
        with mock.patch.object(self.mod.subprocess, "run", side_effect=fake):
            result = self.mod.fetch_issues_and_prs(["a", "b"])

        self.assertEqual(50, len(result["issues"]), "ISSUE_CAP overall")
        created = [i["created_at"] for i in result["issues"]]
        self.assertEqual(sorted(created, reverse=True), created, "newest first")
        self.assertTrue(all(i["project"] == "b" for i in result["issues"]),
                        "cap keeps the globally newest items")
        self.assertEqual(50, len(result["prs"]), "PR_CAP overall")
        self.assertEqual({"a": 55, "b": 55}, result["counts"], "counts are pre-cap")

    def test_call_budget_le_40_documented_formula_counter_scoped_to_gh_layer_only(self):
        # Budget formula (tech-plan §1.5 / AC19): 1 org call + 2N per-repo
        # calls = 1 + 2N per run; ≤ 40 ⇔ N ≤ 19 scanned repos.
        names = [f"repo-{i}" for i in range(16)] + ["skip-me"]
        responses = {"orgs/moo-swarm/repos?per_page=100": [{"name": n} for n in names]}
        for repo in names:
            responses[f"repos/moo-swarm/{repo}/issues?state=open&per_page=100"] = []
            responses[f"repos/moo-swarm/{repo}/pulls?state=open&per_page=100"] = []
        calls = []
        fake = make_gh_fake(responses, calls=calls)
        with mock.patch.object(self.mod.subprocess, "run", side_effect=fake):
            repos = self.mod.fetch_org_repos(("skip-me",))     # gh layer only
            self.mod.fetch_issues_and_prs(repos)               # gh layer only
        n = len(repos)
        self.assertEqual(1 + 2 * n, len(calls), "1 + 2N gh calls actually made")
        self.assertLessEqual(len(calls), 40, "1+2N ≤ 40 ⇔ N ≤ 19; today N=15 ⇒ 31")


class CronExtractionTest(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.db = make_cron_db(
            self.tmp / "openclaw.sqlite",
            [
                cron_row(name="alpha-cron"),
                cron_row(name="beta-every", schedule_kind="every", schedule_expr=None,
                         schedule_tz=None, every_ms=1800000),
                cron_row(name="gamma-failing", last_run_status="error",
                         consecutive_errors=10),
                cron_row(name="delta-disabled", enabled=0),
            ],
        )

    def extract(self):
        return {j["name"]: j for j in self.mod.extract_cron_jobs(self.db)}

    def test_cron_expr_with_tz_becomes_schedule_human(self):
        job = self.extract()["alpha-cron"]
        self.assertEqual("0 2 * * 0 (Europe/Madrid)", job["schedule_human"])
        self.assertEqual("0 2 * * 0", job["schedule"])

    def test_every_ms_rendered_human_readable(self):
        job = self.extract()["beta-every"]
        self.assertEqual("every 30m", job["schedule_human"])
        self.assertEqual(1800000, job["schedule"])

    def test_disabled_job_reports_status_disabled(self):
        self.assertEqual("disabled", self.extract()["delta-disabled"]["status"])

    def test_ok_and_fail_status_from_last_run_status(self):
        jobs = self.extract()
        self.assertEqual("ok", jobs["alpha-cron"]["status"])
        self.assertEqual("fail", jobs["gamma-failing"]["status"])

    def test_ms_to_iso_utc_z_and_next_run_consecutive_errors(self):
        jobs = self.extract()
        alpha = jobs["alpha-cron"]
        self.assertEqual("2025-06-15T15:06:40Z", alpha["last_run"])
        self.assertEqual("2025-10-09T08:53:20Z", alpha["next_run"])
        self.assertEqual(0, alpha["consecutive_errors"])
        gamma = jobs["gamma-failing"]
        self.assertEqual(10, gamma["consecutive_errors"])
        self.assertIsNone(self.mod.ms_to_iso(None))

    def test_missing_db_raises_operational_error(self):
        with self.assertRaises(sqlite3.OperationalError):
            self.mod.extract_cron_jobs(self.tmp / "nope.sqlite")

    def test_output_keys_are_whitelist_even_when_private_columns_populated(self):
        allowed = {"name", "schedule_human", "schedule", "last_run",
                   "status", "next_run", "consecutive_errors"}
        blob = json.dumps(self.mod.extract_cron_jobs(self.db))
        for job in json.loads(blob):
            self.assertTrue(set(job) <= allowed, f"leaked keys: {set(job) - allowed}")
        for secret in ("telegram:", "payload_message", "private description",
                       '"secret"', "999888777"):
            self.assertNotIn(secret, blob)

    def test_connect_uses_readonly_mode_uri(self):
        real_connect = self.mod.sqlite3.connect
        captured = {}

        def spy(path, *args, **kwargs):
            captured["path"] = path
            captured["kwargs"] = kwargs
            return real_connect(path, *args, **kwargs)

        with mock.patch.object(self.mod.sqlite3, "connect", side_effect=spy):
            self.mod.extract_cron_jobs(self.db)
        self.assertTrue(captured["kwargs"].get("uri"), "connect(uri=True)")
        self.assertIn("mode=ro", captured["path"])
        self.assertIn(str(self.db), captured["path"])


class SecretsGuardTest(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()

    def test_serialized_output_has_no_forbidden_substrings_or_token_patterns(self):
        clean = json.dumps({"cron_jobs": [{"name": "x", "status": "ok"}]})
        self.assertIsNone(self.mod.guard_output(clean))
        for bad_key in ("payload", "delivery_to", "session_key", "telegram:"):
            with self.assertRaises(RuntimeError, msg=bad_key):
                self.mod.guard_output(json.dumps({bad_key: "x"}))
            with self.assertRaises(RuntimeError, msg=bad_key):
                self.mod.guard_output(json.dumps({"v": bad_key}))
        with self.assertRaises(RuntimeError):
            self.mod.guard_output(json.dumps({"t": "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234"}))

    def test_source_errors_error_strings_redact_home_prefix_and_absolute_paths_truncate_200c(self):
        home = str(Path.home())
        exc = RuntimeError(f"{home}/.openclaw/state/openclaw.sqlite: unable to open")
        sanitized = self.mod.sanitize_error(exc)
        self.assertNotIn(home, sanitized)
        self.assertNotIn("/home/", sanitized)
        self.assertTrue(sanitized.startswith("~/.openclaw/"))
        other = self.mod.sanitize_error(RuntimeError("failed on /var/log/huge/dir/file.txt x"))
        self.assertNotIn("/var/log", other)
        self.assertIn("/…", other)
        long = self.mod.sanitize_error(RuntimeError("x" * 500))
        self.assertLessEqual(len(long), 200)
        messy = self.mod.sanitize_error(RuntimeError("a\n  b\t c"))
        self.assertEqual("a b c", messy)


def merge_fixture():
    """Seed-shaped input carrying last-good values + old stamps."""
    return {
        "schema_version": "2.0",
        "updated_at": "2026-08-01T00:00:00Z",
        "sections_updated_at": {"cron_jobs": "2026-08-01T00:00:00Z"},
        "source_errors": {},
        "projects": [{"name": "halo", "open_issues": 3, "custom": "keep"}],
        "pipeline": [{"agent": "cmok", "emoji": "🐉", "role": "Build",
                      "status": "pass", "last_run": "2026-07-02T23:30:00Z"}],
        "issues": [{"project": "old", "number": 1}],
        "prs": [],
        "cron_jobs": [{"name": "old-job", "status": "ok"}],
        "agents": [{"name": "moo", "custom_agent": True}],
    }


class MergeAndFailureTest(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "projects").mkdir()
        agents = self.root / "agents"
        (agents / "moo" / "sessions").mkdir(parents=True)
        (agents / "moo" / "sessions" / "s.jsonl").write_text("{}\n")

    def run_main(self, data, env=None, gh_responses=None):
        data_file = self.root / "swarm.json"
        data_file.write_text(json.dumps(data))
        base_env = {
            "HALO_OPENCLAW_DB": str(self.root / "db.sqlite"),
            "HALO_AGENTS_DIR": str(self.root / "agents"),
            "HALO_PROJECTS_DIR": str(self.root / "projects"),
            "HALO_REPO_DENYLIST": ".github",
        }
        base_env.update(env or {})
        if gh_responses is None:
            runner = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
            ctx = mock.patch.object(self.mod.subprocess, "run", return_value=runner)
        else:
            ctx = mock.patch.object(self.mod.subprocess, "run",
                                    side_effect=make_gh_fake(gh_responses))
        with mock.patch.dict(os.environ, base_env), ctx, \
                mock.patch.object(self.mod, "DATA_FILE", data_file):
            self.mod.main()  # partial success exits 0 == plain return
        return json.loads(data_file.read_text())

    def test_path_bearing_exception_lands_redacted_in_published_map(self):
        secret_dir = str(self.root / "agents-private-moo-sessions")
        out = self.run_main(
            merge_fixture(),
            env={"HALO_AGENTS_DIR": secret_dir},
        )
        error = out["source_errors"]["agents"]["error"]
        self.assertNotIn(secret_dir, error)
        self.assertNotIn(str(self.root), error)
        self.assertIn("/…", error)
        # published file passes the guard even though an error was recorded
        self.assertIsNone(self.mod.guard_output(json.dumps(out)))

    def test_project_open_issues_come_from_issues_fetch_not_extra_call(self):
        responses = {
            "orgs/moo-swarm/repos?per_page=100": [{"name": "halo"}],
            "repos/moo-swarm/halo/issues?state=open&per_page=100": [
                {"number": 1, "title": "real issue", "labels": [],
                 "created_at": "2026-08-01T00:00:00Z",
                 "html_url": "https://github.com/moo-swarm/halo/issues/1"},
                {"number": 2, "title": "actually a PR", "labels": [],
                 "created_at": "2026-08-02T00:00:00Z",
                 "html_url": "u", "pull_request": {"url": "u"}},
            ],
            "repos/moo-swarm/halo/pulls?state=open&per_page=100": [],
        }
        calls = []
        data = merge_fixture()
        data_file = self.root / "swarm.json"
        data_file.write_text(json.dumps(data))
        env = {
            "HALO_OPENCLAW_DB": str(self.root / "db.sqlite"),
            "HALO_AGENTS_DIR": str(self.root / "agents"),
            "HALO_PROJECTS_DIR": str(self.root / "projects"),
            "HALO_REPO_DENYLIST": ".github",
        }
        with mock.patch.dict(os.environ, env), \
                mock.patch.object(self.mod.subprocess, "run",
                                  side_effect=make_gh_fake(responses, calls=calls)), \
                mock.patch.object(self.mod, "DATA_FILE", data_file):
            self.mod.main()
        out = json.loads(data_file.read_text())
        self.assertEqual(1, out["projects"][0]["open_issues"],
                         "PR-shaped item excluded from project issue count")
        gh_calls = [c for c in calls if c[:2] == ["gh", "api"]]
        self.assertEqual(3, len(gh_calls),
                         "org listing + issues + pulls only — no separate integer call")

    def test_success_stamps_real_fetch_time_updated_at_stays_file_time(self):
        responses = {
            "orgs/moo-swarm/repos?per_page=100": [],
            "repos/moo-swarm/x/issues?state=open&per_page=100": [],
            "repos/moo-swarm/x/pulls?state=open&per_page=100": [],
        }
        db = make_cron_db(self.root / "db.sqlite", [cron_row()])
        out = self.run_main(
            merge_fixture(),
            env={"HALO_OPENCLAW_DB": str(db)},
            gh_responses=responses,
        )
        stamps = out["sections_updated_at"]
        for section in ("issues", "prs", "projects", "pipeline", "cron_jobs", "agents"):
            self.assertEqual(out["updated_at"], stamps[section], section)
        self.assertEqual({}, out["source_errors"])

    def test_failed_source_keeps_lastgood_data_stamp_records_error_exit_zero(self):
        missing_db = self.root / "missing.sqlite"  # never created
        old_stamp = "2026-08-01T00:00:00Z"
        out = self.run_main(merge_fixture(), env={"HALO_OPENCLAW_DB": str(missing_db)})
        self.assertEqual([{"name": "old-job", "status": "ok"}], out["cron_jobs"],
                         "last-good cron data retained")
        self.assertEqual(old_stamp, out["sections_updated_at"]["cron_jobs"],
                         "old stamp retained — truthful staleness")
        err = out["source_errors"]["cron_jobs"]
        self.assertTrue(err["error"])
        self.assertEqual(out["updated_at"], err["at"])
        # exit-zero semantics: main() above returned without SystemExit

    def test_global_updated_at_advances_despite_partial_failure(self):
        missing_db = self.root / "missing.sqlite"
        out = self.run_main(merge_fixture(), env={"HALO_OPENCLAW_DB": str(missing_db)})
        self.assertNotEqual("2026-08-01T00:00:00Z", out["updated_at"])
        self.assertTrue(out["updated_at"].endswith("Z"))
        self.assertEqual(out["updated_at"], out["sections_updated_at"]["pipeline"])

    def test_empty_source_is_success_with_fresh_stamp_no_error(self):
        responses = {
            "orgs/moo-swarm/repos?per_page=100": [{"name": "halo"}],
            "repos/moo-swarm/halo/issues?state=open&per_page=100": [],
            "repos/moo-swarm/halo/pulls?state=open&per_page=100": [],
        }
        out = self.run_main(merge_fixture(), gh_responses=responses)
        self.assertEqual([], out["issues"], "legitimately empty ≠ failure")
        self.assertEqual([], out["prs"])
        self.assertNotIn("issues", out["source_errors"])
        self.assertNotIn("prs", out["source_errors"])
        self.assertEqual(out["updated_at"], out["sections_updated_at"]["issues"])
        self.assertEqual(out["updated_at"], out["sections_updated_at"]["prs"])

    def test_serialization_failure_mid_write_leaves_original_swarm_json_byte_identical(self):
        """Carry-forward gate blocker 2: atomic-write crash safety.

        A failure between serialize and replace must leave the previous
        swarm.json byte-identical and no partial state (or tmp litter)
        behind — the input file IS the last-good cache.
        """
        data_file = self.root / "swarm.json"
        original = merge_fixture()
        data_file.write_text(json.dumps(original, indent=2) + "\n")
        before = data_file.read_bytes()

        with mock.patch.dict(os.environ, {
            "HALO_OPENCLAW_DB": str(self.root / "db.sqlite"),
            "HALO_AGENTS_DIR": str(self.root / "agents"),
            "HALO_PROJECTS_DIR": str(self.root / "projects"),
            "HALO_REPO_DENYLIST": ".github",
        }), mock.patch.object(self.mod.subprocess, "run", return_value=subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr=""
        )), mock.patch.object(self.mod, "DATA_FILE", data_file), \
                mock.patch.object(self.mod, "serialize_data",
                                  side_effect=TypeError("Object of type set is not JSON serializable")):
            with self.assertRaises(SystemExit) as caught:
                self.mod.main()
        self.assertEqual(1, caught.exception.code)
        self.assertEqual(before, data_file.read_bytes(), "original file byte-identical")
        leftovers = list(self.root.glob("swarm.json.tmp-*"))
        self.assertEqual([], leftovers, "no torn tmp files left behind")


class PipelineExtractionTest(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.projects = Path(tmp.name)

    def write_log(self, project, feature, lines):
        log = self.projects / project / ".moo-swarm" / "features" / feature / "handoff-log.md"
        log.parent.mkdir(parents=True)
        log.write_text("\n".join(lines) + "\n")
        return log

    def test_latest_header_line_wins_per_worker(self):
        self.write_log("alpha", "2026-08-20-old-feature", [
            "# log",
            "## 09:00 Cmok → Coordinator [build] progress",
            "## 17:30 Cmok → Coordinator [build] done",
        ])
        self.write_log("alpha", "2026-08-23-new-feature", [
            "## 08:00 cmok [build] done",
            "## 12:15 Cmok → Coordinator [code QA] FAIL",
        ])
        entries = {e["agent"]: e for e in self.mod.extract_pipeline(
            self.projects, now=FROZEN_NOW)}
        cmok = entries["cmok"]
        self.assertEqual("fail", cmok["status"], "newest entry across files wins")
        self.assertEqual("2026-08-23T12:15:00Z", cmok["last_run"])
        self.assertEqual("Build", cmok["role"])
        self.assertEqual("🐉", cmok["emoji"])

    def test_status_mapping_done_pass_fail_blocked_progress(self):
        cases = [("done", "pass"), ("pass", "pass"), ("PASS", "pass"),
                 ("fail", "fail"), ("FAIL", "fail"), ("blocked", "idle"),
                 ("progress", "running")]
        for word, expected in cases:
            self.assertEqual(expected, self.mod.status_from_entry(word, 0), word)
        self.assertEqual("pass", self.mod.status_from_entry("done", 29),
                         "recent-enough activity keeps the mapped status")
        self.assertEqual("running", self.mod.status_from_entry("progress", 29))
        self.assertEqual("idle", self.mod.status_from_entry("done", 30),
                         "≥30d staleness overrides everything")

    def test_malformed_log_skipped_without_failing_run(self):
        self.write_log("broken", "not-a-date-feature", ["## 10:00 Cmok [build] done"])
        self.write_log("broken", "2026-08-23-garbage-log", ["hello world", "***"])
        self.write_log("broken", "2026-08-23-bad-time", ["## 99:99 Cmok [build] done"])
        self.write_log("good", "2026-08-23-fine", ["## 10:00 veles → Coordinator [spec] done"])
        empty_dir = self.projects / "hollow"
        (empty_dir / ".moo-swarm" / "features").mkdir(parents=True)
        entries = self.mod.extract_pipeline(self.projects, now=FROZEN_NOW)
        self.assertEqual(["veles"], [e["agent"] for e in entries])

    def test_worker_inactive_30d_falls_back_to_idle_with_last_run(self):
        self.write_log("stale-proj", "2026-07-01-ancient", [
            "## 12:00 zlydni → Coordinator [commit] done",
        ])
        entries = self.mod.extract_pipeline(self.projects, now=FROZEN_NOW)
        self.assertEqual(1, len(entries))
        self.assertEqual("idle", entries[0]["status"], "54d inactivity → idle")
        self.assertEqual("2026-07-01T12:00:00Z", entries[0]["last_run"],
                         "last recorded run preserved")


class AgentsScanTest(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.agents = Path(tmp.name) / "agents"
        self.now = FROZEN_NOW

    def touch(self, agent, fname, age_seconds):
        d = self.agents / agent / "sessions"
        d.mkdir(parents=True, exist_ok=True)
        f = d / fname
        f.write_text("{}\n")
        os.utime(f, ((self.now - timedelta(seconds=age_seconds)).timestamp(),
                     (self.now - timedelta(seconds=age_seconds)).timestamp()))

    def scan(self):
        return {a["name"]: a for a in self.mod.extract_agents(self.agents, now=self.now)}

    def test_last_active_max_mtime_sessions_24h_count(self):
        self.touch("moo", "old.jsonl", 36 * 3600)
        self.touch("moo", "mid.jsonl", 7200)
        self.touch("moo", "fresh.jsonl", 1800)  # 30 min — comfortably inside active window
        self.touch("veles", "c.jsonl", 3 * 86400)
        agents = self.scan()
        moo = agents["moo"]
        self.assertEqual(2, moo["sessions_24h"], "files touched within trailing 24h")
        self.assertEqual(
            (self.now - timedelta(seconds=1800)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            moo["last_active"],
        )
        self.assertEqual("active", moo["status"])
        self.assertEqual("idle", agents["veles"]["status"])

    def test_unknown_dir_gets_neutral_meta_roster_is_union(self):
        self.touch("r2d2", "a.jsonl", 60)
        agents = self.scan()
        r2d2 = agents["r2d2"]
        self.assertEqual("🤖", r2d2["emoji"])
        self.assertEqual("agent", r2d2["role"])
        for seed_name in self.mod.AGENT_META:          # union: seed knowledge
            self.assertIn(seed_name, agents)
        ghost = agents["mokash"]                        # seed agent with no dir
        self.assertEqual("🧶", ghost["emoji"])
        self.assertIsNone(ghost["last_active"])
        self.assertEqual(0, ghost["sessions_24h"])
        self.assertEqual("dormant", ghost["status"])

    def test_status_thresholds_active_idle_dormant(self):
        f = self.mod.status_from_age
        self.assertEqual("active", f(0))
        self.assertEqual("active", f(59.9))
        self.assertEqual("idle", f(60))
        self.assertEqual("idle", f(7 * 24 * 60 - 1))
        self.assertEqual("dormant", f(7 * 24 * 60))
        self.assertEqual("dormant", f(None))

    def test_tokens_24h_is_null_honest_gap(self):
        self.touch("cmok", "a.jsonl", 120)
        for agent in self.scan().values():
            self.assertIsNone(agent["tokens_24h"],
                              "tokens not derivable without transcript parsing")
            self.assertEqual(
                {"tokens": 0, "cost": 0.0, "pricing_configured": False,
                 "limit_tokens": 200000, "limit_cost": 0.60},
                agent["budget_daily"],
            )


class SchemaCompatTest(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "projects").mkdir()

    def run_main(self, data):
        data_file = self.root / "swarm.json"
        data_file.write_text(json.dumps(data))
        env = {
            "HALO_OPENCLAW_DB": str(self.root / "nonexistent.sqlite"),
            "HALO_AGENTS_DIR": str(self.root / "nonexistent-agents"),
            "HALO_PROJECTS_DIR": str(self.root / "projects"),
            "HALO_REPO_DENYLIST": ".github",
        }
        failed = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
        with mock.patch.dict(os.environ, env), \
                mock.patch.object(self.mod.subprocess, "run", return_value=failed), \
                mock.patch.object(self.mod, "DATA_FILE", data_file):
            self.mod.main()
        return json.loads(data_file.read_text())

    def test_required_keys_and_version_2_on_every_success(self):
        out = self.run_main({})  # even an empty file yields schema-complete output
        required = ["updated_at", "projects", "pipeline", "issues", "prs",
                    "cron_jobs", "agents"]
        for key in required:
            self.assertIn(key, out, key)
        self.assertEqual("2.0", out["schema_version"])
        self.assertIn("meta", out)

    def test_main_against_seed_shaped_fixture_preserves_custom_user_fields(self):
        fixture = merge_fixture()
        fixture["custom_top"] = {"owner_note": "keep me"}
        out = self.run_main(fixture)
        self.assertEqual({"owner_note": "keep me"}, out["custom_top"])
        self.assertEqual("keep", out["projects"][0]["custom"])
        self.assertEqual(True, out["agents"][0].get("custom_agent"))


class EnvConfigTest(unittest.TestCase):
    def test_env_vars_override_defaults(self):
        mod = load_module()
        overrides = {
            "HALO_OPENCLAW_DB": "/tmp/x/db.sqlite",
            "HALO_AGENTS_DIR": "/tmp/x/agents",
            "HALO_PROJECTS_DIR": "/tmp/x/projects",
            "HALO_REPO_DENYLIST": ".github, brain-runtime",
        }
        with mock.patch.dict(os.environ, overrides):
            cfg = mod.env_config()
        self.assertEqual(Path("/tmp/x/db.sqlite"), cfg["db"])
        self.assertEqual(Path("/tmp/x/agents"), cfg["agents_dir"])
        self.assertEqual(Path("/tmp/x/projects"), cfg["projects_dir"])
        self.assertEqual((".github", "brain-runtime"), cfg["denylist"])

        clean = {k: v for k, v in os.environ.items() if not k.startswith("HALO_")}
        with mock.patch.dict(os.environ, clean, clear=True):
            cfg = mod.env_config()
        self.assertEqual(Path(mod.DEFAULT_OPENCLAW_DB), cfg["db"])
        self.assertEqual(mod.PROJECTS_DIR, cfg["projects_dir"])
        self.assertEqual((".github",), cfg["denylist"])


if __name__ == "__main__":
    unittest.main()
