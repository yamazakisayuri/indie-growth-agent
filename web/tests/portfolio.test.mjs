import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import {
  buildPortfolioEntries,
  selectKpis,
  selectTopAction,
} from "../src/lib/portfolio.ts";
import {
  loadCachedReport,
  loadSelectedProductId,
  saveCachedReport,
  saveSelectedProductId,
} from "../src/lib/report-cache.ts";

function installLocalStorage() {
  const data = new Map();
  globalThis.window = {
    localStorage: {
      getItem: (key) => (data.has(key) ? data.get(key) : null),
      setItem: (key, value) => data.set(key, String(value)),
      removeItem: (key) => data.delete(key),
    },
  };
}

function report(productId, overrides = {}) {
  return {
    source: "live",
    dataSource: "live",
    analysisRunId: `run-${productId}`,
    language: "en",
    appName: productId,
    periodLabel: "Oct 14 – Oct 20",
    comparisonLabel: "vs previous 7 days",
    period: { start: "", end: "", lookbackDays: 7, label: "", comparisonLabel: "" },
    metrics: [],
    metricsPayload: {},
    actions: [],
    facts: [],
    speculation: [],
    dataScope: [],
    groundingRules: [],
    product: { id: productId, name: productId, type: "hybrid" },
    ...overrides,
  };
}

const PRODUCTS = [
  { id: "mahjong", name: "Mahjong", type: "hybrid" },
  { id: "shopping-memo", name: "Shopping", type: "mobile_app" },
  { id: "nextuta", name: "Nextuta", type: "hybrid" },
];

describe("selectTopAction", () => {
  it("picks the lowest rank regardless of order", () => {
    const top = selectTopAction([
      { rank: 2, title: "Second", reason: "b" },
      { rank: 1, title: "First", reason: "a" },
      { rank: 3, title: "Third", reason: "c" },
    ]);
    assert.equal(top?.title, "First");
  });

  it("ignores untitled actions and returns null when none remain", () => {
    assert.equal(selectTopAction([{ rank: 1, title: " ", reason: "" }]), null);
    assert.equal(selectTopAction([]), null);
    assert.equal(selectTopAction(undefined), null);
  });
});

describe("selectKpis", () => {
  it("keeps API order, skips metrics without a value, and caps per block", () => {
    const [block] = selectKpis([
      {
        id: "app_store",
        title: "App Store",
        source: "ASC",
        connected: true,
        metrics: [
          { id: "impressions", label: "Impressions", changePercent: null },
          { id: "first_time_downloads", label: "Downloads", changePercent: -12.5, value: "40" },
          { id: "active_users", label: "Active", changePercent: 3 },
          { id: "extra", label: "Extra", changePercent: 1, value: "9" },
        ],
      },
    ]);
    assert.equal(block.status, "ok");
    assert.deepEqual(
      block.metrics.map((metric) => metric.id),
      ["first_time_downloads", "active_users"],
    );
    assert.equal(block.metrics[0].value, "40");
  });

  it("distinguishes not connected from connected-without-values", () => {
    const [off, empty] = selectKpis([
      { id: "revenue", title: "Revenue", source: "AdMob", connected: false, statusMessage: "AdMob not configured", metrics: [] },
      { id: "usage", title: "Usage", source: "GA4", connected: true, metrics: [{ id: "x", label: "x", changePercent: null }] },
    ]);
    assert.equal(off.status, "not_connected");
    assert.equal(off.statusMessage, "AdMob not configured");
    assert.equal(empty.status, "no_data");
    assert.deepEqual(empty.metrics, []);
  });
});

describe("buildPortfolioEntries", () => {
  it("lists every configured product in catalog order and marks missing reports", () => {
    const entries = buildPortfolioEntries(PRODUCTS, {
      "shopping-memo": report("shopping-memo", {
        actions: [{ rank: 1, title: "Fix onboarding", reason: "Drop at step 2" }],
      }),
      nextuta: null,
    });
    assert.deepEqual(
      entries.map((entry) => [entry.product.id, entry.status]),
      [
        ["mahjong", "not_analyzed"],
        ["shopping-memo", "analyzed"],
        ["nextuta", "not_analyzed"],
      ],
    );
    const analyzed = entries[1];
    assert.equal(analyzed.analysisRunId, "run-shopping-memo");
    assert.equal(analyzed.topAction?.title, "Fix onboarding");
  });

  it("does not fabricate KPIs or recommendations for not-analyzed products", () => {
    const [entry] = buildPortfolioEntries([PRODUCTS[0]], {});
    assert.deepEqual(Object.keys(entry).sort(), ["product", "status"]);
  });
});

describe("report cache (Portfolio → Dashboard handoff)", () => {
  beforeEach(installLocalStorage);

  it("restores the selected product and its own cached report", () => {
    saveCachedReport("mahjong", report("mahjong"));
    saveCachedReport("shopping-memo", report("shopping-memo"));
    saveSelectedProductId("mahjong");

    // Clicking a Portfolio card saves the target product, then the Dashboard hydrates.
    saveSelectedProductId("shopping-memo");
    const selected = loadSelectedProductId();
    assert.equal(selected, "shopping-memo");
    assert.equal(loadCachedReport(selected)?.analysisRunId, "run-shopping-memo");
  });

  it("returns null for a product that has never been analyzed", () => {
    saveCachedReport("mahjong", report("mahjong"));
    assert.equal(loadCachedReport("nextuta"), null);
  });

  it("rejects a cached report recorded for a different product", () => {
    window.localStorage.setItem(
      "indie-growth-agent:lastReports",
      JSON.stringify({ nextuta: report("mahjong") }),
    );
    assert.equal(loadCachedReport("nextuta"), null);
  });

  it("never returns mock or run-less reports", () => {
    saveCachedReport("mahjong", report("mahjong", { dataSource: "mock", source: "mock" }));
    assert.equal(loadCachedReport("mahjong"), null);
    window.localStorage.setItem(
      "indie-growth-agent:lastReports",
      JSON.stringify({ mahjong: report("mahjong", { analysisRunId: "" }) }),
    );
    assert.equal(loadCachedReport("mahjong"), null);
  });
});
