"use client";

type AppHeaderProps = {
  userEmail: string;
  onOpenProjects: () => void;
  onOpenDocs: () => void;
  onOpenChat: () => void;
  onLogout: () => void;
};

export default function AppHeader({
  userEmail,
  onOpenProjects,
  onOpenDocs,
  onOpenChat,
  onLogout,
}: AppHeaderProps) {
  return (
    <header className="w-full bg-[radial-gradient(circle_at_top,#1f2937_0%,#0b1120_55%,#0a0f1d_100%)] text-white">
      <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-6 py-4">
        <div className="flex items-center gap-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-full border border-white/20 bg-white/10 text-lg font-semibold">
            C
          </div>
          <div>
            <p className="text-lg font-semibold tracking-tight">Civora AI</p>
            <p className="text-xs uppercase tracking-[0.3em] text-white/60">Autonomous Civil</p>
          </div>
        </div>
        <nav className="relative hidden items-center gap-6 text-sm font-medium text-white/80 md:flex">
          <button
            type="button"
            onClick={onOpenProjects}
            className="text-white/70 transition hover:text-white"
          >
            Projects
          </button>
          <button
            type="button"
            onClick={onOpenDocs}
            className="text-white/70 transition hover:text-white"
          >
            Docs
          </button>
          <button
            type="button"
            onClick={onOpenChat}
            className="text-white/70 transition hover:text-white"
          >
            Chat
          </button>
        </nav>
        <div className="flex items-center gap-3">
          <span className="hidden rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs text-white/70 md:inline-flex">
            {userEmail}
          </span>
          <button
            type="button"
            onClick={onLogout}
            className="rounded-full border border-white/20 bg-white/10 px-3 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-white/80 transition hover:bg-white/20"
          >
            Sign Out
          </button>
        </div>
      </div>
    </header>
  );
}
