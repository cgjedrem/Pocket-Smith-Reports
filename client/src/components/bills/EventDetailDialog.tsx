// Event detail dialog — fetches one event by id, renders 10 fields.

import { useEffect } from "react";

import { ErrorAlert } from "@/components/ErrorAlert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import { formatKr } from "./finance-data";
import { useBillsEvent } from "@/hooks/useBills";

const AUTO_CLOSE_MS = 3000;

export function EventDetailDialog({
  open,
  id,
  month,
  onClose,
}: {
  open: boolean;
  id: string | null;
  month: string;
  onClose: () => void;
}) {
  const { event, loading, error, notFound } = useBillsEvent(id, month, open);

  // Auto-close on event-not-found after delay.
  useEffect(() => {
    if (!notFound) return;
    const t = setTimeout(onClose, AUTO_CLOSE_MS);
    return () => clearTimeout(t);
  }, [notFound, onClose]);

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <DialogContent className="w-full max-w-md">
        <DialogHeader>
          <DialogTitle>Event detail</DialogTitle>
          <DialogDescription>
            {id ? `Event ${id} for ${month}` : ""}
          </DialogDescription>
        </DialogHeader>

        {loading && (
          <div className="text-sm text-muted-foreground">Loading…</div>
        )}

        {error && (
          <ErrorAlert message={error.detail} />
        )}

        {notFound && (
          <div className="rounded-md border border-warning bg-warning/10 px-4 py-3 text-sm text-foreground">
            Event not found in {month}. Closing…
          </div>
        )}

        {event && !loading && (
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <Field label="ID" value={event.id} />
            <Field label="Date" value={event.date} />
            <Field label="Day" value={String(event.day)} />
            <Field label="Title (category)" value={event.title} />
            <Field label="Type" value={event.type} />
            <Field label="Account" value={event.account} />
            {/* BillsEvent.partner is the plain display label. */}
            <Field label="Partner" value={event.partner} />
            <Field label="Amount" value={formatKr(event.amount)} />
            <Field
              label="CC payment"
              value={event.is_cc_payment ? "Yes" : "No"}
            />
            <Field
              label="Matched"
              value={
                event.is_matched === null
                  ? "—"
                  : event.is_matched
                    ? "Yes"
                    : "No"
              }
            />
          </dl>
        )}

        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline">
              Close
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd className="font-medium text-foreground break-all">{value}</dd>
    </>
  );
}
