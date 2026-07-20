export type PreviewQualityValue = "standard" | "high";

export function PreviewQualityToggle({
  value,
  onChange,
  standardTestId,
  highTestId,
  buttonClassName = "inline-flex h-8 items-center rounded-md border px-2.5 text-xs font-semibold",
}: {
  value: PreviewQualityValue;
  onChange: (value: PreviewQualityValue) => void;
  standardTestId?: string;
  highTestId?: string;
  buttonClassName?: string;
}) {
  const inactiveClass = "border-slate-200 bg-white text-slate-600";
  const activeClass = "border-slate-900 bg-slate-950 text-white";
  const setQuality = (next: PreviewQualityValue) => {
    if (value === next) return;
    onChange(next);
  };

  return (
    <>
      <button
        type="button"
        data-testid={standardTestId}
        onClick={() => setQuality("standard")}
        className={`${buttonClassName} ${value === "standard" ? activeClass : inactiveClass}`}
      >
        Standard
      </button>
      <button
        type="button"
        data-testid={highTestId}
        onClick={() => setQuality("high")}
        className={`${buttonClassName} ${value === "high" ? activeClass : inactiveClass}`}
      >
        High
      </button>
    </>
  );
}
