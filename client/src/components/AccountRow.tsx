import { useCallback, useEffect, useState } from "react";

import { updateBinding } from "@/api/accounts";
import { ErrorAlert } from "@/components/ErrorAlert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { TableCell, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import type { Account, AccountType, Partner } from "@/types/api";

// Account row — per-row save.

const TYPE_OPTIONS: Array<{ value: AccountType; label: string }> = [
  { value: null, label: "none" },
  { value: "checking", label: "checking" },
  { value: "cc", label: "cc" },
  { value: "savings", label: "savings" },
];

interface AccountRowProps {
  account: Account;
  partners: Partner[];
  onSaved: () => void;
}

export function AccountRow({ account, partners, onSaved }: AccountRowProps) {
  const [partnerId, setPartnerId] = useState<string | null>(account.partner_id);
  const [type, setType] = useState<AccountType>(account.type);
  const [excluded, setExcluded] = useState(account.excluded);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Resync local state only when server binding values actually change.
  // Primitive deps (not object ref) prevent cross-row reset on refresh.
  useEffect(() => {
    setPartnerId(account.partner_id);
    setType(account.type);
    setExcluded(account.excluded);
  }, [account.partner_id, account.type, account.excluded]);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await updateBinding(account.id, { partner_id: partnerId, type, excluded });
      setSaved(true);
      onSaved();
    } catch (err) {
      setError((err as { detail?: string })?.detail ?? "Cannot reach server");
    } finally {
      setSaving(false);
    }
  }, [account.id, partnerId, type, excluded, onSaved]);

  return (
    <>
      <TableRow className={cn(account.excluded && "opacity-50")}>
        <TableCell>{account.name}</TableCell>
        <TableCell>
          <Select
            value={partnerId ?? "__none__"}
            onValueChange={(v) => setPartnerId(v === "__none__" ? null : v)}
          >
            <SelectTrigger size="sm" className="w-[8rem]">
              <SelectValue placeholder="(none)" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__none__">(none)</SelectItem>
              {partners.map((p) => (
                <SelectItem key={p.id} value={p.id}>
                  {p.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </TableCell>
        <TableCell>
          <Select
            value={type ?? "__none__"}
            onValueChange={(v) =>
              setType((v === "__none__" ? null : v) as AccountType)
            }
          >
            <SelectTrigger size="sm" className="w-[7rem]">
              <SelectValue placeholder="none" />
            </SelectTrigger>
            <SelectContent>
              {TYPE_OPTIONS.map((o) => (
                <SelectItem key={o.label} value={o.value ?? "__none__"}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </TableCell>
        <TableCell>
          <Checkbox
            checked={excluded}
            onCheckedChange={(v) => setExcluded(Boolean(v))}
          />
        </TableCell>
        <TableCell>
          <Button
            type="button"
            size="sm"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? "..." : "Save"}
          </Button>
          {saved && (
            <span className="ml-1 text-sm text-primary">Saved</span>
          )}
        </TableCell>
      </TableRow>
      {error && (
        <TableRow>
          <TableCell colSpan={5} className="pt-1 pb-2">
            <ErrorAlert message={error} />
          </TableCell>
        </TableRow>
      )}
    </>
  );
}