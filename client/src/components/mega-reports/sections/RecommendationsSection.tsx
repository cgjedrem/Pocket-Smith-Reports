// RecommendationsSection — recommendation cards if artifact exists, empty state if null.

import { EmptyState } from "@/components/EmptyState";
import type { MegaReportResponse, RecommendationSeverity } from "@/types/mega_report";

interface RecommendationsSectionProps {
  report: MegaReportResponse;
}

const SEVERITY_CLASS: Record<RecommendationSeverity, string> = {
  high: "bg-destructive text-white",
  medium: "bg-secondary text-secondary-foreground",
  low: "bg-muted text-muted-foreground",
};

export function RecommendationsSection({ report }: RecommendationsSectionProps) {
  const artifact = report.recommendations;

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold">9. Recommendations</h2>

      {!artifact || artifact.recommendations.length === 0 ? (
        <EmptyState message="No recommendations available." />
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {artifact.recommendations.map((rec) => (
            <div key={rec.id} className="rounded-md border border-border bg-card p-3">
              <div className="flex items-center justify-between gap-2">
                <h3 className="font-semibold">{rec.title}</h3>
                <span className={`rounded-full px-2 py-0.5 text-xs ${SEVERITY_CLASS[rec.severity]}`}>
                  {rec.severity}
                </span>
              </div>
              <p className="mt-1 text-sm">{rec.body}</p>
              {rec.evidence.length > 0 && (
                <ul className="mt-2 list-disc pl-5 text-xs text-muted-foreground">
                  {rec.evidence.map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}