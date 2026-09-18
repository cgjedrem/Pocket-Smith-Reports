// Partner form — inline add/edit.

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

interface PartnerFormProps {
  initialLabel?: string;
  onSubmit: (label: string) => void;
  onCancel: () => void;
}

export function PartnerForm({
  initialLabel = "",
  onSubmit,
  onCancel,
}: PartnerFormProps) {
  const [label, setLabel] = useState(initialLabel);
  const [err, setErr] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!label.trim()) {
      setErr("label is required");
      return;
    }
    onSubmit(label.trim());
  };

  return (
    <form onSubmit={handleSubmit} className="my-1 flex items-center gap-2">
      <Label htmlFor="partner-label" className="sr-only">Partner label</Label>
      <input
        id="partner-label"
        type="text"
        value={label}
        onChange={(e) => {
          setLabel(e.target.value);
          setErr(null);
        }}
        placeholder="Partner label"
        className="h-9 rounded-md border border-input bg-transparent px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
      />
      <Button type="submit" size="sm">Save</Button>
      <Button type="button" variant="outline" size="sm" onClick={onCancel}>
        Cancel
      </Button>
      {err && (
        <span className="text-sm text-destructive">{err}</span>
      )}
    </form>
  );
}