// Empty state wrapper.

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface EmptyStateProps {
  message: string;
  children?: ReactNode;
}

export function EmptyState({ message, children }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "rounded-md border border-dashed border-border bg-muted/30 p-4 text-center text-muted-foreground",
      )}
    >
      <p>{message}</p>
      {children}
    </div>
  );
}