// JSON-lines bridge from Python to the unmodified Meterless H-MEM reference
// (vendor/, Apache-2.0, upstream github.com/Meterless/Meterless @ 1742dec).
//
// Run: node --experimental-transform-types --no-warnings sidecar.ts <persistDir>
// One request per stdin line: {"id": n, "op": "...", ...}. One response per
// stdout line: {"id": n, "ok": true, "result": ...} or {"id": n, "ok": false, "error": "..."}.

import readline from "node:readline";
import { HMEM } from "./vendor/reference/src/index.ts";
import type { FeedbackKind, LedgerEntry, MemoryRecord } from "./vendor/reference/src/index.ts";

const persistDir = process.argv[2];
if (!persistDir) {
  process.stderr.write("usage: sidecar.ts <persistDir>\n");
  process.exit(2);
}
const hmem = new HMEM({ persistDir, actor: process.env.HMEM_ACTOR ?? "indie-growth-agent" });

function publicRecord(m: MemoryRecord) {
  const { embedding, ...rest } = m;
  return rest;
}

function ledgerWithIndex(entries: readonly LedgerEntry[], memoryId?: string) {
  return entries
    .map((entry, index) => ({ index, ...entry }))
    .filter((e) => memoryId === undefined || e.memoryId === memoryId);
}

type Request = { id: number; op: string; [key: string]: unknown };

function handle(req: Request): unknown {
  switch (req.op) {
    case "ping":
      return { records: hmem.store.all().length, ledger: hmem.ledger.all().length };
    case "add":
      return publicRecord(hmem.add(req.input as Parameters<HMEM["add"]>[0]));
    case "query": {
      const result = hmem.query(String(req.query), {
        topN: req.topN as number | undefined,
        threshold: req.threshold as number | undefined,
        chatId: req.chatId as string | undefined,
      });
      return {
        memories: result.memories.map((r) => ({ memory: publicRecord(r.memory), relevance: r.relevance })),
        context: result.context,
        trace: result.trace,
      };
    }
    case "feedback":
      hmem.feedback(String(req.memoryId), req.kind as FeedbackKind);
      return publicRecord(hmem.store.get(String(req.memoryId))!);
    case "ledger":
      return ledgerWithIndex(hmem.ledger.all(), req.memoryId as string | undefined);
    default:
      throw new Error(`unknown op ${req.op}`);
  }
}

const rl = readline.createInterface({ input: process.stdin, terminal: false });
rl.on("line", (line) => {
  if (!line.trim()) return;
  let id: number | null = null;
  try {
    const req = JSON.parse(line) as Request;
    id = req.id;
    process.stdout.write(JSON.stringify({ id, ok: true, result: handle(req) }) + "\n");
  } catch (err) {
    process.stdout.write(JSON.stringify({ id, ok: false, error: String((err as Error).message ?? err) }) + "\n");
  }
});
