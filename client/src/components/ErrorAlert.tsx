// Error alert — destructive bg, white text.

import { cn } from "@/lib/utils";

interface ErrorAlertProps {
  errors?: string[];
  message?: string;
}

export function ErrorAlert({ errors, message }: ErrorAlertProps) {
  const msgs = errors?.length ? errors : message ? [message] : [];
  if (msgs.length === 0) return null;

  return (
    <div
      role="alert"
      className={cn(
        "rounded-md bg-destructive p-3 text-sm text-destructive-foreground",
      )}
    >
      {msgs.map((m, i) => (
        <div key={i}>{m}</div>
      ))}
    </div>
  );
}