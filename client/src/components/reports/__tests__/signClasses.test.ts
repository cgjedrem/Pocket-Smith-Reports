// PR3 (monthly-reports-logic-migration) — sign-class enum lookup + local
// fallback classifier. SIGN_CLASS must round-trip every SignClass value
// unchanged (it's an identity lookup to CSS class names); signOf() must
// mirror the backend's accounting.py::_sign_class exactly (-0 counts as
// zero, this is the one field — kpis.*.net_cash — with no server `_class`).

import { describe, expect, it } from "vitest";

import { SIGN_CLASS, signOf } from "@/components/reports/signClasses";
import type { SignClass } from "@/types/report";

describe("SIGN_CLASS", () => {
  it("maps every sign enum to its expected CSS class", () => {
    const cases: Array<[SignClass, string]> = [
      ["pos", "pos"],
      ["neg", "neg"],
      ["zero", "zero"],
    ];
    for (const [signClass, expected] of cases) {
      expect(SIGN_CLASS[signClass]).toBe(expected);
    }
  });
});

describe("signOf", () => {
  it("classifies positive numbers as pos", () => {
    expect(signOf(1)).toBe("pos");
    expect(signOf(0.01)).toBe("pos");
  });

  it("classifies negative numbers as neg", () => {
    expect(signOf(-1)).toBe("neg");
    expect(signOf(-0.01)).toBe("neg");
  });

  it("classifies 0 and -0 as zero", () => {
    expect(signOf(0)).toBe("zero");
    expect(signOf(-0)).toBe("zero");
  });
});
