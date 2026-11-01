import { useState } from "react";
import { LifestyleCreepCard } from "@/components/bills/LifestyleCreepCard";
import { useLifestyleCreep } from "@/hooks/useLifestyleCreep";
import {
  canonicalThreshold, currentLifestyleMonth, defaultLifestyleSelection, lifestyleSelectionError,
} from "@/lib/lifestyle-creep";

export function LifestyleCreepPage() {
  const [selection, setSelection] = useState(() => defaultLifestyleSelection());
  const [draft, setDraft] = useState(selection);
  const [thresholdDraft, setThresholdDraft] = useState("20");
  const [appliedThreshold, setAppliedThreshold] = useState("20");
  const history = useLifestyleCreep(
    selection.target, appliedThreshold, selection.referenceStart, selection.referenceEnd,
  );

  function applyComparison(target: string, referenceStart: string, referenceEnd: string) {
    if (lifestyleSelectionError(target, referenceStart, referenceEnd, currentLifestyleMonth())) return;
    const next = { target, referenceStart, referenceEnd };
    setSelection(next);
    setDraft(next);
  }

  function applyThreshold(value: string) {
    const canonical = canonicalThreshold(value);
    if (canonical === null) return;
    setAppliedThreshold(canonical);
    setThresholdDraft(canonical);
  }

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold">Lifestyle Creep</h1>
        <p className="text-sm text-muted-foreground">
          Compares spending in the selected target month with average monthly spending in the selected reference period.
          A category is flagged when it is above the applied threshold; this is descriptive, not advice.
        </p>
      </header>
      <LifestyleCreepCard
        targetMonth={selection.target}
        referenceStart={selection.referenceStart}
        referenceEnd={selection.referenceEnd}
        targetDraft={draft.target}
        referenceStartDraft={draft.referenceStart}
        referenceEndDraft={draft.referenceEnd}
        currentMonth={currentLifestyleMonth()}
        onTargetDraftChange={(target) => setDraft((value) => ({ ...value, target }))}
        onReferenceStartDraftChange={(referenceStart) => setDraft((value) => ({ ...value, referenceStart }))}
        onReferenceEndDraftChange={(referenceEnd) => setDraft((value) => ({ ...value, referenceEnd }))}
        onComparisonApply={applyComparison}
        thresholdDraft={thresholdDraft}
        appliedThreshold={appliedThreshold}
        onThresholdDraftChange={setThresholdDraft}
        onThresholdApply={applyThreshold}
        data={history.data}
        loading={history.loading}
        error={history.error}
        onRetry={history.retry}
      />
    </div>
  );
}
