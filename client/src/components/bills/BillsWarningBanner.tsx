// Warning banner — yellow card for snapshot.warnings[]. Reused outside the
// bills domain (e.g. SplitConfigSection) via the optional `title` prop —
// default stays "Fidelity warnings" so every existing call site (Bills,
// ReportView, MegaReportView) is unaffected.

import { AlertTriangle } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

interface BillsWarningBannerProps {
  warnings: string[];
  title?: string;
}

export function BillsWarningBanner({ warnings, title = "Fidelity warnings" }: BillsWarningBannerProps) {
  if (warnings.length === 0) return null;
  return (
    <Card className="border-warning bg-warning/10">
      <CardContent className="flex flex-col gap-1 py-4">
        <div className="flex items-center gap-2 font-semibold text-warning">
          <AlertTriangle className="size-4" />
          {title}
        </div>
        <ul className="ml-6 list-disc text-sm text-foreground">
          {warnings.map((w, i) => (
            <li key={i}>{w}</li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
