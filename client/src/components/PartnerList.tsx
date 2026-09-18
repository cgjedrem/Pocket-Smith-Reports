import { useCallback, useEffect, useState } from "react";

import {
  createPartner,
  deletePartner,
  listPartners,
  updatePartner,
} from "@/api/partners";
import { EmptyState } from "@/components/EmptyState";
import { ErrorAlert } from "@/components/ErrorAlert";
import { PartnerForm } from "@/components/PartnerForm";
import { Button } from "@/components/ui/button";
import type { Partner } from "@/types/api";

// Partner list — CRUD inline.

export function PartnerList() {
  const [partners, setPartners] = useState<Partner[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const list = await listPartners();
      setPartners(list.partners);
    } catch (err) {
      setError((err as { detail?: string })?.detail ?? "Cannot reach server");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleCreate = useCallback(
    async (label: string) => {
      setError(null);
      try {
        await createPartner(label);
        setAdding(false);
        refresh();
      } catch (err) {
        setError((err as { detail?: string })?.detail ?? "Cannot reach server");
      }
    },
    [refresh]
  );

  const handleUpdate = useCallback(
    async (id: string, label: string) => {
      setError(null);
      try {
        await updatePartner(id, label);
        setEditingId(null);
        refresh();
      } catch (err) {
        setError((err as { detail?: string })?.detail ?? "Cannot reach server");
      }
    },
    [refresh]
  );

  const handleDelete = useCallback(
    async (id: string) => {
      if (!window.confirm("Delete this partner?")) return;
      setError(null);
      setDeletingId(id);
      try {
        await deletePartner(id);
        refresh();
      } catch (err) {
        setError((err as { detail?: string })?.detail ?? "Cannot reach server");
      } finally {
        setDeletingId(null);
      }
    },
    [refresh]
  );

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading...</p>;
  }

  return (
    <div>
      {error && <ErrorAlert message={error} />}

      {partners.length === 0 && !adding && (
        <EmptyState message="No partners yet." />
      )}

      <ul className="m-0 list-none p-0">
        {partners.map((p) => (
          <li
            key={p.id}
            className="flex items-center gap-2 border-b border-border py-1"
          >
            {editingId === p.id ? (
              <PartnerForm
                initialLabel={p.label}
                onSubmit={(label) => handleUpdate(p.id, label)}
                onCancel={() => setEditingId(null)}
              />
            ) : (
              <>
                <span className="flex-1">{p.label}</span>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setEditingId(p.id)}
                >
                  Edit
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => handleDelete(p.id)}
                  disabled={deletingId === p.id}
                >
                  {deletingId === p.id ? "..." : "Delete"}
                </Button>
              </>
            )}
          </li>
        ))}
      </ul>

      {adding ? (
        <PartnerForm onSubmit={handleCreate} onCancel={() => setAdding(false)} />
      ) : (
        <Button type="button" className="mt-2" onClick={() => setAdding(true)}>
          Add Partner
        </Button>
      )}
    </div>
  );
}