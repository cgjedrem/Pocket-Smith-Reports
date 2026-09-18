// Tests for identity-neutral logic fix: empty list should not show hint
// (vacuous every trap), only when there's at least one row AND all are neutral.

import { describe, expect, it } from "vitest";
import { isIdentityNeutral } from "@/components/bills/finance-data";

interface MockRow {
  partner: { partner_id: string };
}

describe("isIdentityNeutral", () => {
  it("returns false for empty list (no hint when no data)", () => {
    const rows: MockRow[] = [];
    expect(isIdentityNeutral(rows)).toBe(false);
  });

  it("returns true when all rows have empty partner_id (legacy/neutral)", () => {
    const rows: MockRow[] = [
      { partner: { partner_id: "" } },
      { partner: { partner_id: "" } },
      { partner: { partner_id: "" } },
    ];
    expect(isIdentityNeutral(rows)).toBe(true);
  });

  it("returns false when at least one row has non-empty partner_id", () => {
    const rows: MockRow[] = [
      { partner: { partner_id: "" } },
      { partner: { partner_id: "partner_a" } },
      { partner: { partner_id: "" } },
    ];
    expect(isIdentityNeutral(rows)).toBe(false);
  });

  it("returns false when all rows have non-empty partner_id", () => {
    const rows: MockRow[] = [
      { partner: { partner_id: "partner_a" } },
      { partner: { partner_id: "partner_b" } },
    ];
    expect(isIdentityNeutral(rows)).toBe(false);
  });

  it("returns true for single neutral row", () => {
    const rows: MockRow[] = [{ partner: { partner_id: "" } }];
    expect(isIdentityNeutral(rows)).toBe(true);
  });

  it("returns false for single identified row", () => {
    const rows: MockRow[] = [{ partner: { partner_id: "partner_a" } }];
    expect(isIdentityNeutral(rows)).toBe(false);
  });
});
