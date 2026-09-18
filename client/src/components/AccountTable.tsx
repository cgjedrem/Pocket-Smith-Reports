import { useCallback, useEffect, useMemo, useState } from "react";

import { listAccounts } from "@/api/accounts";
import { listPartners } from "@/api/partners";
import { AccountRow } from "@/components/AccountRow";
import { EmptyState } from "@/components/EmptyState";
import { ErrorAlert } from "@/components/ErrorAlert";
import { Pagination } from "@/components/Pagination";
import {
  Table,
  TableBody,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Account, Partner } from "@/types/api";

// Account table — ~10 per page, client-side pagination.

const PAGE_SIZE = 10;

export function AccountTable() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [partners, setPartners] = useState<Partner[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const refresh = useCallback(async () => {
    try {
      const [accList, partnerList] = await Promise.all([
        listAccounts(),
        listPartners(),
      ]);
      setAccounts(accList.accounts);
      setPartners(partnerList.partners);
    } catch (err) {
      setError((err as { detail?: string })?.detail ?? "Cannot reach server");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Sort: non-excluded first, excluded last. Stable within each group.
  const sortedAccounts = useMemo(
    () => [...accounts].sort((a, b) => Number(a.excluded) - Number(b.excluded)),
    [accounts],
  );

  const totalPages = Math.max(1, Math.ceil(sortedAccounts.length / PAGE_SIZE));
  // Clamp page — data may shrink after refresh, leaving page out of range.
  const safePage = Math.min(page, totalPages);
  const pageAccounts = useMemo(
    () => sortedAccounts.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE),
    [sortedAccounts, safePage],
  );

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading...</p>;
  }

  return (
    <div>
      {error && <ErrorAlert message={error} />}

      {accounts.length === 0 ? (
        <EmptyState message="No accounts — run sync first." />
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Partner</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Excluded</TableHead>
                <TableHead> </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pageAccounts.map((a) => (
                <AccountRow
                  key={a.id}
                  account={a}
                  partners={partners}
                  onSaved={refresh}
                />
              ))}
            </TableBody>
          </Table>
          <Pagination
            page={safePage}
            totalPages={totalPages}
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  );
}