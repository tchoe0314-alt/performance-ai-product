import {
  CheckCircle2, CircleHelp, EyeOff, GitBranch, Link2, LoaderCircle,
  LockKeyhole, MousePointer2, OctagonAlert, Pin, TriangleAlert, Unplug, Clock3,
} from "lucide-react";

// Presentation only: callers supply authoritative states. Higher confidence
// or successful draft checks must never be converted into "verified" here.
export const WORKSPACE_STATES = {
  selected: { label: "Selected", icon: MousePointer2 },
  hovered: { label: "Hovered", icon: MousePointer2 },
  hidden: { label: "Hidden", icon: EyeOff },
  locked: { label: "Locked", icon: LockKeyhole },
  fixed: { label: "Fixed", icon: Pin },
  following: { label: "Following", icon: Link2 },
  ask: { label: "Ask", icon: CircleHelp },
  independent: { label: "Independent", icon: Unplug },
  stale: { label: "Stale", icon: Clock3 },
  updating: { label: "Updating", icon: LoaderCircle },
  blocked: { label: "Blocked", icon: OctagonAlert },
  unverified: { label: "Unverified", icon: CircleHelp },
  conflicting: { label: "Conflicting", icon: TriangleAlert },
  assumed: { label: "Assumed", icon: GitBranch },
  verified: { label: "Verified", icon: CheckCircle2 },
} as const;
export type WorkspaceVisualState = keyof typeof WORKSPACE_STATES;

export function WorkspaceStateBadge({ state, title, label }: {
  state: WorkspaceVisualState; title?: string; label?: string;
}) {
  const definition = WORKSPACE_STATES[state];
  const Icon = definition.icon;
  return <span className="civora-state-badge" data-ui-state={state} title={title}>
    <Icon aria-hidden="true" className={state === "updating" ? "civora-state-spinner" : undefined} />
    <span>{label ?? definition.label}</span>
  </span>;
}
