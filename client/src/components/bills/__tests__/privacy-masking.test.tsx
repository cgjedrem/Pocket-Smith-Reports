// Bills surface privacy masking — SC-001 + research.md Decision 3b.
// Hydrates bills-source from a synthetic BillsSnapshot through the SAME
// mapper path useBillsSnapshot uses, renders the EconomyBar, toggles the
// privacy flag, and asserts labels re-derive to "****" with NO new fetch.

import { act, render, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/bills", () => ({
  getSnapshot: vi.fn(),
  getEvents: vi.fn(),
  getEvent: vi.fn(),
}));

import { getSnapshot } from "@/api/bills";
import { EconomyBar } from "@/components/bills/EconomyBar";
import { useBillsSnapshot } from "@/hooks/useBills";
import { getMonths, reset } from "@/lib/bills-source";
import { setAmountsHidden } from "@/lib/privacy-store";
import type { BillsSnapshot } from "@/types/bills";

const mockedGetSnapshot = vi.mocked(getSnapshot);

function makeSnapshot(): BillsSnapshot {
  return {
    schema_version: 1,
    month: "2026-07",
    month_label: "July 2026",
    is_past: true,
    is_current: false,
    is_future: false,
    synced_at: "2026-08-02T14:01:08Z",
    bills_count: 1,
    buys_count: 1,
    warnings: [],
    partners: [
      {
        partner: "Fixture A",
        partner_id: "partner_a",
        partner_slot: "a",
        salary: 42000,
        bills: 15500,
        planned_cc_buys: 3500,
        everyday_budget: 8200,
        savings_transfer: 5000,
        savings_planned: 3000,
        savings_delta: 2000,
        savings_balance: 32000,
        estimated_cc_bill: null,
        real_bills: null,
        real_cc_bill: 9800,
        cc_usage: 4200,
        budget_usage: 4200,
        net: 16700,
        status: "covered",
        events: [],
      },
    ],
    source_counts: {
      ps_events_fetched: 10,
      ps_transactions_fetched: 5,
      events_kept_after_filter: 2,
    },
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  setAmountsHidden(false);
  reset();
  mockedGetSnapshot.mockResolvedValue(makeSnapshot());
});

afterEach(() => {
  setAmountsHidden(false);
  reset();
});

describe("bills surface privacy masking", () => {
  it("re-derives cached snapshot labels on toggle — masked, no refetch", async () => {
    const { result } = renderHook(() => useBillsSnapshot("2026-07", 0, 0));
    await waitFor(() => expect(result.current.loading).toBe(false));

    const months = getMonths();
    expect(months.length).toBe(1);
    const economy = months[0].partners[0];

    // Visible baseline — real kr labels.
    expect(economy.estimatedSalaryLabel).toContain("kr");
    expect(economy.estimatedSalaryLabel).toContain("42,000");

    // Render the partner card bar; capture width styles + status text.
    const visible = render(<EconomyBar economy={economy} />);
    const widthsBefore = [...visible.container.querySelectorAll("[style]")].map(
      (el) => (el as HTMLElement).style.cssText,
    );
    expect(visible.container.textContent).toContain(
      "CC bill covered by salary",
    );

    const fetchesBefore = mockedGetSnapshot.mock.calls.length;

    // Toggle hidden — hook re-maps cached snapshots and re-hydrates.
    act(() => setAmountsHidden(true));

    const maskedEconomy = getMonths()[0].partners[0];
    expect(maskedEconomy.estimatedSalaryLabel).toBe("****");
    expect(maskedEconomy.billsLabel).toBe("****");
    expect(maskedEconomy.estimatedCcBillLabel).toBe("****");
    expect(maskedEconomy.ccUsageLabel).toBe("****");
    expect(maskedEconomy.savingsBalanceLabel).toBe("****");
    expect(maskedEconomy.savingsDeltaLabel).toBe("****");
    // Bar labels baked into the view model are masked too.
    expect(maskedEconomy.bar.netLabel).toBe("****");
    expect(maskedEconomy.bar.remainingLabel).toMatch(/^\*\*\*\*/);

    // Zero network requests caused by the toggle (FR-008).
    expect(mockedGetSnapshot.mock.calls.length).toBe(fetchesBefore);

    // Status text + geometry untouched.
    const masked = render(<EconomyBar economy={maskedEconomy} />);
    expect(masked.container.textContent).toContain(
      "CC bill covered by salary",
    );
    const widthsAfter = [...masked.container.querySelectorAll("[style]")].map(
      (el) => (el as HTMLElement).style.cssText,
    );
    expect(widthsAfter).toEqual(widthsBefore);

    // Toggle back — exact values restored, still no refetch.
    act(() => setAmountsHidden(false));
    expect(getMonths()[0].partners[0].estimatedSalaryLabel).toContain(
      "42,000",
    );
    expect(mockedGetSnapshot.mock.calls.length).toBe(fetchesBefore);
  });
});
