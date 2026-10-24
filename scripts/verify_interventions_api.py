"""Verify /api/interventions offline (temporary ledger, memory, runs, and SQLite store).

Run: python scripts/verify_interventions_api.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

import api_server  # noqa: E402
import evidence_api  # noqa: E402
import interventions_api  # noqa: E402
from evidence.schema import (  # noqa: E402
    AnalystOutput,
    Claim,
    EvidenceRun,
    ProposedAction,
    RevisionStep,
    TestPlan,
)
from evidence.sources import ASC_DAILY  # noqa: E402
from evidence.sqlite_store import SQLiteEvidenceStore  # noqa: E402
from interventions import InterventionLedger  # noqa: E402

APP_ID = "6740174129"


def fixture_store() -> SQLiteEvidenceStore:
    """Daily rows 2026-10-01..10-24; page views and downloads go up from 10-16."""
    rows = []
    day = date(2026, 10, 1)
    while day <= date(2026, 10, 24):
        later = day >= date(2026, 10, 16)
        rows.append(
            {
                "date": day, "app_id": APP_ID, "territory": "ALL", "impressions": 100,
                "product_page_views": 20 if later else 10,
                "first_time_downloads": 5 if later else 2, "source": "asc_analytics",
            }
        )
        day += timedelta(days=1)
    store = SQLiteEvidenceStore(":memory:")
    store.replace_table(ASC_DAILY, rows)
    return store


def write_run(runs_dir: Path, run_id: str, status: str) -> None:
    output = AnalystOutput(
        most_important_finding="f",
        claims=[
            Claim(
                id="C1", text="h", kind="hypothesis",
                test_plan=TestPlan(
                    metric="page_view_to_download_pct", method="前後7日比較",
                    duration_days=7, success_criterion="+5ポイント",
                ),
            )
        ],
        actions=[
            ProposedAction(rank=1, title="スクショ1枚目を変える", reason="r", claim_ids=["C1"]),
            ProposedAction(rank=2, title="説明文を変える", reason="r"),
        ],
    )
    run = EvidenceRun(
        run_id=run_id, product_id="mahjong", started_at="2026-10-15T09:00:00+09:00",
        status=status,  # type: ignore[arg-type]
        steps=[RevisionStep(version="v3", stage="critic_revision", output=output)],
    )
    (runs_dir / f"{run_id}.json").write_text(run.model_dump_json(by_alias=True), "utf-8")


def detail_code(response) -> str:
    return response.json()["detail"]["code"]


def main() -> None:
    saved_env = {k: os.environ.get(k) for k in ("INTERVENTIONS_PATH", "MEMORY_BACKEND",
                                                "MEMORY_LOCAL_DIR")}
    saved = (evidence_api.RUNS_DIR, interventions_api.open_store, interventions_api._app_id)
    store_up = {"value": True}

    def fake_open_store():
        if not store_up["value"]:
            return None, "evidence store unavailable, nothing measured (down)"
        return fixture_store(), None

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        ledger_path = tmp_path / "interventions" / "ledger.jsonl"
        os.environ["INTERVENTIONS_PATH"] = str(ledger_path)
        os.environ["MEMORY_BACKEND"] = "local"
        os.environ["MEMORY_LOCAL_DIR"] = str(tmp_path / "memory")
        evidence_api.RUNS_DIR = runs_dir
        interventions_api.open_store = fake_open_store  # type: ignore[assignment]
        interventions_api._app_id = lambda product_id: APP_ID  # type: ignore[assignment]
        try:
            client = TestClient(api_server.app)
            write_run(runs_dir, "mahjong-20261015-090000", "converged")
            write_run(runs_dir, "mahjong-20261015-100000", "running")

            assert client.get("/api/interventions").json() == {"interventions": []}
            assert client.get("/api/interventions/iv_missing").status_code == 404

            # --- 1) Adopt: guards ---
            def adopt(**body):
                return client.post("/api/interventions/adopt", json=body)

            assert detail_code(adopt(runId="../x", rank=1)) == "invalid_run_id"
            assert detail_code(adopt(runId="mahjong-nope", rank=1)) == "run_not_found"
            assert detail_code(adopt(runId="mahjong-20261015-100000", rank=1)) == "run_in_progress"
            assert detail_code(adopt(runId="mahjong-20261015-090000", rank=3)) == "not_found"
            missing = adopt(runId="mahjong-20261015-090000", rank=2)
            assert missing.status_code == 400 and detail_code(missing) == "missing_plan", missing.text
            print("OK adopt rejects bad ids, unknown or running runs, missing ranks and plans")

            # --- 2) Adopt and manual add, without duplicates ---
            first = adopt(runId="mahjong-20261015-090000", rank=1)
            assert first.status_code == 200, first.text
            body = first.json()
            ai = body["intervention"]
            assert body["changed"] is True and body["warnings"] == []
            assert ai["status"] == "planned" and ai["decision"]["origin"] == "ai_adopted"
            assert ai["prediction"]["testPlan"]["durationDays"] == 7
            assert ai["targetMetric"] == "page_view_to_download_pct"
            assert list(ai["memoryIds"]) == ["local:decision"]
            again = adopt(runId="mahjong-20261015-090000", rank=1).json()
            assert again["changed"] is False and again["intervention"]["id"] == ai["id"]
            second = adopt(
                runId="mahjong-20261015-090000", rank=2, targetMetric="impressions",
                method="前後比較", successCriterion="減らない", durationDays=14,
            ).json()["intervention"]
            assert second["decision"]["actionTitle"] == "説明文を変える"
            assert second["prediction"]["testPlan"] is None

            manual_body = dict(
                productId="mahjong", title="キーワード変更", targetMetric="impressions",
                method="前後比較", successCriterion="減らない", durationDays=7,
            )
            bad = client.post("/api/interventions", json={**manual_body, "productId": "nope"})
            assert bad.status_code == 400 and detail_code(bad) == "invalid_product"
            manual = client.post("/api/interventions", json=manual_body).json()
            assert manual["changed"] and manual["intervention"]["prediction"] is None
            dup = client.post(
                "/api/interventions", json={**manual_body, "title": " キーワード変更 "}
            ).json()
            assert dup["changed"] is False and dup["intervention"]["id"] == manual["intervention"]["id"]
            listed = client.get("/api/interventions", params={"productId": "mahjong"}).json()
            assert len(listed["interventions"]) == 3
            assert client.get("/api/interventions", params={"productId": "nextuta"}).json() == {
                "interventions": []
            }
            print("OK adopt and manual add create once; repeats return the same intervention")

            # --- 3) Implement measures before; repeats are no-ops ---
            url = f"/api/interventions/{ai['id']}"
            done = client.post(f"{url}/implement", json={"implementedOn": "2026-10-15"})
            assert done.status_code == 200, done.text
            item = done.json()["intervention"]
            assert item["status"] == "implemented" and item["decision"]["evaluationDate"] == "2026-10-22"
            values = {m["metric"]: m["value"] for m in item["baseline"]["metrics"]}
            assert values["page_view_to_download_pct"] == 20.0 and values["impressions"] == 700
            assert all(m["sql"].startswith("SELECT") for m in item["baseline"]["metrics"])
            repeat = client.post(f"{url}/implement", json={"implementedOn": "2026-10-15"}).json()
            assert repeat["changed"] is False
            conflict = client.post(f"{url}/implement", json={"implementedOn": "2026-10-16"})
            assert conflict.status_code == 409 and detail_code(conflict) == "invalid_transition"
            short = client.post(
                f"/api/interventions/{manual['intervention']['id']}/implement",
                json={"implementedOn": "2026-10-15", "evaluationDate": "2026-10-18"},
            )
            assert short.status_code == 400 and detail_code(short) == "invalid_dates", short.text
            print("OK implement measures the window before; repeat is a no-op; conflicts are 409")

            # --- 4) Evaluate: not due, then verdict + after window ---
            early = client.post(
                f"{url}/evaluate", json={"verdict": "improved", "evaluatedOn": "2026-10-18"}
            )
            assert early.status_code == 409 and detail_code(early) == "not_due", early.text
            bad_verdict = client.post(
                f"{url}/evaluate", json={"verdict": "great", "evaluatedOn": "2026-10-23"}
            )
            assert bad_verdict.status_code == 422
            judged = client.post(
                f"{url}/evaluate",
                json={"verdict": "improved", "note": "上がった", "evaluatedOn": "2026-10-23"},
            ).json()
            item = judged["intervention"]
            assert item["status"] == "evaluated" and item["evaluation"] == {
                "evaluatedOn": "2026-10-23", "verdict": "improved", "note": "上がった",
            }
            after = {m["metric"]: m["value"] for m in item["after"]["metrics"]}
            assert after["page_view_to_download_pct"] == 25.0
            assert set(item["memoryIds"]) == {"local:decision", "local:outcome"}
            print("OK evaluate is refused before the due date; the verdict and after numbers are stored")

            # --- 5) Store down: the change is recorded with a warning, measured later ---
            store_up["value"] = False
            manual_url = f"/api/interventions/{manual['intervention']['id']}"
            down = client.post(f"{manual_url}/implement", json={"implementedOn": "2026-10-10"}).json()
            assert down["changed"] and down["intervention"]["baseline"] is None
            assert any("unavailable" in w for w in down["warnings"]), down["warnings"]
            unavailable = client.post(f"{manual_url}/measure")
            assert unavailable.status_code == 503 and detail_code(unavailable) == "store_unavailable"
            store_up["value"] = True
            measured = client.post(f"{manual_url}/measure").json()
            assert measured["changed"] and measured["intervention"]["baseline"]["metrics"]
            assert client.post(f"{manual_url}/measure").json()["changed"] is False
            print("OK a store outage leaves a warning, and measure fills the numbers in later")

            # --- 6) Inconclusive, drop ---
            inconclusive = client.post(
                f"{manual_url}/evaluate",
                json={"verdict": "inconclusive", "evaluatedOn": "2026-10-17"},
            ).json()["intervention"]
            assert inconclusive["evaluation"]["verdict"] == "inconclusive"
            second_url = f"/api/interventions/{second['id']}"
            assert client.post(f"{second_url}/drop", json={"reason": ""}).status_code == 422
            dropped = client.post(f"{second_url}/drop", json={"reason": "今月はやらない"}).json()
            assert dropped["changed"] and dropped["intervention"]["status"] == "dropped"
            assert client.post(f"{second_url}/drop", json={"reason": "x"}).json()["changed"] is False
            assert client.post(f"{url}/drop", json={"reason": "x"}).status_code == 409
            print("OK inconclusive is accepted; drop is idempotent; evaluated cannot be dropped")

            # --- 7) The API and the CLI share one ledger ---
            ledger = InterventionLedger(ledger_path)
            by_status = {i.id: i.status for i in ledger.list_interventions()}
            assert by_status == {
                ai["id"]: "evaluated",
                second["id"]: "dropped",
                manual["intervention"]["id"]: "evaluated",
            }, by_status
            got = client.get(url).json()
            assert got["id"] == ai["id"] and got["after"]["metrics"]
            print("OK the API writes the same ledger the CLI reads")

            print("\nAll interventions API checks passed.")
        finally:
            evidence_api.RUNS_DIR, interventions_api.open_store, interventions_api._app_id = saved
            for key, value in saved_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    main()
