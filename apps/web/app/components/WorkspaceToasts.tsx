export type WorkspaceToast = {
  id: string;
  title: string;
  detail?: string;
  tone?: "info" | "success" | "warning" | "error";
};

type WorkspaceToastsProps = {
  toasts: WorkspaceToast[];
};

export default function WorkspaceToasts({ toasts }: WorkspaceToastsProps) {
  if (!toasts.length) return null;

  return (
    <div className="fixed right-3 top-20 z-[70] flex w-[min(360px,calc(100vw-1.5rem))] flex-col gap-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`rounded-xl border px-3 py-2 shadow-lg backdrop-blur ${
            toast.tone === "error"
              ? "border-red-200 bg-red-50/95 text-red-800"
              : toast.tone === "success"
                ? "border-emerald-200 bg-emerald-50/95 text-emerald-800"
                : toast.tone === "warning"
                  ? "border-amber-200 bg-amber-50/95 text-amber-800"
                  : "border-slate-200 bg-white/95 text-slate-800"
          }`}
        >
          <p className="text-sm font-semibold">{toast.title}</p>
          {toast.detail ? <p className="mt-0.5 text-xs leading-5 opacity-80">{toast.detail}</p> : null}
        </div>
      ))}
    </div>
  );
}
