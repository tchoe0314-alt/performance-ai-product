/** One ephemeral entry per page instance; no tokens or project data in leases. */
const PREFIX = "civora-project-tab-v1:";
const TTL = 90_000;
export function projectTabLeaseKey(projectId: string, tabId: string) {
  return `${PREFIX}${projectId}:${tabId}`;
}
export function hasOtherProjectTab(storage: Pick<Storage, "length" | "key" | "getItem">, projectId: string, tabId: string, now = Date.now()) {
  const prefix = `${PREFIX}${projectId}:`;
  for (let index = 0; index < storage.length; index++) {
    const key = storage.key(index);
    if (!key?.startsWith(prefix) || key === projectTabLeaseKey(projectId, tabId)) continue;
    const seen = Number(storage.getItem(key));
    if (Number.isFinite(seen) && seen <= now && now - seen < TTL) return true;
  }
  return false;
}
