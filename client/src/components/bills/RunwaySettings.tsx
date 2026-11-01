import { useId } from "react";
import { ErrorAlert } from "@/components/ErrorAlert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import type { RunwayState } from "@/hooks/useRunway";
import { runwayIssueText } from "@/lib/runway";

interface RunwaySettingsProps {
  state: RunwayState;
}

export function RunwaySettings({ state }: RunwaySettingsProps) {
  const id = useId();
  const { settings, settingsLoading, settingsError, draftIds, saving, saveError } = state;
  const blocked = settingsLoading || settingsError !== null || !settings || saving;
  const invalidDraft = draftIds.some((accountId) =>
    !settings?.accounts.find((account) => account.id === accountId)?.eligible,
  );
  const savedMessage = state.error
    ? "Selection saved locally; result refresh failed. Retry runway."
    : state.loading
      ? "Selection saved locally. Updating runway result…"
      : "Selection saved locally. Runway refreshed independently.";

  return (
    <details className="rounded-lg border p-4">
      <summary className="cursor-pointer font-medium focus-visible:outline-ring">Liquid account settings</summary>
      <div className="mt-4 flex flex-col gap-3 text-sm">
        <p>Choose liquid checking or savings accounts explicitly. Save changes only local runway settings — no sync, account-binding changes, or financial record changes.</p>
        <p>Clear selection prepares an empty draft; only Save selection applies it. Reload saved selection discards unsaved changes.</p>
        {settingsLoading && <p role="status">Loading runway settings…</p>}
        {settingsError && <ErrorAlert message={settingsError} />}
        {settings && !settingsLoading && (
          <>
            <ul className="space-y-1 text-muted-foreground">
              {[...new Set(settings.issues.map((entry) => runwayIssueText(entry, settings.owners, settings.accounts)))].map((text) => <li key={text}>{text}</li>)}
            </ul>
            {settings.accounts.length === 0 && <p>No account choices available. Check local account mappings and recorded balances.</p>}
            <fieldset disabled={blocked} className="flex flex-col gap-3">
              <legend className="mb-3 font-medium">Reserve account choices</legend>
              {settings.accounts.map((account) => {
                const checked = draftIds.includes(account.id);
                const owner = settings.owners.find((entry) => entry.partner_id === account.partner_id)?.label ?? account.partner_id ?? "Owner unknown";
                const inputId = `${id}-${account.id}`;
                return (
                  <div key={account.id} className="rounded-md border p-3">
                    <div className="flex items-center gap-3">
                      <Checkbox
                        id={inputId}
                        checked={checked}
                        disabled={blocked || (!account.eligible && !checked)}
                        aria-describedby={`${inputId}-info`}
                        onCheckedChange={(value) => state.setDraftIds(value === true
                          ? [...draftIds, account.id]
                          : draftIds.filter((entry) => entry !== account.id))}
                      />
                      <Label htmlFor={inputId} className="break-words">{account.name} · {owner}</Label>
                    </div>
                    <div id={`${inputId}-info`} className="mt-2 text-xs text-muted-foreground">
                      <p>Account {account.id} · {account.type ?? "Unknown type"} · {account.eligible ? "Eligible" : "Ineligible"}{account.excluded ? " · Excluded" : ""}{settings.liquid_account_ids.includes(account.id) ? " · Saved selection" : ""}</p>
                      {account.issues.map((entry, index) => <p key={index}>{runwayIssueText(entry, settings.owners, settings.accounts)}</p>)}
                      {!account.eligible && checked && <p>Uncheck to remove this invalid saved selection.</p>}
                    </div>
                  </div>
                );
              })}
            </fieldset>
          </>
        )}
        <p role="status">
          {saving ? "Saving selection locally…" : state.saved ? savedMessage : !settings || settingsError ? "Saved selection unavailable." : state.dirty ? `Unsaved changes · ${draftIds.length} accounts in draft.` : `${settings.liquid_account_ids.length} accounts in saved selection.`}
        </p>
        {invalidDraft && !blocked && <p>Remove ineligible selected accounts before saving.</p>}
        {saveError && <ErrorAlert message={saveError} />}
        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" disabled={blocked || invalidDraft || !state.dirty} onClick={() => void state.save()}>
            {saving ? "Saving…" : "Save selection"}
          </Button>
          <Button type="button" size="sm" variant="outline" disabled={blocked || !state.dirty} onClick={() => state.setDraftIds(settings?.liquid_account_ids ?? [])}>Reset changes</Button>
          <Button type="button" size="sm" variant="outline" disabled={blocked || draftIds.length === 0} onClick={() => state.setDraftIds([])}>Clear selection</Button>
          <Button type="button" size="sm" variant="ghost" disabled={saving || settingsLoading} onClick={() => void state.retrySettings()}>
            {settingsError ? "Retry settings" : "Reload saved selection"}
          </Button>
        </div>
      </div>
    </details>
  );
}
