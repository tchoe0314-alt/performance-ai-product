import type { RefObject } from "react";

import { DisclosurePanel } from "./ui";

type AddressSuggestion = {
  lat?: number;
  lng?: number;
  display_name?: string;
};

type AutoExistingConditionsStatus = {
  status: string;
  message: string;
};

type SetupAddressSectionProps = {
  pendingAddressEdit: boolean;
  siteAddress: string;
  appliedAddress: string;
  addressNeedsApply: boolean;
  hasAppliedAddress: boolean;
  localAddressLocked: boolean;
  siteScaleLocked: boolean;
  onlineDiscoveryBusy: boolean;
  addressSuggestions: AddressSuggestion[];
  autoExistingConditionsStatus: AutoExistingConditionsStatus;
  siteAddressInputRef: RefObject<HTMLInputElement | null>;
  onSiteAddressChange: (value: string) => void;
  onSelectedAddressSuggestionChange: (value: AddressSuggestion | null) => void;
  onAddressSuggestionsChange: (value: AddressSuggestion[]) => void;
  onSaveSiteAddress: () => void;
  onCreateCenteredSite: () => void;
  onStartBlankSite: () => void;
};

export function SetupAddressSection({
  pendingAddressEdit,
  siteAddress,
  appliedAddress,
  addressNeedsApply,
  hasAppliedAddress,
  localAddressLocked,
  siteScaleLocked,
  onlineDiscoveryBusy,
  addressSuggestions,
  autoExistingConditionsStatus,
  siteAddressInputRef,
  onSiteAddressChange,
  onSelectedAddressSuggestionChange,
  onAddressSuggestionsChange,
  onSaveSiteAddress,
  onStartBlankSite,
}: SetupAddressSectionProps) {
  return (
    <DisclosurePanel
      defaultOpen
      testId="setup-address-truth"
      title="Address / Location"
      subtitle={pendingAddressEdit ? siteAddress.trim() : appliedAddress || siteAddress.trim() || "No address applied"}
      status={addressNeedsApply ? "Needs apply" : hasAppliedAddress ? "Applied" : localAddressLocked ? "Local" : "Not set"}
      statusClassName={
        addressNeedsApply
          ? "bg-amber-50 text-amber-700"
          : hasAppliedAddress || localAddressLocked
            ? "bg-emerald-50 text-emerald-700"
            : "bg-slate-100 text-slate-500"
      }
    >
      <label className="block text-xs font-semibold text-slate-700">
        Project address
        <input
          ref={siteAddressInputRef}
          aria-label="Type project address"
          value={siteAddress}
          onChange={(event) => {
            onSiteAddressChange(event.target.value);
            onSelectedAddressSuggestionChange(null);
          }}
          placeholder="123 Main St, City, State"
          className="mt-2 w-full rounded-[7px] border border-slate-300 bg-white px-3 py-2.5 text-sm font-medium normal-case tracking-normal text-slate-900 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
        />
      </label>
      {addressSuggestions.length && !siteScaleLocked ? (
        <div className="mt-2 max-h-40 overflow-y-auto rounded-lg border border-slate-200 bg-white p-1 text-xs text-slate-600">
          <p className="px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
            Optional address matches
          </p>
          {addressSuggestions.map((suggestion) => (
            <button
              key={`${suggestion.lat ?? "lat"}-${suggestion.lng ?? "lng"}-${suggestion.display_name ?? "address"}`}
              type="button"
              aria-label={`Use address suggestion ${suggestion.display_name ?? "address"}`}
              onClick={() => {
                onSelectedAddressSuggestionChange(suggestion);
                onSiteAddressChange(suggestion.display_name ?? siteAddress);
                onAddressSuggestionsChange([]);
              }}
              className="w-full rounded-md px-3 py-2 text-left text-[12px] transition hover:bg-slate-50"
            >
              <span className="block truncate">{suggestion.display_name ?? "Address suggestion"}</span>
            </button>
          ))}
        </div>
      ) : null}
      <button
        type="button"
        onClick={onSaveSiteAddress}
        disabled={!siteAddress.trim() || onlineDiscoveryBusy}
        aria-label={siteAddress.trim() ? "Apply address" : "Enter address first"}
        className="mt-3 w-full rounded-[7px] border border-blue-600 bg-blue-600 px-3 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
      >
        {onlineDiscoveryBusy ? "Finding site context..." : siteAddress.trim() ? "Apply & Find Site Context" : "Enter an address"}
      </button>
      <button
        type="button"
        onClick={onStartBlankSite}
        aria-label="Start a blank site from detailed setup controls and clear address map evidence"
        className="mt-2 w-full px-2 py-1 text-center text-xs font-semibold text-slate-500 transition hover:text-slate-900"
      >
        Start without an address
      </button>
      {autoExistingConditionsStatus.status === "blocked" ? (
        <p data-testid="apply-address-status" className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800">
          Needs input: {autoExistingConditionsStatus.message.replace(/\bblocked:?/gi, "needs input:").replace(/\bfailed\b/gi, "could not complete")}
        </p>
      ) : null}
    </DisclosurePanel>
  );
}
