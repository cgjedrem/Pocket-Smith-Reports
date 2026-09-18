// Tests for identity-neutral hint logic and partner_slot "" styling robustness.
// Covers: slot-"" styling with partnerDotClass function, sorting with byDisplayOrder.

import { describe, expect, it } from "vitest";

import { partnerDotClass, byDisplayOrder } from "@/components/bills/finance-data";
import type { F2PartnerIdentity } from "@/types/api";

describe("partnerDotClass — slot-'' robustness", () => {
  it("returns neutral gray for empty slot ('')", () => {
    const result = partnerDotClass("");
    expect(result).toBe("bg-muted-foreground");
  });

  it("returns teal for slot 'a'", () => {
    const result = partnerDotClass("a");
    expect(result).toBe("bg-partner-a");
  });

  it("returns violet for slot 'b'", () => {
    const result = partnerDotClass("b");
    expect(result).toBe("bg-partner-b");
  });

  it("returns neutral gray for undefined slot", () => {
    const result = partnerDotClass(undefined);
    expect(result).toBe("bg-muted-foreground");
  });
});

describe("byDisplayOrder — slot-'' sorting", () => {
  it("sorts slot-'' rows after a and b slots", () => {
    interface MockRow {
      partner: F2PartnerIdentity;
    }

    const rows: MockRow[] = [
      { partner: { partner_id: "partner_b", partner_slot: "b", label: "Fixture B" } },
      { partner: { partner_id: "partner_c", partner_slot: "", label: "Third Partner" } },
      { partner: { partner_id: "partner_a", partner_slot: "a", label: "Fixture A" } },
    ];

    const sorted = byDisplayOrder(rows);

    expect(sorted[0].partner.label).toBe("Fixture A");
    expect(sorted[1].partner.label).toBe("Fixture B");
    expect(sorted[2].partner.label).toBe("Third Partner");
  });

  it("handles all empty slots correctly", () => {
    interface MockRow {
      partner: F2PartnerIdentity;
    }

    const rows: MockRow[] = [
      { partner: { partner_id: "", partner_slot: "", label: "Zebra" } },
      { partner: { partner_id: "", partner_slot: "", label: "Alice" } },
      { partner: { partner_id: "", partner_slot: "", label: "Bob" } },
    ];

    const sorted = byDisplayOrder(rows);

    // When all slots are "", sort by label alphabetically
    expect(sorted[0].partner.label).toBe("Alice");
    expect(sorted[1].partner.label).toBe("Bob");
    expect(sorted[2].partner.label).toBe("Zebra");
  });

  it("handles mixed identified and unidentified slots", () => {
    interface MockRow {
      partner: F2PartnerIdentity;
    }

    const rows: MockRow[] = [
      { partner: { partner_id: "", partner_slot: "", label: "Unknown" } },
      { partner: { partner_id: "partner_b", partner_slot: "b", label: "Fixture B" } },
      { partner: { partner_id: "partner_a", partner_slot: "a", label: "Fixture A" } },
    ];

    const sorted = byDisplayOrder(rows);

    expect(sorted[0].partner.partner_id).toBe("partner_a");
    expect(sorted[1].partner.partner_id).toBe("partner_b");
    expect(sorted[2].partner.partner_slot).toBe("");
  });
});
