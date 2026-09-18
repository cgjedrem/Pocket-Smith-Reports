// Stale badge — shows when synced_at > thresholdHours ago.

import { Badge } from "@/components/ui/badge";

const DEFAULT_THRESHOLD_HOURS = 24;

export function BillsStaleBadge({
  syncedAt,
  thresholdHours = DEFAULT_THRESHOLD_HOURS,
}: {
  syncedAt: string;
  thresholdHours?: number;
}) {
  const ageMs = Date.now() - new Date(syncedAt).getTime();
  if (ageMs <= thresholdHours * 3600 * 1000) return null;
  const date = new Date(syncedAt).toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
  return (
    <Badge
      variant="secondary"
      title={`Last synced ${date}`}
      className="gap-1"
    >
      Stale
    </Badge>
  );
}
