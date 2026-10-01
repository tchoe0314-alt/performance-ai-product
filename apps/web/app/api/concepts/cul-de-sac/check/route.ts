import { checkConcept, parseLayout } from "../../../../utils/culDeSacConcept";

// Stateless concept-only adapter. No project records or engineering approvals.
export async function POST(request: Request) {
  try {
    if (Number(request.headers.get("content-length")) > 8192) throw new Error("Layout too large");
    const reader = request.body?.getReader();
    if (!reader) throw new Error("Missing layout");
    const chunks: Uint8Array[] = [];
    let size = 0;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 8192) { await reader.cancel(); throw new Error("Layout too large"); }
      chunks.push(value);
    }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    const state = JSON.parse(new TextDecoder().decode(bytes));
    if (!state || !Number.isSafeInteger(state.revision) || state.revision < 0) throw new Error("Invalid revision");
    const layout = parseLayout(state);
    return Response.json({ revision: state.revision, issues: checkConcept(layout), check: "analytic-pavement-and-island" },
      { headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ error: "Invalid concept layout" }, { status: 400 });
  }
}
