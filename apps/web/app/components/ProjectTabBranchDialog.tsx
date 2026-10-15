import { useEffect, useRef } from "react";
import type { TabBranchChoice } from "../hooks/useProjectTabBranch";

export function ProjectTabBranchDialog({ open, onChoose }: { open: boolean; onChoose: (choice: TabBranchChoice) => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (open && !dialog.current?.open) dialog.current?.showModal();
    if (!open) dialog.current?.close();
  }, [open]);
  return <dialog ref={dialog} aria-labelledby="tab-branch-title" data-testid="project-tab-branch-dialog"
    className="civora-dialog m-auto w-[min(92vw,420px)] rounded-xl border border-slate-200 bg-white p-4 shadow-xl backdrop:bg-slate-950/40"
    onCancel={event => { event.preventDefault(); onChoose("cancel"); }}>
    <h2 id="tab-branch-title" className="text-lg font-semibold text-slate-900">Keep these edits separate?</h2>
    <p className="mt-2 text-sm text-slate-600">This project is open elsewhere. Save your edits as a copy or replace the original. Replacing keeps a recovery snapshot.</p>
    <div className="mt-5 flex flex-wrap gap-2">
      <button type="button" autoFocus onClick={() => onChoose("copy")} className="rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white">Save as a copy</button>
      <button type="button" onClick={() => onChoose("replace")} className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-800">Replace original</button>
      <button type="button" onClick={() => onChoose("cancel")} className="rounded-lg px-3 py-2 text-sm text-slate-600">Keep editing</button>
    </div>
  </dialog>;
}
