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
      className={`rounded-[28px] border border-slate-200/80 bg-white/92 shadow-[0_20px_60px_-28px_rgba(15,23,42,0.28)] backdrop-blur ${className}`}
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
    <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600">
      {children}
    </span>
  );
}

export function SmallButton({
  children,
  onClick,
  variant = "primary",
  disabled = false,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: "primary" | "secondary";
  disabled?: boolean;
}) {
  const styles =
    variant === "primary"
      ? "border border-slate-900 bg-slate-950 text-white hover:bg-slate-800"
      : "border border-slate-200 bg-white text-slate-900 hover:border-slate-300 hover:bg-slate-50";

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center rounded-2xl px-4 py-2.5 text-sm font-medium shadow-[0_12px_30px_-22px_rgba(15,23,42,0.55)] transition duration-200 ${styles} ${
        disabled ? "cursor-not-allowed opacity-60" : "hover:-translate-y-0.5"
      }`}
    >
      {children}
    </button>
  );
}

export function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
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
      className={`w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-950 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)] placeholder:text-slate-400 outline-none transition focus:border-slate-400 focus:ring-4 focus:ring-slate-200/70 ${
        props.className ?? ""
      }`}
    />
  );
}

export function TextArea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={`min-h-[168px] max-h-[280px] w-full resize-none overflow-y-auto rounded-[24px] border border-slate-200 bg-white px-4 py-3.5 text-sm leading-6 text-slate-950 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)] placeholder:text-slate-400 outline-none transition focus:border-slate-400 focus:ring-4 focus:ring-slate-200/70 ${
        props.className ?? ""
      }`}
    />
  );
}
