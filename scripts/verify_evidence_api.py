"""Verify /api/evidence without starting a real run (no model, no evidence store).

Run: python scripts/verify_evidence_api.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

import api_server  # noqa: E402
import evidence_api  # noqa: E402
from evidence.schema import (  # noqa: E402
    AnalystOutput,
    CriticFinding,
    CriticReview,
    EvidenceRun,
    ProposedAction,
    RevisionStep,
)


class FakeProcess:
    def __init__(self) -> None:
        self.returncode: int | None = None
        self.pid = 4242

    def poll(self) -> int | None:
        return self.returncode


def _step(version: str, stage: str, title: str, critic: CriticReview | None = None) -> RevisionStep:
    return RevisionStep(
        version=version,
        stage=stage,  # type: ignore[arg-type]
        output=AnalystOutput(
            most_important_finding=f"{version} finding",
            actions=[ProposedAction(rank=1, title=title, reason="r")],
        ),
        critic=critic,
    )


def _write(runs_dir: Path, run: EvidenceRun) -> None:
    (runs_dir / f"{run.run_id}.json").write_text(
        run.model_dump_json(by_alias=True, indent=2), encoding="utf-8"
    )


def main() -> None:
    spawned: list[tuple[str, str, str]] = []
    processes: list[FakeProcess] = []

    def fake_spawn(run_id: str, product_id: str, language: str) -> FakeProcess:
        spawned.append((run_id, product_id, language))
        process = FakeProcess()
        processes.append(process)
        return process  # type: ignore[return-value]

    original_dir, original_spawn = evidence_api.RUNS_DIR, evidence_api.spawn_run
    with tempfile.TemporaryDirectory() as tmp:
        runs_dir = Path(tmp)
        evidence_api.RUNS_DIR = runs_dir
        evidence_api.spawn_run = fake_spawn  # type: ignore[assignment]
        evidence_api._launches.clear()
        try:
            client = TestClient(api_server.app)

            unresolved = CriticFinding(
                id="r2-f1",
                claim_id="c1",
                kind="causal_leap",
                message="m",
                origin="critic",
                resolution="unresolved",
            )
            _write(
                runs_dir,
                EvidenceRun(
                    run_id="mahjong-20261024-100000",
                    product_id="mahjong",
                    started_at="2026-10-24T10:00:00+09:00",
                    finished_at="2026-10-24T10:20:00+09:00",
                    status="max_rounds",
                    steps=[
                        _step("v1", "internal", "A"),
                        _step("v2", "competitive", "B", CriticReview(summary="s")),
                        _step(
                            "v3",
                            "critic_revision",
                            "C",
                            CriticReview(summary="s", findings=[unresolved]),
                        ),
                    ],
                ),
            )
            _write(
                runs_dir,
                EvidenceRun(
                    run_id="nextuta-20261024-110000",
                    product_id="nextuta",
                    started_at="2026-10-24T11:00:00+09:00",
                    status="converged",
                ),
            )
            (runs_dir / "mahjong-20261024-120000.json").write_text('{"runId": "mahj', "utf-8")

            # --- 1) List: product filter, newest first, summary fields ---
            listed = client.get("/api/evidence/runs", params={"productId": "mahjong"})
            assert listed.status_code == 200, listed.text
            body = listed.json()
            assert body["activeRunId"] is None
            assert [r["runId"] for r in body["runs"]] == ["mahjong-20261024-100000"], body
            summary = body["runs"][0]
            assert summary["versions"] == ["v1", "v2", "v3"]
            assert summary["topActions"] == ["A", "B", "C"]
            assert summary["unresolvedFindings"] == 1
            all_runs = client.get("/api/evidence/runs").json()["runs"]
            assert [r["runId"] for r in all_runs] == [
                "nextuta-20261024-110000",
                "mahjong-20261024-100000",
            ], all_runs
            print("OK list filters by product, newest first, skips a partial trace")

            # --- 2) Read one run in camelCase; bad ids and missing runs ---
            got = client.get("/api/evidence/runs/mahjong-20261024-100000")
            assert got.status_code == 200, got.text
            run = got.json()
            assert run["runId"] == "mahjong-20261024-100000"
            assert run["steps"][2]["critic"]["findings"][0]["resolution"] == "unresolved"
            assert "mostImportantFinding" in run["steps"][0]["output"]
            assert client.get("/api/evidence/runs/nope-1").status_code == 404
            assert client.get("/api/evidence/runs/..%2Fsecrets").status_code in (400, 404)
            assert client.get("/api/evidence/runs/.hidden").status_code == 400
            partial = client.get("/api/evidence/runs/mahjong-20261024-120000")
            assert partial.status_code == 503, partial.text
            assert partial.json()["detail"]["code"] == "run_unreadable"
            print("OK read run; invalid id 400, missing 404, partial trace 503")

            # --- 3) Start: unknown product 400, one active run at a time ---
            bad = client.post("/api/evidence/runs", json={"productId": "no-such-app"})
            assert bad.status_code == 400, bad.text
            assert not spawned
            started = client.post(
                "/api/evidence/runs", json={"productId": "mahjong", "language": "en"}
            )
            assert started.status_code == 202, started.text
            run_id = started.json()["runId"]
            assert run_id.startswith("mahjong-"), run_id
            assert spawned == [(run_id, "mahjong", "en")], spawned
            busy = client.post("/api/evidence/runs", json={"productId": "nextuta"})
            assert busy.status_code == 409, busy.text
            assert busy.json()["detail"]["code"] == "run_in_progress"
            assert len(spawned) == 1
            print("OK start spawns once; a second start while running is 409")

            # --- 4) Before the first step: running placeholder, listed as active ---
            pending = client.get(f"/api/evidence/runs/{run_id}")
            assert pending.status_code == 200, pending.text
            assert pending.json()["status"] == "running"
            assert pending.json()["steps"] == []
            listed = client.get("/api/evidence/runs", params={"productId": "mahjong"}).json()
            assert listed["activeRunId"] == run_id
            assert listed["runs"][0]["runId"] == run_id
            print("OK started run is visible as running before its trace exists")

            # --- 5) Process exits without a trace: error, and a new start is allowed ---
            processes[0].returncode = 1
            dead = client.get(f"/api/evidence/runs/{run_id}").json()
            assert dead["status"] == "error", dead
            assert f"{run_id}.log" in dead["error"]
            assert client.get("/api/evidence/runs").json()["activeRunId"] is None
            print("OK process that exits before the first step shows as error")

            # --- 6) Trace left at running after the process died: error ---
            evidence_api._launches.clear()
            again = client.post("/api/evidence/runs", json={"productId": "mahjong"})
            assert again.status_code == 202, again.text
            second_id = again.json()["runId"]
            _write(
                runs_dir,
                EvidenceRun(
                    run_id=second_id,
                    product_id="mahjong",
                    started_at="2026-10-24T13:00:00+09:00",
                    steps=[_step("v1", "internal", "A")],
                ),
            )
            assert client.get(f"/api/evidence/runs/{second_id}").json()["status"] == "running"
            processes[-1].returncode = -9
            crashed = client.get(f"/api/evidence/runs/{second_id}").json()
            assert crashed["status"] == "error", crashed
            assert crashed["steps"][0]["version"] == "v1"
            print("OK trace stuck at running after the process died shows as error")

            print("\nAll evidence API checks passed.")
        finally:
            evidence_api.RUNS_DIR = original_dir
            evidence_api.spawn_run = original_spawn  # type: ignore[assignment]
            evidence_api._launches.clear()


if __name__ == "__main__":
    main()
