// Mapper tests â€” pure functions, no React, no API.

import { describe, expect, it } from "vitest";

import {
  mapEvent,
  mapPartnerToEconomy,
  mapSnapshotToEvents,
  mapSnapshotToMonthData,
} from "@/lib/bills-mapper";
import type { BillsSnapshot } from "@/types/bills";

function makeSnapshot(over: Partial<BillsSnapshot> = {}): BillsSnapshot {
  return {
    schema_version: 1,
    month: "2026-07",
    month_label: "July 2026",
    is_past: true,
    is_current: false,
    is_future: false,
    synced_at: "2026-08-02T14:01:08Z",
    bills_count: 2,
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
        events: [
          {
            id: "c1",
            date: "2026-07-25",
            day: 25,
            title: "Salary",
            type: "salary",
            account: "Income",
            partner: "Fixture A",
            partner_id: "partner_a",
            partner_slot: "a",
            amount: 42000,
            is_cc_payment: false,
            is_matched: null,
          },
        ],
      },
    ],
    source_counts: {
      ps_events_fetched: 100,
      ps_transactions_fetched: 50,
      events_kept_after_filter: 5,
    },
    ...over,
  };
}

describe("mapSnapshotToMonthData", () => {
  it("builds MonthData with key + label + monthIndex from month string", () => {
    const m = mapSnapshotToMonthData(makeSnapshot());
    expect(m.key).toBe("2026-07");
    expect(m.label).toBe("July 2026");
    expect(m.year).toBe(2026);
    expect(m.monthIndex).toBe(6); // July = 0-based 6
    expect(m.billsCount).toBe(2);
    expect(m.buysCount).toBe(1);
  });

  it("sums partner nets", () => {
    const snap = makeSnapshot({
      partners: [
        {
          partner: "A",
          partner_id: "partner_a",
          partner_slot: "a",
          salary: 100,
          bills: 0,
          planned_cc_buys: 0,
          everyday_budget: 0,
          savings_transfer: 0,
          savings_planned: 0,
          savings_delta: 0,
          savings_balance: 0,
          estimated_cc_bill: null,
          real_bills: null,
          real_cc_bill: null,
          cc_usage: 0,
          budget_usage: 0,
          net: 50,
          status: "covered",
          events: [],
        },
        {
          partner: "B",
          partner_id: "partner_b",
          partner_slot: "b",
          salary: 100,
          bills: 0,
          planned_cc_buys: 0,
          everyday_budget: 0,
          savings_transfer: 0,
          savings_planned: 0,
          savings_delta: 0,
          savings_balance: 0,
          estimated_cc_bill: null,
          real_bills: null,
          real_cc_bill: null,
          cc_usage: 0,
          budget_usage: 0,
          net: 30,
          status: "covered",
          events: [],
        },
      ],
    });
    expect(mapSnapshotToMonthData(snap).net).toBe(80);
  });

  it("flattens + sorts events by day asc", () => {
    const snap = makeSnapshot({
      partners: [
        {
          partner: "A",
          partner_id: "partner_a",
          partner_slot: "a",
          salary: 0,
          bills: 0,
          planned_cc_buys: 0,
          everyday_budget: 0,
          savings_transfer: 0,
          savings_planned: 0,
          savings_delta: 0,
          savings_balance: 0,
          estimated_cc_bill: null,
          real_bills: null,
          real_cc_bill: null,
          cc_usage: 0,
          budget_usage: 0,
          net: 0,
          status: "covered",
          events: [
            {
              id: "x",
              date: "2026-07-20",
              day: 20,
              title: "Late",
              type: "bill",
              account: "C",
              partner: "A",
              partner_id: "partner_a",
              partner_slot: "a",
              amount: -100,
              is_cc_payment: false,
              is_matched: null,
            },
            {
              id: "y",
              date: "2026-07-05",
              day: 5,
              title: "Early",
              type: "bill",
              account: "C",
              partner: "A",
              partner_id: "partner_a",
              partner_slot: "a",
              amount: -50,
              is_cc_payment: false,
              is_matched: null,
            },
          ],
        },
      ],
    });
    const m = mapSnapshotToMonthData(snap);
    expect(m.events[0].day).toBe(5);
    expect(m.events[1].day).toBe(20);
  });

  it("maps partners to PartnerEconomy", () => {
    const m = mapSnapshotToMonthData(makeSnapshot());
    expect(m.partners).toHaveLength(1);
    // Identity triple — id keys attribution, slot keys styling, label display.
    expect(m.partners[0].partner).toEqual({
      partner_id: "partner_a",
      partner_slot: "a",
      label: "Fixture A",
    });
    expect(m.partners[0].estimatedSalary).toBe(42000);
    expect(m.partners[0].status).toBe("covered");
  });

  it("handles snapshot with no partners", () => {
    const m = mapSnapshotToMonthData(
      makeSnapshot({ partners: [], bills_count: 0, buys_count: 0 }),
    );
    expect(m.partners).toHaveLength(0);
    expect(m.events).toHaveLength(0);
    expect(m.net).toBe(0);
  });
});

describe("mapSnapshotToEvents", () => {
  it("flattens events from all partners", () => {
    const snap = makeSnapshot({
      partners: [
        {
          partner: "A",
          partner_id: "partner_a",
          partner_slot: "a",
          salary: 0,
          bills: 0,
          planned_cc_buys: 0,
          everyday_budget: 0,
          savings_transfer: 0,
          savings_planned: 0,
          savings_delta: 0,
          savings_balance: 0,
          estimated_cc_bill: null,
          real_bills: null,
          real_cc_bill: null,
          cc_usage: 0,
          budget_usage: 0,
          net: 0,
          status: "covered",
          events: [
            {
              id: "1",
              date: "2026-07-01",
              day: 1,
              title: "Housing",
              type: "bill",
              account: "FxA Check",
              partner: "A",
              partner_id: "partner_a",
              partner_slot: "a",
              amount: -10,
              is_cc_payment: false,
              is_matched: null,
            },
            {
              id: "2",
              date: "2026-07-02",
              day: 2,
              title: "Income",
              type: "bill",
              account: "FxA Check",
              partner: "A",
              partner_id: "partner_a",
              partner_slot: "a",
              amount: 100,
              is_cc_payment: false,
              is_matched: null,
            },
          ],
        },
      ],
    });
    const evs = mapSnapshotToEvents(snap);
    expect(evs).toHaveLength(1);
    expect(evs[0].id).toBe("1");
  });

  it("filters out Income + Savings categories", () => {
    const snap = makeSnapshot({
      partners: [
        {
          partner: "A",
          partner_id: "partner_a",
          partner_slot: "a",
          salary: 0,
          bills: 0,
          planned_cc_buys: 0,
          everyday_budget: 0,
          savings_transfer: 0,
          savings_planned: 0,
          savings_delta: 0,
          savings_balance: 0,
          estimated_cc_bill: null,
          real_bills: null,
          real_cc_bill: null,
          cc_usage: 0,
          budget_usage: 0,
          net: 0,
          status: "covered",
          events: [
            {
              id: "inc",
              date: "2026-07-01",
              day: 1,
              title: "Income",
              type: "salary",
              account: "FxA Check",
              partner: "A",
              partner_id: "partner_a",
              partner_slot: "a",
              amount: 100,
              is_cc_payment: false,
              is_matched: null,
            },
            {
              id: "sav",
              date: "2026-07-02",
              day: 2,
              title: "Savings",
              type: "savings",
              account: "FxA Savings",
              partner: "A",
              partner_id: "partner_a",
              partner_slot: "a",
              amount: -10,
              is_cc_payment: false,
              is_matched: null,
            },
            {
              id: "bill",
              date: "2026-07-03",
              day: 3,
              title: "Housing",
              type: "bill",
              account: "FxA Check",
              partner: "A",
              partner_id: "partner_a",
              partner_slot: "a",
              amount: -50,
              is_cc_payment: false,
              is_matched: null,
            },
          ],
        },
      ],
    });
    const evs = mapSnapshotToEvents(snap);
    expect(evs.map((e) => e.id)).toEqual(["bill"]);
  });
});

describe("mapEvent", () => {
  it("copies fields 1:1", () => {
    const e = mapEvent({
      id: "x",
      date: "2026-07-01",
      day: 1,
      title: "t",
      type: "bill",
      account: "c",
      partner: "Fixture A",
      partner_id: "partner_a",
      partner_slot: "a",
      amount: -10,
      is_cc_payment: false,
      is_matched: null,
    });
    expect(e.id).toBe("x");
    expect(e.amount).toBe(-10);
    expect(e.type).toBe("bill");
  });

  it("passes salary type through unchanged (round-4 fix — no more coercion to bill)", () => {
    const e = mapEvent({
      id: "x",
      date: "2026-07-01",
      day: 1,
      title: "t",
      type: "salary",
      account: "c",
      partner: "Fixture A",
      partner_id: "partner_a",
      partner_slot: "a",
      amount: 42000,
      is_cc_payment: false,
      is_matched: null,
    });
    expect(e.type).toBe("salary");
  });

  it("passes savings type through unchanged (round-4 fix — no more coercion to bill)", () => {
    const e = mapEvent({
      id: "x",
      date: "2026-07-01",
      day: 1,
      title: "t",
      type: "savings",
      account: "c",
      partner: "Fixture A",
      partner_id: "partner_a",
      partner_slot: "a",
      amount: -10,
      is_cc_payment: false,
      is_matched: null,
    });
    expect(e.type).toBe("savings");
  });

  it("passes buy type through unchanged", () => {
    const e = mapEvent({
      id: "x",
      date: "2026-07-01",
      day: 1,
      title: "t",
      type: "buy",
      account: "c",
      partner: "Fixture A",
      partner_id: "partner_a",
      partner_slot: "a",
      amount: -10,
      is_cc_payment: false,
      is_matched: true,
    });
    expect(e.type).toBe("buy");
  });

  it("maps an unrecognized future type defensively to bill", () => {
    const e = mapEvent({
      id: "x",
      date: "2026-07-01",
      day: 1,
      title: "t",
      // Cast: simulate an unknown future BE type value not in the union.
      type: "transfer" as unknown as "bill",
      account: "c",
      partner: "Fixture A",
      partner_id: "partner_a",
      partner_slot: "a",
      amount: -10,
      is_cc_payment: false,
      is_matched: null,
    });
    expect(e.type).toBe("bill");
  });
});

describe("mapPartnerToEconomy", () => {
  it("maps numeric fields to labels", () => {
    const p = mapPartnerToEconomy({
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
    });
    // Identity triple — id keys attribution, slot keys styling, label display.
    expect(p.partner).toEqual({
      partner_id: "partner_a",
      partner_slot: "a",
      label: "Fixture A",
    });
    expect(p.estimatedSalary).toBe(42000);
    expect(p.billsLabel).toContain("15,500");
    expect(p.estimatedSalaryLabel).toContain("42,000");
    expect(p.status).toBe("covered");
  });

  it("passes budget through from BE everyday_budget verbatim (F2 §8)", () => {
    // Pin: budget === everyday_budget exactly. NO FE arithmetic —
    // no ccBuys add-back, no own-month subtraction, no next-month
    // lookup. BE formula = salary(m+1) − bills(m+1) − ccBuys(m+1);
    // 8200 ≠ any combination of this partner's own fields
    // (42000 − 15500 − 3500 = 23000), so equality proves passthrough.
    const p = mapPartnerToEconomy({
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
    });
    expect(p.budget).toBe(8_200);
    expect(p.budgetLabel).toBe("8,200 kr");
    // Bar-zone derives off the same value: 4200 / 8200 ≈ 51.2% → warning.
    expect(p.bar.budgetUsageWidth).toBe("51.21951219512195%");
    expect(p.bar.budgetOverspent).toBe(false);
    expect(p.bar.budgetFillTone).toBe("warning");
  });

  it("null everyday_budget → budget null + empty label (zone hidden)", () => {
    // Last sync-window month: BE has no m+1 data → everyday_budget null.
    // EconomyBar hides the whole budget zone on budget == null (same
    // gate pattern as realBillsLabel).
    const p = mapPartnerToEconomy({
      partner: "X",
      partner_id: "partner_x",
      partner_slot: "a",
      salary: 30_000,
      bills: 12_000,
      planned_cc_buys: 0,
      everyday_budget: null,
      savings_transfer: 0,
      savings_planned: 0,
      savings_delta: 0,
      savings_balance: 0,
      estimated_cc_bill: null,
      real_bills: null,
      real_cc_bill: null,
      cc_usage: 0,
      budget_usage: 0,
      net: 18_000,
      status: "covered",
      events: [],
    });
    expect(p.budget).toBeNull();
    expect(p.budgetLabel).toBe("");
    // Bar stays null-safe (placeholder 0 — never rendered).
    expect(p.bar.budgetUsageWidth).toBe("0%");
    expect(p.bar.budgetFillTone).toBe("shortfall");
    expect(p.bar.budgetOverspent).toBe(false);
  });

  it("negative everyday_budget passes through (no floor at 0)", () => {
    // BE formula can go negative (bills(m+1) + ccBuys(m+1) > salary(m+1)).
    // Label must show "-4,000 kr" verbatim, not "0 kr".
    const p = mapPartnerToEconomy({
      partner: "X",
      partner_id: "partner_x",
      partner_slot: "a",
      salary: 10_000,
      bills: 12_000,
      planned_cc_buys: 2_000,
      everyday_budget: -4_000,
      savings_transfer: 0,
      savings_planned: 0,
      savings_delta: 0,
      savings_balance: 0,
      estimated_cc_bill: null,
      real_bills: null,
      real_cc_bill: null,
      cc_usage: 0,
      budget_usage: 0,
      net: -2_000,
      status: "shortfall",
      events: [],
    });
    expect(p.budget).toBe(-4_000);
    expect(p.budgetLabel).toBe("-4,000 kr");
    // budget <= 0 → forced shortfall tone (existing convention, kept).
    expect(p.bar.budgetFillTone).toBe("shortfall");
  });

  it("prefers real_cc_bill over estimated_cc_bill for display", () => {
    const p = mapPartnerToEconomy({
      partner: "X",
      partner_id: "partner_x",
      partner_slot: "a",
      salary: 100,
      bills: 10,
      planned_cc_buys: 0,
      everyday_budget: 0,
      savings_transfer: 0,
      savings_planned: 0,
      savings_delta: 0,
      savings_balance: 0,
      estimated_cc_bill: 50,
      real_bills: null,
      real_cc_bill: 80,
      cc_usage: 5,
      budget_usage: 5,
      net: 10,
      status: "covered",
      events: [],
    });
    // Display uses real (80) when present
    expect(p.estimatedCcBill).toBe(80);
  });

  it("falls back to estimated when real is null", () => {
    const p = mapPartnerToEconomy({
      partner: "X",
      partner_id: "partner_x",
      partner_slot: "a",
      salary: 100,
      bills: 10,
      planned_cc_buys: 0,
      everyday_budget: 0,
      savings_transfer: 0,
      savings_planned: 0,
      savings_delta: 0,
      savings_balance: 0,
      estimated_cc_bill: 50,
      real_bills: null,
      real_cc_bill: null,
      cc_usage: 5,
      budget_usage: 5,
      net: 10,
      status: "covered",
      events: [],
    });
    expect(p.estimatedCcBill).toBe(50);
  });

  it("derives bar view fields", () => {
    const p = mapPartnerToEconomy({
      partner: "X",
      partner_id: "partner_x",
      partner_slot: "a",
      salary: 100,
      bills: 10,
      planned_cc_buys: 0,
      everyday_budget: 0,
      savings_transfer: 0,
      savings_planned: 0,
      savings_delta: 5,
      savings_balance: 100,
      estimated_cc_bill: null,
      real_bills: null,
      real_cc_bill: 5,
      cc_usage: 5,
      budget_usage: 5,
      net: 50,
      status: "covered",
      events: [],
    });
    expect(p.bar).toBeDefined();
    expect(p.bar.salaryWidth).toMatch(/%$/);
    expect(p.bar.upperBarWidth).toMatch(/%$/);
    expect(p.bar.remainingTone).toBe("income");
    expect(p.bar.savingsDeltaTone).toBe("income");
  });

  it("marks status shortfall when partner net is negative", () => {
    const p = mapPartnerToEconomy({
      partner: "X",
      partner_id: "partner_x",
      partner_slot: "a",
      salary: 100,
      bills: 200,
      planned_cc_buys: 0,
      everyday_budget: 0,
      savings_transfer: 0,
      savings_planned: 0,
      savings_delta: 0,
      savings_balance: 0,
      estimated_cc_bill: null,
      real_bills: null,
      real_cc_bill: null,
      cc_usage: 0,
      budget_usage: 0,
      net: -100,
      status: "shortfall",
      events: [],
    });
    expect(p.status).toBe("shortfall");
  });
  it("maps savings_planned passthrough + label (F2 §13)", () => {
    const p = mapPartnerToEconomy({
      partner: "X",
      partner_id: "partner_x",
      partner_slot: "a",
      salary: 42_000,
      bills: 15_500,
      planned_cc_buys: 0,
      everyday_budget: 0,
      savings_transfer: 5_000,
      savings_planned: 3_000,
      savings_delta: 2_000,
      savings_balance: 32_000,
      estimated_cc_bill: null,
      real_bills: null,
      real_cc_bill: 9_800,
      cc_usage: 0,
      budget_usage: 0,
      net: 16_700,
      status: "covered",
      events: [],
    });
    expect(p.savingsPlanned).toBe(3_000);
    expect(p.savingsPlannedLabel).toBe("3,000 kr");
    // Envelope = planned / balance = 3000/32000 = 9.375%.
    expect(p.bar.savingsPlannedWidth).toBe("9.375%");
    // Fill = |delta| / balance = 2000/32000 = 6.25%.
    expect(p.bar.savingsDeltaWidth).toBe("6.25%");
    expect(p.savingsDeltaLabel).toBe("+2,000 kr");
  });

  it("handles null savings_delta (future month): fill hidden, envelope shown", () => {
    const p = mapPartnerToEconomy({
      partner: "X",
      partner_id: "partner_x",
      partner_slot: "a",
      salary: 42_000,
      bills: 15_500,
      planned_cc_buys: 0,
      everyday_budget: 0,
      savings_transfer: 5_000,
      savings_planned: 3_000,
      savings_delta: null,
      savings_balance: 32_000,
      estimated_cc_bill: 9_800,
      real_bills: null,
      real_cc_bill: null,
      cc_usage: 0,
      budget_usage: 0,
      net: 16_700,
      status: "covered",
      events: [],
    });
    // Null → 0% width, neutral tone, empty label. EconomyBar gates
    // the fill + value render on economy.savingsDelta != null.
    expect(p.savingsDelta).toBeNull();
    expect(p.bar.savingsDeltaWidth).toBe("0%");
    expect(p.bar.savingsDeltaTone).toBe("neutral");
    expect(p.savingsDeltaLabel).toBe("");
    // Envelope unaffected by null delta.
    expect(p.bar.savingsPlannedWidth).toBe("9.375%");
  });

  it("treats savings_planned 0 as 'no plan known' → empty envelope", () => {
    // Old on-disk snapshots lack savings_planned → BE defaults 0.0.
    const p = mapPartnerToEconomy({
      partner: "X",
      partner_id: "partner_x",
      partner_slot: "a",
      salary: 42_000,
      bills: 15_500,
      planned_cc_buys: 0,
      everyday_budget: 0,
      savings_transfer: 5_000,
      savings_planned: 0,
      savings_delta: 2_000,
      savings_balance: 32_000,
      estimated_cc_bill: null,
      real_bills: null,
      real_cc_bill: 9_800,
      cc_usage: 0,
      budget_usage: 0,
      net: 16_700,
      status: "covered",
      events: [],
    });
    expect(p.bar.savingsPlannedWidth).toBe("0%");
    expect(p.savingsPlannedLabel).toBe("0 kr");
  });

  it("passes cc_usage_by_category through as ccUsageByCategory (F2 grid R3)", () => {
    // Per-category-title real CC spend feeds the BudgetTab free-budget
    // section. Verbatim passthrough — no key/case transforms.
    const p = mapPartnerToEconomy({
      partner: "X",
      partner_id: "partner_x",
      partner_slot: "a",
      salary: 42_000,
      bills: 15_500,
      planned_cc_buys: 0,
      everyday_budget: 8_200,
      savings_transfer: 5_000,
      savings_planned: 3_000,
      savings_delta: 2_000,
      savings_balance: 32_000,
      estimated_cc_bill: null,
      real_cc_bill: 9_800,
      real_bills: 15_500,
      cc_usage: 4_200,
      cc_usage_by_category: { Groceries: 2_500, Dining: 1_700 },
      budget_usage: 4_200,
      net: 16_700,
      status: "covered",
      events: [],
    });
    expect(p.ccUsageByCategory).toEqual({ Groceries: 2_500, Dining: 1_700 });
  });

  it("maps missing cc_usage_by_category (stale snapshot) to null", () => {
    const p = mapPartnerToEconomy({
      partner: "X",
      partner_id: "partner_x",
      partner_slot: "a",
      salary: 42_000,
      bills: 15_500,
      planned_cc_buys: 0,
      everyday_budget: 8_200,
      savings_transfer: 5_000,
      savings_planned: 3_000,
      savings_delta: 2_000,
      savings_balance: 32_000,
      estimated_cc_bill: null,
      real_cc_bill: 9_800,
      real_bills: 15_500,
      cc_usage: 4_200,
      // cc_usage_by_category omitted — pre-field snapshot on disk.
      budget_usage: 4_200,
      net: 16_700,
      status: "covered",
      events: [],
    });
    expect(p.ccUsageByCategory).toBeNull();
  });
});

describe("US2 partner identity (T049)", () => {
  // LG-007 regression: label is display-only text. Renaming a partner's
  // label must not move events or change any grouping/total — attribution
  // is keyed on partner_id.
  it("renaming a label keeps partner_id attribution and totals identical", () => {
    const snapTwo = (labelA: string, labelB: string): BillsSnapshot =>
      makeSnapshot({
        partners: [
          {
            partner: labelA,
            partner_id: "partner_a",
            partner_slot: "a",
            salary: 100,
            bills: 40,
            planned_cc_buys: 10,
            everyday_budget: 20,
            savings_transfer: 5,
            savings_planned: 5,
            savings_delta: 0,
            savings_balance: 50,
            estimated_cc_bill: 0,
            real_cc_bill: 0,
            real_bills: 40,
            cc_usage: 10,
            budget_usage: 10,
            net: 25,
            status: "covered",
            events: [
              {
                id: "a1",
                date: "2026-07-02",
                day: 2,
                title: "Salary",
                type: "salary",
                account: "Income",
                partner: labelA,
                partner_id: "partner_a",
                partner_slot: "a",
                amount: 100,
                is_cc_payment: false,
                is_matched: null,
              },
            ],
          },
          {
            partner: labelB,
            partner_id: "partner_b",
            partner_slot: "b",
            salary: 200,
            bills: 60,
            planned_cc_buys: 0,
            everyday_budget: 30,
            savings_transfer: 0,
            savings_planned: 0,
            savings_delta: 10,
            savings_balance: 80,
            estimated_cc_bill: 0,
            real_cc_bill: 0,
            real_bills: 60,
            cc_usage: 0,
            budget_usage: 0,
            net: 100,
            status: "covered",
            events: [
              {
                id: "b1",
                date: "2026-07-03",
                day: 3,
                title: "Rent",
                type: "bill",
                account: "Example Joint",
                partner: labelB,
                partner_id: "partner_b",
                partner_slot: "b",
                amount: -60,
                is_cc_payment: false,
                is_matched: null,
              },
            ],
          },
        ],
      });

    const before = mapSnapshotToMonthData(snapTwo("Fixture A", "Fixture B"));
    const after = mapSnapshotToMonthData(snapTwo("Label One", "Label Two"));

    // Ids survive the rename; labels changed.
    expect(after.partners.map((p) => p.partner.partner_id)).toEqual(
      before.partners.map((p) => p.partner.partner_id),
    );
    expect(after.events.map((e) => e.partner.partner_id)).toEqual(
      before.events.map((e) => e.partner.partner_id),
    );
    expect(after.partners.map((p) => p.partner.label)).toEqual([
      "Label One",
      "Label Two",
    ]);

    // Every non-identity field byte-identical — same grouping, same totals.
    const stripIdentity = (m: ReturnType<typeof mapSnapshotToMonthData>) => ({
      ...m,
      partners: m.partners.map(({ partner: _partner, ...rest }) => rest),
      events: m.events.map(({ partner: _partner, ...rest }) => rest),
    });
    expect(stripIdentity(after)).toEqual(stripIdentity(before));
  });

  // Schema-4 file on disk: no partner_id/partner_slot fields. Mapper must
  // default to the identity-neutral triple, never infer from position.
  it("schema-4 snapshot maps to the identity-neutral triple", () => {
    const legacy = JSON.parse(JSON.stringify(makeSnapshot())) as Record<
      string,
      unknown
    >;
    for (const p of legacy.partners as Record<string, unknown>[]) {
      delete p.partner_id;
      delete p.partner_slot;
      for (const e of p.events as Record<string, unknown>[]) {
        delete e.partner_id;
        delete e.partner_slot;
      }
    }
    const m = mapSnapshotToMonthData(legacy as unknown as BillsSnapshot);
    expect(m.partners[0].partner).toEqual({
      partner_id: "",
      partner_slot: "",
      label: "Fixture A",
    });
    expect(m.events[0].partner).toEqual({
      partner_id: "",
      partner_slot: "",
      label: "Fixture A",
    });
  });
});
