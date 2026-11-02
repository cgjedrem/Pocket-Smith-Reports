import { useId } from "react";
import { Button } from "@/components/ui/button";
import { canonicalThreshold, lifestyleSelectionError, shiftLifestyleMonth } from "@/lib/lifestyle-creep";

export interface LifestyleCreepControlsProps {
  targetMonth: string;
  referenceStart: string;
  referenceEnd: string;
  targetDraft: string;
  referenceStartDraft: string;
  referenceEndDraft: string;
  currentMonth: string;
  onTargetDraftChange: (value: string) => void;
  onReferenceStartDraftChange: (value: string) => void;
  onReferenceEndDraftChange: (value: string) => void;
  onComparisonApply: (target: string, referenceStart: string, referenceEnd: string) => void;
  thresholdDraft: string;
  appliedThreshold: string;
  onThresholdDraftChange: (value: string) => void;
  onThresholdApply: (value: string) => void;
}

const inputClass = "h-9 w-full min-w-0 rounded-md border border-input bg-card px-2 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40";

export function LifestyleCreepControls(props: LifestyleCreepControlsProps) {
  const id = useId();
  const threshold = canonicalThreshold(props.thresholdDraft);
  const selectionError = lifestyleSelectionError(
    props.targetDraft, props.referenceStartDraft, props.referenceEndDraft, props.currentMonth,
  );
  const selectionChanged = props.targetDraft !== props.targetMonth
    || props.referenceStartDraft !== props.referenceStart
    || props.referenceEndDraft !== props.referenceEnd;
  const targetMax = shiftLifestyleMonth(props.currentMonth, -1);
  const referenceMax = shiftLifestyleMonth(props.targetDraft, -1);
  const rangeValid = !selectionError;
  return (
    <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
      <form noValidate className="min-w-0 space-y-2" onSubmit={(event) => {
        event.preventDefault();
        if (rangeValid) props.onComparisonApply(props.targetDraft, props.referenceStartDraft, props.referenceEndDraft);
      }}>
        <div className="grid items-end gap-2 sm:grid-cols-[1fr_1fr_1fr_auto]">
          <div className="min-w-0 space-y-2">
            <label htmlFor={`${id}-target`} className="text-sm font-medium">Target month</label>
            <input
              id={`${id}-target`} type="month" min="0001-03" max={targetMax}
              value={props.targetDraft} onChange={(event) => props.onTargetDraftChange(event.target.value)}
              aria-invalid={!!selectionError} aria-describedby={`${id}-comparison-help`} className={inputClass}
            />
          </div>
          <div className="min-w-0 space-y-2">
            <label htmlFor={`${id}-reference-start`} className="text-sm font-medium">Reference start</label>
            <input
              id={`${id}-reference-start`} type="month" min="0001-01" max={props.referenceEndDraft}
              value={props.referenceStartDraft} onChange={(event) => props.onReferenceStartDraftChange(event.target.value)}
              aria-invalid={!!selectionError} aria-describedby={`${id}-comparison-help`} className={inputClass}
            />
          </div>
          <div className="min-w-0 space-y-2">
            <label htmlFor={`${id}-reference-end`} className="text-sm font-medium">Reference end</label>
            <input
              id={`${id}-reference-end`} type="month" min={shiftLifestyleMonth(props.referenceStartDraft, 1)}
              max={referenceMax}
              value={props.referenceEndDraft} onChange={(event) => props.onReferenceEndDraftChange(event.target.value)}
              aria-invalid={!!selectionError} aria-describedby={`${id}-comparison-help`} className={inputClass}
            />
          </div>
          <Button type="submit" variant="outline">Apply comparison</Button>
        </div>
        <p id={`${id}-comparison-help`} aria-live="polite" className="text-xs text-muted-foreground">
          {selectionError ? `${selectionError} Draft not applied.`
            : selectionChanged ? "Draft not applied. Apply comparison to change the target and both reference bounds together."
              : "Choose one completed target and 2–24 consecutive completed reference months before it."}
        </p>
      </form>
      <form noValidate className="min-w-0 space-y-2" onSubmit={(event) => {
        event.preventDefault();
        if (threshold !== null) props.onThresholdApply(threshold);
      }}>
        <label htmlFor={`${id}-threshold`} className="text-sm font-medium">Threshold (1–100%)</label>
        <div className="flex items-center gap-2">
          <input
            id={`${id}-threshold`} type="text" inputMode="decimal"
            value={props.thresholdDraft} onChange={(event) => props.onThresholdDraftChange(event.target.value)}
            aria-invalid={threshold === null} aria-describedby={`${id}-threshold-help`}
            className={inputClass}
          />
          <Button type="submit" variant="outline" aria-label="Apply threshold">Apply threshold</Button>
        </div>
        <p id={`${id}-threshold-help`} className="text-xs text-muted-foreground">
          {threshold === null
            ? "Enter a finite decimal from 1 through 100, inclusive, without spaces. Draft not applied."
            : threshold !== props.appliedThreshold ? "Draft not applied. Apply to change sensitivity."
              : "Threshold applies to this visit only and is independent of the selected months."}
        </p>
      </form>
    </div>
  );
}
