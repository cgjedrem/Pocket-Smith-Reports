// MegaReportExportDialog — confirm + POST /api/mega-reports/{start}/{end}/pdf.
// Backend always returns full PDF (no section selection yet). Download blob,
// create temp <a>, click, defer URL revoke past download init.

import { useEffect, useRef, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { exportMegaPdf } from "@/api/mega_reports";
import { ApiError } from "@/types/api";

interface MegaReportExportDialogProps {
  start: string;
  end: string;
  triggerLabel?: string;
  onError?: (message: string) => void;
  onSuccess?: () => void;
}

export function MegaReportExportDialog({
  start,
  end,
  triggerLabel = "Export PDF",
  onError,
  onSuccess,
}: MegaReportExportDialogProps) {
  const [open, setOpen] = useState(false);
  const [exporting, setExporting] = useState(false);

  // Abort in-flight export when dialog closes or component unmounts.
  const abortRef = useRef<AbortController | null>(null);
  useEffect(() => {
    if (!open && abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
  }, [open]);
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const handleExport = async () => {
    setExporting(true);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const blob = await exportMegaPdf(start, end, controller.signal);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `mega_report_${start}_${end}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      // Defer revoke — browsers need the URL alive until the download
      // stream initializes. setTimeout hands control back to the event loop
      // so the download starts before the URL is freed.
      setTimeout(() => URL.revokeObjectURL(url), 0);
      onSuccess?.();
      setOpen(false);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        // User closed dialog mid-export — silent.
        return;
      }
      const detail =
        err instanceof ApiError
          ? err.detail
          : err instanceof Error
            ? err.message
            : "PDF export failed";
      onError?.(detail);
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
      setExporting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline">
          {triggerLabel}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Export mega report to PDF</DialogTitle>
          <DialogDescription>
            Generate a PDF of the full mega report for {start} → {end}. The file
            downloads automatically when ready.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => setOpen(false)}
            disabled={exporting}
          >
            Cancel
          </Button>
          <Button type="button" onClick={handleExport} disabled={exporting}>
            {exporting ? "Exporting..." : "Export PDF"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
