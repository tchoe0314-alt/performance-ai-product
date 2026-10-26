import { expect, test } from "@playwright/test";
import { provenSupersededHistoryReads, type CurrentHistoryProof,
  type HistoryRequestObservation } from "./helpers/historyRequestEvidence";

const proof: CurrentHistoryProof = { projectId: "synthetic", revision: "revision-b",
  headerRevision: "revision-b", headerNameMatches: true, headerHistoryMatches: true,
  historyResponseMatches: true };
const path = "/api/projects/synthetic/calculations";
const old: HistoryRequestObservation = { id: 1, method: "GET", path, actorMatches: true,
  startedAt: 100, failedAt: 500, error: "net::ERR_ABORTED", startedOrder: 1, abortOrder: 2, failedOrder: 4 };
const replacement: HistoryRequestObservation = { id: 2, method: "GET", path, actorMatches: true,
  startedAt: 499, completedAt: 550, status: 200, startedOrder: 3 };

test("only proven superseded same-project reads are accepted without mutating evidence", () => {
  const observations = [old, replacement];
  const original = JSON.stringify(observations);
  expect([...provenSupersededHistoryReads(observations, proof)]).toEqual([1]);
  expect(JSON.stringify(observations)).toBe(original);
});

test("a chain of superseded reads requires a completed final response", () => {
  const middle = { ...old, id: 2, startedAt: 499, failedAt: 700, startedOrder: 3, abortOrder: 5, failedOrder: 7 };
  const latest = { ...replacement, id: 3, startedAt: 699, completedAt: 750, startedOrder: 6 };
  expect([...provenSupersededHistoryReads([old, middle, latest], proof)]).toEqual([1, 2]);
});

for (const [name, observations, current] of [
  ["missing replacement", [old], proof],
  ["canceled current read", [old, { ...replacement, completedAt: undefined, failedAt: 560, error: "net::ERR_ABORTED" }], proof],
  ["timeout", [{ ...old, failedAt: 6100 }, { ...replacement, startedAt: 6099, completedAt: 6200 }], proof],
  ["server failure", [old, { ...replacement, status: 503 }], proof],
  ["body not finished", [old, { ...replacement, completedAt: undefined }], proof],
  ["wrong actor", [old, { ...replacement, actorMatches: false }], proof],
  ["wrong project", [old, { ...replacement, path: "/api/projects/other/calculations" }], proof],
  ["canceled write", [{ ...old, method: "POST" }, replacement], proof],
  ["canceled upload", [{ ...old, path: "/api/upload-survey" }, replacement], proof],
  ["unrelated later retry", [old, { ...replacement, startedAt: 520, startedOrder: 5 }], proof],
  ["stale header", [old, replacement], { ...proof, headerRevision: "revision-a" }],
  ["wrong displayed project", [old, replacement], { ...proof, headerNameMatches: false }],
  ["unavailable or incorrect history", [old, replacement], { ...proof, headerHistoryMatches: false }],
  ["incorrect response content", [old, replacement], { ...proof, historyResponseMatches: false }],
  ["missing revision proof", [old, replacement], { ...proof, revision: "" }],
  ["non-cancellation network failure", [{ ...old, error: "net::ERR_CONNECTION_RESET" }, replacement], proof],
  ["invalid replacement clock", [old, { ...replacement, startedAt: NaN }], proof],
  ["no observed cancellation signal", [{ ...old, abortOrder: undefined }, replacement], proof],
  ["replacement before cancellation", [old, { ...replacement, startedOrder: 1 }], proof],
  ["missing rejection order", [{ ...old, failedOrder: undefined }, replacement], proof],
] as Array<[string, HistoryRequestObservation[], CurrentHistoryProof]>) {
  test(`history cancellation remains a failure: ${name}`, () => {
    expect([...provenSupersededHistoryReads(observations, current)]).toEqual([]);
  });
}
