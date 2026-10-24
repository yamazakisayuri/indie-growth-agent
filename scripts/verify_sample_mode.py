"""Verify sample mode offline: loading, scenarios, Recorded Demo rules, API, and viewer.

Run: python scripts/verify_sample_mode.py

Uses a small fixture written to a temporary directory, not samples/mahjong/, so the
checks do not depend on the sample numbers. Network connections are refused in-process.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _no_network(*_args, **_kwargs):
    raise AssertionError("sample mode must not open network connections")


socket.socket.connect = _no_network  # type: ignore[method-assign]

from fastapi.testclient import TestClient  # noqa: E402

import api_server  # noqa: E402
import evidence_api  # noqa: E402
import sample_mode  # noqa: E402
from evidence.loop import comparison_periods  # noqa: E402
from evidence.schema import (  # noqa: E402
    AnalystOutput,
    CriticReview,
    EvidenceRun,
    ProposedAction,
    RevisionStep,
)
from evidence.sources import (  # noqa: E402
    ASC_DAILY,
    ASC_DAILY_BY_SOURCE,
    COMPETITOR_LISTING,
    KNOWN_EVENTS,
    write_csv,
)
from sample_mode import (  # noqa: E402
    DATA_KIND,
    SampleError,
    apply_scenario,
    build_sample_store,
    load_sample_set,
    load_scenario,
    read_sample_meta,
    record_demo,
    recording_problems,
    write_sample_meta,
)

SCENARIOS = {
    "dataKind": DATA_KIND,
    "note": "fixture: fictional",
    "app": {"productId": "mahjong", "name": "Fixture app (fictional)", "appId": "fx-self"},
    "scenarios": {
        "base": {"description": "base fixture", "overrides": []},
        "competitor-variant": {
            "description": "fewer ratings, stale updates",
            "overrides": [
                {
                    "table": "competitor_listing",
                    "match": {"app_id": "fx-a"},
                    "set": {"rating_count": 3, "current_version_released_on": "2024-01-01"},
                    "reason": "remove the rating lead",
                }
            ],
        },
    },
}


def write_fixture(directory: Path, *, scenarios: dict | None = None, source: str = DATA_KIND,
                  competitor_id: str = "fx-a") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    days = [date(2026, 10, 1) + timedelta(days=i) for i in range(14)]
    daily = [
        {"date": d, "app_id": "fx-self", "territory": "ALL", "impressions": 100 + i,
         "product_page_views": 10, "first_time_downloads": 4, "source": source}
        for i, d in enumerate(days)
    ]
    write_csv(ASC_DAILY, daily, directory / "asc_daily.csv")
    write_csv(
        ASC_DAILY_BY_SOURCE,
        [{**r, "source_bucket": "search"} for r in daily],
        directory / "asc_daily_by_source.csv",
    )
    write_csv(KNOWN_EVENTS, [], directory / "known_events.csv")
    write_csv(
        COMPETITOR_LISTING,
        [
            {"fetched_on": date(2026, 10, 14), "country": "jp", "app_id": "fx-self", "is_self": 1,
             "name": "self", "rating_avg": None, "rating_count": 0, "source": DATA_KIND},
            {"fetched_on": date(2026, 10, 14), "country": "jp", "app_id": competitor_id,
             "is_self": 0, "name": "comp", "rating_avg": 4.5, "rating_count": 900,
             "current_version_released_on": "2026-10-10", "source": DATA_KIND},
        ],
        directory / "competitor_listing.csv",
    )
    (directory / "scenarios.json").write_text(
        json.dumps(scenarios or SCENARIOS, ensure_ascii=False), "utf-8"
    )
    return directory


def expect_error(fn, text: str) -> None:
    try:
        fn()
    except SampleError as exc:
        assert text in str(exc), (text, str(exc))
    else:
        raise AssertionError(f"expected SampleError containing {text!r}")


def write_trace(runs_dir: Path, run_id: str, info: dict | None, *, status: str = "converged",
                model: str = "openai_compatible:test-model") -> Path:
    output = AnalystOutput(
        most_important_finding="f",
        actions=[ProposedAction(rank=1, title=f"action for {run_id}", reason="r")],
    )
    run = EvidenceRun(
        run_id=run_id, product_id="mahjong", started_at="2026-10-25T10:00:00+09:00",
        finished_at="2026-10-25T10:15:00+09:00", model=model, status=status,  # type: ignore[arg-type]
        steps=[
            RevisionStep(version="v1", stage="internal", output=output),
            RevisionStep(version="v2", stage="competitive", output=output,
                         critic=CriticReview(summary="s")),
        ],
    )
    path = runs_dir / f"{run_id}.json"
    path.write_text(run.model_dump_json(by_alias=True), "utf-8")
    if info is not None:
        write_sample_meta(path, info)
    return path


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        fixture = write_fixture(tmp_path / "sample")

        # --- 1) Load: types, NULLs, and the layout checks ---
        sample = load_sample_set(fixture)
        assert sample.scenario_names == ["base", "competitor-variant"]
        competitor = sample.tables["competitor_listing"][1]
        assert competitor["rating_count"] == 900 and competitor["rating_avg"] == 4.5
        assert sample.tables["competitor_listing"][0]["rating_avg"] is None
        assert sample.tables["known_events"] == []
        expect_error(lambda: load_sample_set(tmp_path / "nowhere"), "No sample data")
        broken = Path(shutil.copytree(fixture, tmp_path / "broken"))
        (broken / "known_events.csv").unlink()
        expect_error(lambda: load_sample_set(broken), "missing known_events.csv")
        (broken / "known_events.csv").write_text("date,type\n", "utf-8")
        expect_error(lambda: load_sample_set(broken), "known_events.csv: columns must be")
        not_fictional = {**SCENARIOS, "dataKind": "real"}
        expect_error(
            lambda: load_sample_set(write_fixture(tmp_path / "kind", scenarios=not_fictional)),
            "dataKind",
        )
        print("OK sample CSVs load with typed values and NULLs; a bad layout is refused")

        # --- 2) Only fictional data: source marker, no real app ids ---
        expect_error(
            lambda: load_sample_set(write_fixture(tmp_path / "src", source="asc_analytics")),
            "source must be 'fictional_sample'",
        )
        real_id = sorted(sample_mode.real_app_ids())[0]
        expect_error(
            lambda: load_sample_set(write_fixture(tmp_path / "real", competitor_id=real_id)),
            "is a real app",
        )
        print("OK data without the fictional marker, or naming a real configured app, is refused")

        # --- 3) Scenarios state every changed value and why ---
        variant = load_scenario(sample, "competitor-variant")
        tables, changes = apply_scenario(sample.tables, variant)
        assert [(c.column, c.before, c.after, c.reason) for c in changes] == [
            ("rating_count", 900, 3, "remove the rating lead"),
            ("current_version_released_on", "2026-10-10", "2024-01-01", "remove the rating lead"),
        ], changes
        assert sample.tables["competitor_listing"][1]["rating_count"] == 900, "base untouched"
        for name in sample.tables:
            if name != "competitor_listing":
                assert tables[name] == sample.tables[name], name
        assert tables["competitor_listing"][0] == sample.tables["competitor_listing"][0]
        assert apply_scenario(sample.tables, load_scenario(sample, "base"))[1] == []
        expect_error(lambda: load_scenario(sample, "nope"), "Unknown scenario")
        for bad, text in (
            ({"table": "competitor_listing", "match": {"app_id": "fx-z"}, "set": {"rating_count": 1},
              "reason": "r"}, "No competitor_listing row matches"),
            ({"table": "competitor_listing", "match": {"app_id": "fx-a"}, "set": {"stars": 1},
              "reason": "r"}, "has no column stars"),
            ({"table": "competitor_listing", "match": {"app_id": "fx-a"}, "set": {"rating_count": 1},
              "reason": " "}, "needs a reason"),
        ):
            scenarios = json.loads(json.dumps(SCENARIOS))
            scenarios["scenarios"]["competitor-variant"]["overrides"] = [bad]
            odd = load_sample_set(write_fixture(tmp_path / f"odd{len(text)}", scenarios=scenarios))
            expect_error(lambda: apply_scenario(odd.tables, load_scenario(odd, "competitor-variant")), text)
        print("OK a scenario lists each changed cell with before, after, and reason; others stay equal")

        # --- 4) Dedicated SQLite store, separate from EVIDENCE_STORE ---
        store_path = tmp_path / "stores" / "variant.sqlite"
        store, _, info = build_sample_store("competitor-variant", path=store_path, sample_dir=fixture)
        assert comparison_periods(store) == (("2026-10-08", "2026-10-14"), ("2026-10-01", "2026-10-07"))
        assert store.query(
            "SELECT rating_count FROM competitor_listing WHERE app_id = 'fx-a'"
        ).scalar() == 3
        store.close()
        assert info["dataKind"] == DATA_KIND and info["scenario"] == "competitor-variant"
        assert len(info["changes"]) == 2 and info["changes"][0]["reason"]
        assert set(info["csvSha256"]) == {
            "asc_daily.csv", "asc_daily_by_source.csv", "competitor_listing.csv",
            "known_events.csv", "scenarios.json",
        }
        again, _, _ = build_sample_store("base", path=store_path, sample_dir=fixture)
        assert again.query(
            "SELECT rating_count FROM competitor_listing WHERE app_id = 'fx-a'"
        ).scalar() == 900, "the store is rebuilt from scratch for each scenario"
        again.close()
        print("OK each scenario gets a freshly built SQLite store")

        env = {**os.environ, "EVIDENCE_STORE": "zetaris", "LLM_PROVIDER": "no-such-provider"}
        before = set(sample_mode.RUNS_DIR.glob("sample-*")) if sample_mode.RUNS_DIR.exists() else set()
        dry = subprocess.run(
            [sys.executable, "scripts/run_sample.py", "--scenario", "competitor-variant",
             "--sample-dir", str(fixture), "--dry-run"],
            cwd=ROOT, env=env, capture_output=True, text=True,
        )
        assert dry.returncode == 0, dry.stderr
        assert "rating_count: 900 -> 3  (remove the rating lead)" in dry.stdout, dry.stdout
        assert "asc_daily: 14 rows" in dry.stdout
        after = set(sample_mode.RUNS_DIR.glob("sample-*")) if sample_mode.RUNS_DIR.exists() else set()
        assert after == before, "a dry run writes no trace"
        missing = subprocess.run(
            [sys.executable, "scripts/run_sample.py", "--sample-dir", str(tmp_path / "nowhere"),
             "--dry-run"],
            cwd=ROOT, env=env, capture_output=True, text=True,
        )
        assert missing.returncode == 1 and "No sample data" in missing.stderr, missing.stderr
        print("OK the dry run ignores EVIDENCE_STORE and the model, and writes no trace")

        # --- 5) Recorded Demo: only finished real-model Live Sample runs on the same data ---
        runs = tmp_path / "runs"
        runs.mkdir()
        recorded = tmp_path / "recorded"
        good = write_trace(runs, "sample-competitor-variant-20261025-100000", info)
        assert recording_problems(good, sample_dir=fixture) == []
        cases = {
            "real-data run": (write_trace(runs, "mahjong-20261025-100000", None), "start with 'sample-'"),
            "no metadata": (write_trace(runs, "sample-base-20261025-100001", None), "no sample metadata"),
            "error status": (
                write_trace(runs, "sample-base-20261025-100002", info, status="error"), "status is error"
            ),
            "no model": (write_trace(runs, "sample-base-20261025-100003", info, model=""), "no model"),
        }
        for label, (path, text) in cases.items():
            problems = recording_problems(path, sample_dir=fixture)
            assert any(text in p for p in problems), (label, problems)
            expect_error(lambda p=path: record_demo(p, recorded_dir=recorded, sample_dir=fixture), text)
        other = write_fixture(tmp_path / "other")
        assert any("the run used" in p for p in recording_problems(good, sample_dir=other))
        target = record_demo(good, recorded_dir=recorded, sample_dir=fixture)
        assert target.read_bytes() == good.read_bytes()
        assert read_sample_meta(target)["recordedAt"]
        assert sorted(p.name for p in recorded.iterdir()) == [
            "sample-competitor-variant-20261025-100000.json",
            "sample-competitor-variant-20261025-100000.sample.json",
        ]
        with (fixture / "asc_daily.csv").open("a", encoding="utf-8") as fh:
            fh.write(f"2026-10-15,fx-self,ALL,1,1,1,{DATA_KIND}\n")
        assert any("CSVs changed" in p for p in recording_problems(good, sample_dir=fixture))
        print("OK only finished Live Sample runs with a model, on unchanged sample data, are recorded")

        # --- 6) API: Recorded Demo and Live Sample are labeled; real runs are not ---
        live = write_trace(runs, "sample-base-20261025-110000", {**info, "scenario": "base"})
        saved = (evidence_api.RUNS_DIR, evidence_api.RECORDED_DIR)
        evidence_api.RUNS_DIR, evidence_api.RECORDED_DIR = runs, recorded
        try:
            client = TestClient(api_server.app)
            listed = client.get("/api/evidence/runs", params={"productId": "mahjong", "limit": 100})
            by_id = {r["runId"]: r for r in listed.json()["runs"]}
            demo = by_id["sample-competitor-variant-20261025-100000"]
            assert demo["recorded"] is True and demo["sample"]["scenario"] == "competitor-variant"
            assert demo["sample"]["changes"][0]["after"] == 3
            assert by_id[live.stem]["recorded"] is False and by_id[live.stem]["sample"]["scenario"] == "base"
            assert by_id["mahjong-20261025-100000"]["sample"] is None
            assert not any(".sample" in run_id for run_id in by_id)
            got = client.get("/api/evidence/runs/sample-competitor-variant-20261025-100000").json()
            assert got["recorded"] is True and got["sample"]["dataKind"] == DATA_KIND
            assert got["steps"][0]["output"]["actions"][0]["title"].startswith("action for")
            real = client.get("/api/evidence/runs/mahjong-20261025-100000").json()
            assert real["sample"] is None and real["recorded"] is False
            print("OK the API marks Recorded Demo and Live Sample traces; real runs carry no sample")

            adopt = client.post(
                "/api/interventions/adopt", json={"runId": live.stem, "rank": 1}
            )
            assert adopt.status_code == 409 and adopt.json()["detail"]["code"] == "sample_run"
            print("OK proposals from fictional sample runs cannot be adopted as interventions")
        finally:
            evidence_api.RUNS_DIR, evidence_api.RECORDED_DIR = saved

        # --- 7) Viewer for a fresh clone: no server, key, or model ---
        import show_sample_demo

        shown = show_sample_demo.recorded_runs(recorded)
        assert [r.run_id for r, _ in shown] == ["sample-competitor-variant-20261025-100000"]
        text = "\n".join(show_sample_demo.describe(*shown[0]))
        assert "Recorded Demo / fictional sample data" in text
        assert "rating_count: 900 -> 3 (remove the rating lead)" in text
        assert show_sample_demo.recorded_runs(tmp_path / "empty") == []
        assert "review outcome" not in text and "known limitations" not in text
        noted = {
            **shown[0][1],
            "reviewOutcome": "max_rounds; 1 unresolved",
            "knownLimitations": ["limit a", " ", 3],
            "comparisonNote": "not a causal effect",
        }
        noted_text = "\n".join(show_sample_demo.describe(shown[0][0], noted))
        assert "review outcome: max_rounds; 1 unresolved" in noted_text
        assert "known limitations:\n    - limit a\n  comparison note: not a causal effect" in noted_text
        print("OK show_sample_demo lists recorded traces with their scenario changes and review notes")

    print("\nAll sample mode checks passed.")


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "scripts"))
    main()
