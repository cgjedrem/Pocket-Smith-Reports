// 404 alert — page takeover when snapshot is missing.

import { RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export function BillsNotFoundAlert({
  month,
  onSyncClick,
}: {
  month: string;
  onSyncClick: (month: string) => void;
}) {
  return (
    <Card className="border-warning bg-warning/10">
      <CardContent className="flex flex-col gap-3 py-6">
        <div className="flex flex-col gap-1">
          <h2 className="text-lg font-semibold text-foreground">
            No snapshot for {month}
          </h2>
          <p className="text-sm text-muted-foreground">
            Run sync to generate this month&apos;s data. After the sync
            completes, come back to view the dashboard.
          </p>
        </div>
        <div>
          <Button onClick={() => onSyncClick(month)}>
            <RefreshCw />
            Run sync
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
