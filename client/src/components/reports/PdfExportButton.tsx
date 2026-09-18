// PDF export button — triggers POST /pdf → browser download.

import { Button } from "@/components/ui/button";

interface PdfExportButtonProps {
  onClick: () => void;
  disabled?: boolean;
}

export function PdfExportButton({ onClick, disabled }: PdfExportButtonProps) {
  return (
    <Button
      type="button"
      variant="outline"
      onClick={onClick}
      disabled={disabled}
    >
      {disabled ? "Exporting..." : "Export PDF"}
    </Button>
  );
}