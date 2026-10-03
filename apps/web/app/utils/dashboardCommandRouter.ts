type CommandAdapters = {
  power: (message: string) => boolean | "panel";
  shouldOrchestrate: (message: string) => boolean;
  object: (message: string) => boolean;
  sheet: (message: string) => boolean;
  info: (message: string) => boolean;
  action: (message: string) => boolean;
};

/** One precedence policy for local commands; adapters keep their supported grammar. */
export function routeDashboardCommand(message: string, adapters: CommandAdapters): "handled" | "panel" | "orchestrate" {
  const power = adapters.power(message);
  if (power) return power === "panel" ? "panel" : "handled";
  if (adapters.shouldOrchestrate(message)) return "orchestrate";
  for (const adapter of [adapters.object, adapters.sheet, adapters.info, adapters.action]) {
    if (adapter(message)) return "handled";
  }
  return "orchestrate";
}
