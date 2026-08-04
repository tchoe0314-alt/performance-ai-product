type PreviewRectObjectChromeProps = {
  showBox: boolean;
  showBoxChrome: boolean;
  selected: boolean;
  accessHighlighted: boolean;
  highQuality: boolean;
  visualKind: string;
  borderColor: string;
  outlineColor?: string;
};

export function PreviewRectObjectChrome({
  showBox,
  showBoxChrome,
  selected,
  accessHighlighted,
  highQuality,
  visualKind,
  borderColor,
  outlineColor,
}: PreviewRectObjectChromeProps) {
  const selectionBorderRadius =
    visualKind === "water"
      ? "44% 56% 48% 52% / 38% 46% 54% 62%"
      : visualKind === "road" || visualKind === "parking"
        ? "4px"
        : "8px";
  return (
    <>
      <div
        className={`pointer-events-none h-full w-full rounded-[8px] transition ${
          showBoxChrome ? `border ${borderColor}` : ""
        } ${
          showBoxChrome && selected ? "ring-2 ring-amber-400 ring-offset-2 ring-offset-white/80 shadow-[0_0_0_6px_rgba(251,191,36,0.14)]" : ""
        } ${showBoxChrome && accessHighlighted ? "ring-2 ring-rose-300" : ""}`}
        style={{
          backgroundColor: "transparent",
          borderColor: showBoxChrome ? outlineColor || undefined : "transparent",
          borderRadius: selectionBorderRadius,
        }}
      />
      {selected && showBox ? (
        <>
          <div
            className="pointer-events-none absolute inset-0 border border-amber-500/70"
            style={{ borderRadius: selectionBorderRadius }}
          />
          {visualKind !== "water" ? [
            "left-0 top-0 -translate-x-1/2 -translate-y-1/2",
            "right-0 top-0 translate-x-1/2 -translate-y-1/2",
            "bottom-0 right-0 translate-x-1/2 translate-y-1/2",
            "bottom-0 left-0 -translate-x-1/2 translate-y-1/2",
          ].map((position) => (
            <span
              key={`box-grip-${position}`}
              className={`pointer-events-none absolute h-2.5 w-2.5 rounded-sm border border-white bg-amber-400 shadow ${position}`}
            />
          )) : null}
        </>
      ) : null}
      {showBox && highQuality && visualKind === "water" ? (
        <div className="pointer-events-none absolute inset-x-[14%] top-1/2 h-px -translate-y-1/2 bg-sky-100/60 shadow-[0_5px_0_rgba(224,242,254,0.34),0_-5px_0_rgba(224,242,254,0.24)]" />
      ) : null}
      {showBox && highQuality && visualKind === "utility" ? (
        <div className="pointer-events-none absolute left-1/2 top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/80 bg-violet-500/80" />
      ) : null}
    </>
  );
}
