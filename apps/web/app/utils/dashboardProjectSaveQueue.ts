export type DashboardProjectSaveQueue = { generation: number; tail: Promise<unknown> };

/** Preserve write order within a workspace; a new workspace owns an independent queue. */
export function enqueueDashboardProjectSave<T>(
  owner: { current: DashboardProjectSaveQueue | null },
  generation: number,
  save: () => Promise<T>,
): Promise<T> {
  if (!owner.current || owner.current.generation !== generation) {
    owner.current = { generation, tail: Promise.resolve() };
  }
  const queue = owner.current;
  const result = queue.tail.then(save);
  queue.tail = result.catch(() => undefined);
  return result;
}
