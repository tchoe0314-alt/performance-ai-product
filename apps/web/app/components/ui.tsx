import React from "react";

export function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`civora-panel ${className}`}
    >
      {children}
    </div>
  );
}

export function CardHeader({ children }: { children: React.ReactNode }) {
  return <div className="p-6 pb-4">{children}</div>;
}

export function CardContent({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={`p-6 pt-0 ${className}`}>{children}</div>;
}

export function SectionTitle({
  icon: Icon,
  title,
  desc,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  desc: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <div className="rounded-2xl border border-slate-200 bg-[linear-gradient(180deg,#ffffff_0%,#f8fafc_100%)] p-2.5 shadow-[0_10px_30px_-20px_rgba(15,23,42,0.45)]">
        <Icon className="h-5 w-5 text-slate-800" />
      </div>
      <div>
        <h3 className="text-[15px] font-semibold tracking-tight text-slate-950">
          {title}
        </h3>
        <p className="mt-1 text-sm leading-6 text-slate-500">{desc}</p>
      </div>
    </div>
  );
}

export function Pill({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full border border-[var(--civora-border)] bg-[var(--civora-surface-muted)] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--civora-text-muted)]">
      {children}
    </span>
  );
}

export function SmallButton({
  children,
  onClick,
  variant = "primary",
  disabled = false,
  type = "button",
}: {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: "primary" | "secondary";
  disabled?: boolean;
  type?: "button" | "submit" | "reset";
}) {
  const styles =
    variant === "primary"
      ? "border border-[var(--civora-accent)] bg-[var(--civora-accent)] text-white hover:bg-blue-700"
      : "civora-control text-[var(--civora-text)]";

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center rounded-[var(--civora-radius-md)] px-4 py-2.5 text-sm font-medium shadow-[0_12px_30px_-22px_rgba(15,23,42,0.55)] transition duration-200 ${styles} ${
        disabled ? "cursor-not-allowed opacity-60" : "hover:-translate-y-0.5"
      }`}
    >
      {children}
    </button>
  );
}

export function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <label className="civora-muted-label" htmlFor={htmlFor}>
        {label}
      </label>
      {children}
    </div>
  );
}

export function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`w-full rounded-[var(--civora-radius-md)] border border-[var(--civora-border)] bg-[var(--civora-surface-solid)] px-4 py-3 text-sm text-[var(--civora-text)] shadow-[inset_0_1px_0_rgba(255,255,255,0.85)] placeholder:text-[var(--civora-text-soft)] outline-none transition focus:border-[var(--civora-border-strong)] focus:ring-4 focus:ring-[var(--civora-accent-soft)] ${
        props.className ?? ""
      }`}
    />
  );
}

export function TextArea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement> & { ref?: React.Ref<HTMLTextAreaElement> }) {
  return (
    <textarea
      {...props}
      className={`min-h-[168px] max-h-[280px] w-full resize-none overflow-y-auto rounded-[var(--civora-radius-lg)] border border-[var(--civora-border)] bg-[var(--civora-surface-solid)] px-4 py-3.5 text-sm leading-6 text-[var(--civora-text)] shadow-[inset_0_1px_0_rgba(255,255,255,0.85)] placeholder:text-[var(--civora-text-soft)] outline-none transition focus:border-[var(--civora-border-strong)] focus:ring-4 focus:ring-[var(--civora-accent-soft)] ${
        props.className ?? ""
      }`}
    />
  );
}

export function DisclosurePanel({
  title,
  subtitle,
  status,
  statusClassName = "bg-slate-100 text-slate-500",
  children,
  defaultOpen = false,
  className = "",
  bodyClassName = "",
  testId,
}: {
  title: string;
  subtitle: React.ReactNode;
  status?: React.ReactNode;
  statusClassName?: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
  className?: string;
  bodyClassName?: string;
  testId?: string;
}) {
  const [isOpen, setIsOpen] = React.useState(defaultOpen);

  React.useEffect(() => {
    if (defaultOpen) setIsOpen(true);
  }, [defaultOpen]);

  return (
    <details
      open={isOpen}
      onToggle={(event) => setIsOpen(event.currentTarget.open)}
      className={`overflow-clip rounded-xl border border-slate-200/90 bg-white ${className}`}
      data-testid={testId}
    >
      <summary className="flex min-h-14 cursor-pointer items-center gap-2.5 px-3.5 py-3">
        <span className="min-w-0 flex-1">
          <span className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            {title}
          </span>
          <span className="mt-1 block break-words text-sm font-semibold leading-5 text-slate-950">
            {subtitle}
          </span>
        </span>
        {status ? (
          <span
            className={`shrink-0 rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${statusClassName}`}
          >
            {status}
          </span>
        ) : null}
      </summary>
      <div className={`border-t border-slate-100 px-3.5 py-3.5 ${bodyClassName}`}>
        {children}
      </div>
    </details>
  );
}

export function PanelCard({
  children,
  className = "",
  testId,
}: {
  children: React.ReactNode;
  className?: string;
  testId?: string;
}) {
  return (
    <div
      className={`rounded-xl border border-slate-200/90 bg-white p-3.5 ${className}`}
      data-testid={testId}
    >
      {children}
    </div>
  );
}
