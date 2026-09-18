// Status badge — running/success/failed.

import type { VariantProps } from "class-variance-authority";

import { Badge, badgeVariants } from "@/components/ui/badge";
import type { SyncStatusType } from "@/types/api";

type Status = SyncStatusType;
type BadgeVariant = NonNullable<VariantProps<typeof badgeVariants>["variant"]>;

const VARIANT: Record<Status, BadgeVariant> = {
  running: "secondary",
  success: "default",
  failed: "destructive",
};

const LABELS: Record<Status, string> = {
  running: "Running",
  success: "Success",
  failed: "Failed",
};

interface StatusBadgeProps {
  status: Status;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <Badge variant={VARIANT[status]}>{LABELS[status]}</Badge>
  );
}