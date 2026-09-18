import { useCallback, useEffect, useState } from "react";

import { getApiKeyStatus, updateApiKey } from "@/api/settings";
import { ErrorAlert } from "@/components/ErrorAlert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

// API key section — masked, never display raw key.

export function ApiKeySection() {
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [showInput, setShowInput] = useState(false);
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const s = await getApiKeyStatus();
      setConfigured(s.configured);
    } catch (err) {
      setError((err as { detail?: string })?.detail ?? "Cannot reach server");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleSave = useCallback(async () => {
    if (!value.trim()) {
      setError("api_key is required");
      return;
    }
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await updateApiKey(value);
      setSaved(true);
      setShowInput(false);
      setValue("");
      refresh();
    } catch (err) {
      setError((err as { detail?: string })?.detail ?? "Cannot reach server");
    } finally {
      setSaving(false);
    }
  }, [value, refresh]);

  if (configured === null) {
    return <p className="text-sm text-muted-foreground">Loading...</p>;
  }

  return (
    <div>
      {configured ? (
        <div className="mb-2 flex items-center gap-2">
          <Badge variant="default">✓ Configured</Badge>
          {!showInput && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setShowInput(true)}
            >
              Change
            </Button>
          )}
        </div>
      ) : (
        <p className="mb-2 text-sm text-muted-foreground">No API key set.</p>
      )}

      {(showInput || !configured) && (
        <div className="mb-2 flex items-center gap-2">
          <Label htmlFor="ps-api-key" className="sr-only">
            PocketSmith API key
          </Label>
          <input
            id="ps-api-key"
            type="password"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="PocketSmith API key"
            className="h-9 rounded-md border border-input bg-transparent px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
          />
          <Button type="button" onClick={handleSave} disabled={saving}>
            {saving ? "Saving..." : "Save"}
          </Button>
          {showInput && (
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setShowInput(false);
                setValue("");
                setError(null);
              }}
            >
              Cancel
            </Button>
          )}
        </div>
      )}

      {saved && (
        <p className="text-sm text-primary">Saved.</p>
      )}

      {error && <ErrorAlert message={error} />}
    </div>
  );
}