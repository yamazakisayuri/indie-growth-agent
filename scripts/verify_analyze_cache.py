"""Verify Analyze in-process cache + single-flight (no live Bedrock).

Run: python scripts/verify_analyze_cache.py
"""

from __future__ import annotations

import sys
import threading
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

import api_server
import analyze_cache
from analysis_schema import AnalyzeResponse, MetricGroup


def _fake_report(
    *,
    language: str,
    product_id: str,
    run_id: str | None = None,
) -> AnalyzeResponse:
    rid = run_id or f"test-run-{uuid.uuid4().hex[:12]}"
    empty = MetricGroup(
        id="app_store",
        title="App Store",
        source="ASC",
        connected=False,
        metrics=[],
    )
    return AnalyzeResponse(
        language=language,  # type: ignore[arg-type]
        app={"name": product_id},
        period={"start": "2026-09-01", "end": "2026-09-07", "lookbackDays": 7},
        metrics={
            "appStore": empty,
            "ga4": empty.model_copy(update={"id": "usage", "title": "Usage"}),
            "admob": empty.model_copy(update={"id": "revenue", "title": "Revenue"}),
        },
        analysis={
            "mostImportantFinding": "test",
            "facts": ["f1"],
            "speculation": [],
            "actions": [],
        },
        dataScope=[{"source": "ASC", "scope": "JP"}],
        groundingRules=["r1"],
        analysisRunId=rid,
        dataSource="live",
        product={"id": product_id, "name": product_id, "type": "hybrid"},
    )


def main() -> None:
    call_log: list[tuple[str | None, str]] = []
    lock = threading.Lock()

    def fake_run_analysis(language: str | None = "en", *, product_id: str | None = None):
        with lock:
            call_log.append((product_id, language or "en"))
        # Simulate slow external fetch / Bedrock / Planner.
        time.sleep(0.15)
        pid = (product_id or "mahjong").strip() or "mahjong"
        lang = language or "en"
        return _fake_report(language=lang, product_id=pid)

    analyze_cache.clear_analyze_cache()
    original = api_server.run_analysis
    api_server.run_analysis = fake_run_analysis  # type: ignore[assignment]

    try:
        client = TestClient(api_server.app)

        # --- 1) Same product + language: second hit is cache ---
        call_log.clear()
        analyze_cache.clear_analyze_cache()
        r1 = client.post(
            "/api/analyze",
            json={"language": "en", "productId": "mahjong"},
        )
        r2 = client.post(
            "/api/analyze",
            json={"language": "en", "productId": "mahjong"},
        )
        assert r1.status_code == 200, r1.text
        assert r2.status_code == 200, r2.text
        id1 = r1.json()["analysisRunId"]
        id2 = r2.json()["analysisRunId"]
        assert id1 == id2, (id1, id2)
        assert len(call_log) == 1, f"expected 1 run_analysis, got {call_log}"
        print("OK same product+language → 1 run, same analysisRunId")

        # --- 2) Different language → separate run ---
        before = len(call_log)
        r_ja = client.post(
            "/api/analyze",
            json={"language": "ja", "productId": "mahjong"},
        )
        assert r_ja.status_code == 200, r_ja.text
        assert r_ja.json()["analysisRunId"] != id1
        assert len(call_log) == before + 1
        print("OK different language → new run")

        # --- 3) Different product → separate run ---
        before = len(call_log)
        r_nu = client.post(
            "/api/analyze",
            json={"language": "en", "productId": "nextuta"},
        )
        assert r_nu.status_code == 200, r_nu.text
        assert r_nu.json()["analysisRunId"] != id1
        assert len(call_log) == before + 1
        print("OK different product → new run")

        # --- 4) Failure is not cached ---
        def boom(**_kwargs):
            with lock:
                call_log.append(("fail-product", "en"))
            raise RuntimeError("simulated bedrock failure")

        api_server.run_analysis = boom  # type: ignore[assignment]
        analyze_cache.clear_analyze_cache()
        call_log.clear()

        fail1 = client.post(
            "/api/analyze",
            json={"language": "en", "productId": "shopping-memo"},
        )
        assert fail1.status_code == 502, fail1.text

        # Restore success runner for same key — must execute again (not stuck on failure).
        api_server.run_analysis = fake_run_analysis  # type: ignore[assignment]
        ok_after = client.post(
            "/api/analyze",
            json={"language": "en", "productId": "shopping-memo"},
        )
        assert ok_after.status_code == 200, ok_after.text
        # One failure attempt + one success = at least 2 calls for shopping-memo en
        shopping_calls = [c for c in call_log if c[0] == "shopping-memo" or c[0] == "fail-product"]
        assert len(shopping_calls) >= 2, call_log
        print("OK failure not cached; subsequent success runs")

        # --- 5) Single-flight: concurrent same key → one runner ---
        analyze_cache.clear_analyze_cache()
        call_log.clear()
        barrier = threading.Barrier(3)
        results: list[str] = []

        def worker() -> None:
            barrier.wait()
            resp = client.post(
                "/api/analyze",
                json={"language": "en", "productId": "mahjong"},
            )
            assert resp.status_code == 200, resp.text
            results.append(resp.json()["analysisRunId"])

        threads = [threading.Thread(target=worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(set(results)) == 1, results
        assert len(call_log) == 1, call_log
        print("OK single-flight: 3 concurrent → 1 run_analysis")

        print("\nAll analyze cache checks passed.")
    finally:
        api_server.run_analysis = original
        analyze_cache.clear_analyze_cache()


if __name__ == "__main__":
    main()
