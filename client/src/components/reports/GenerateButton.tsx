// Generate button — triggers POST /generate. Shows spinner while generating.

import { Button } from "@/components/ui/button";

interface GenerateButtonProps {
  onClick: () => void;
  disabled?: boolean;
  label?: string;
  size?: "default" | "lg";
}

export function GenerateButton({
  onClick,
  disabled,
  label = "Generate",
  size = "lg",
}: GenerateButtonProps) {
  return (
    <Button type="button" onClick={onClick} disabled={disabled} size={size}>
      {disabled ? "Generating..." : label}
    </Button>
  );
}