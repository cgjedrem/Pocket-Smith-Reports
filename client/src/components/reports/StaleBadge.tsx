// Stale badge — shows when report txn count != ps_raw txn count.

import { Badge } from "@/components/ui/badge";

export function StaleBadge() {
  return (
    <Badge variant="secondary" title="Report txn count differs from source data">
      Stale
    </Badge>
  );
}