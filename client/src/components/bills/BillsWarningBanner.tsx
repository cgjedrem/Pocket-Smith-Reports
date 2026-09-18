// Warning banner — yellow card for snapshot.warnings[].

import { AlertTriangle } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

export function BillsWarningBanner({ warnings }: { warnings: string[] }) {
  if (warnings.length === 0) return null;
  return (
    <Card className="border-warning bg-warning/10">
      <CardContent className="flex flex-col gap-1 py-4">
        <div className="flex items-center gap-2 font-semibold text-warning">
          <AlertTriangle className="size-4" />
          Fidelity warnings
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
