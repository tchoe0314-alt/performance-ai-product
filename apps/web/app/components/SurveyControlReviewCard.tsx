export type SurveyControlReviewCardProps = {
  canReview: boolean;
  completeForReview: boolean;
  pending: boolean;
  message: string;
  tone: "neutral" | "success" | "warning" | "error";
  onAccept: () => void;
  onReject: () => void;
};

export function SurveyControlReviewCard(props: SurveyControlReviewCardProps) {
  return (
    <div data-testid="survey-control-review" className="rounded-lg border border-slate-200 bg-slate-50 p-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Survey-control review</p>
      <p data-testid="survey-control-review-status" className={`mt-1 text-xs leading-5 ${
        props.tone === "error" ? "text-red-700" : props.tone === "warning" ? "text-amber-800" : props.tone === "success" ? "text-emerald-700" : "text-slate-600"
      }`}>{props.message}</p>
      {props.canReview ? (
        <div className="mt-2 grid grid-cols-2 gap-2">
          <button type="button" data-testid="survey-control-accept" disabled={props.pending || !props.completeForReview} onClick={props.onAccept} className="rounded border border-emerald-700 bg-white px-2 py-1.5 text-xs font-semibold text-emerald-800 disabled:cursor-not-allowed disabled:opacity-50">
            {props.pending ? "Recording…" : "Accept for review"}
          </button>
          <button type="button" data-testid="survey-control-reject" disabled={props.pending} onClick={props.onReject} className="rounded border border-slate-300 bg-white px-2 py-1.5 text-xs font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-50">
            Reject
          </button>
        </div>
      ) : (
        <p className="mt-2 text-[11px] text-slate-500">Reviewer access is required to record a decision.</p>
      )}
    </div>
  );
}
