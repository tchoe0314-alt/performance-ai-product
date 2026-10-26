import type { ProjectInput } from "../types";

type SiteInputs = NonNullable<NonNullable<ProjectInput["meta"]>["site_inputs"]>;
const plain = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);
const copy = (value: unknown): unknown => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
const own = (value: Record<string, unknown>, name: string) => Object.prototype.hasOwnProperty.call(value, name) ? value[name] : undefined;
const key = (value: unknown) => JSON.stringify(value, (_name, item) => plain(item)
  ? Object.fromEntries(Object.keys(item).sort().filter(name => item[name] !== undefined).map(name => [name, item[name]])) : item);

/** Rebase a save receipt onto newer live source inputs, never onto geometry.
 * Arrays/type changes are atomic; a concurrently changed live value wins.
 */
export function reconcileAcknowledgedSiteInputs(base: SiteInputs, live: SiteInputs, accepted: SiteInputs): SiteInputs {
  const merge = (before: unknown, current: unknown, saved: unknown): unknown => {
    if (key(before) === key(current)) return copy(saved);
    if (plain(before) && plain(current) && plain(saved)) {
      const result: Record<string, unknown> = {};
      for (const name of new Set([...Object.keys(before), ...Object.keys(current), ...Object.keys(saved)])) {
        const value = merge(own(before, name), own(current, name), own(saved, name));
        if (value !== undefined) Object.defineProperty(result, name, { value, enumerable: true, writable: true, configurable: true });
      }
      return result;
    }
    return copy(current);
  };
  return merge(base, live, accepted) as SiteInputs;
}
