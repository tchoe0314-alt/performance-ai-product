import { expect, test } from "@playwright/test";
import { routeDashboardCommand } from "../../app/utils/dashboardCommandRouter";

test("command precedence stops at the first handler and preserves panel ownership", () => {
  for (const winner of ["power", "object", "sheet", "info", "action", "none", "panel", "orchestrate"]) {
    const called: string[] = [];
    const adapter = (key: string) => () => { called.push(key); return winner === key; };
    const outcome = routeDashboardCommand("fixture", {
      power: () => { called.push("power"); return winner === "panel" ? "panel" : winner === "power"; },
      shouldOrchestrate: adapter("orchestrate"), object: adapter("object"),
      sheet: adapter("sheet"), info: adapter("info"), action: adapter("action"),
    });
    expect(outcome).toBe(winner === "panel" ? "panel" : ["none", "orchestrate"].includes(winner) ? "orchestrate" : "handled");
    const order = ["power", "orchestrate", "object", "sheet", "info", "action"];
    expect(called).toEqual(winner === "none" ? order : winner === "panel" ? ["power"] : order.slice(0, order.indexOf(winner) + 1));
  }
});
