import { beforeEach, describe, expect, it } from "vitest";
import {
  canonicalThreshold, validLifestyleMonth, lifestyleSelectionError, lifestyleEvidenceMonths,
  lifestyleReferenceMonths, shiftLifestyleMonth, defaultLifestyleSelection,
  formatLifestyleMoney, formatLifestylePercent,
} from "../lifestyle-creep";
import { setAmountsHidden } from "../privacy-store";

beforeEach(() => setAmountsHidden(false));

describe("exact threshold text", () => {
  it.each([
    ["1", "1"], ["20", "20"], ["20.5", "20.5"], ["30", "30"], ["100", "100"],
    ["+020.50", "20.5"], ["2e1", "20"], [".2E+2", "20"], ["100.", "100"],
    ["100000e-3", "100"], ["1.00000000000000001", "1.00000000000000001"],
    ["99.99999999999999999", "99.99999999999999999"],
    ["000000100.00000000", "100"], ["010e0000000", "10"],
  ])("canonicalizes %s without rounding", (raw, expected) => {
    expect(canonicalThreshold(raw)).toBe(expected);
  });

  it.each([
    "", " ", " 20", "20 ", "true", "false", "null", "NaN", "Infinity", "-Infinity",
    "0", "-0", "-20", "0.99999999999999999", "100.00000000000000001", "101",
    "1e99999999999999999999999", "1e-99999999999999999999999", "0e1000000",
    "1_0", "20,5", "0x20", ".", "+", "20\n", "２0", "1e", "1e--1",
  ])("rejects %j without defaulting or clamping", (raw) => {
    expect(canonicalThreshold(raw)).toBeNull();
  });
});

describe("detector calendar", () => {
  it("defaults to latest completed target and preceding three references across year boundaries", () => {
    expect(defaultLifestyleSelection("2027-01")).toEqual({
      target: "2026-12", referenceStart: "2026-09", referenceEnd: "2026-11",
    });
    expect(defaultLifestyleSelection("2027-02")).toEqual({
      target: "2027-01", referenceStart: "2026-10", referenceEnd: "2026-12",
    });
    expect(lifestyleReferenceMonths("2026-05", "2026-10")).toEqual([
      "2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10",
    ]);
    expect(lifestyleEvidenceMonths("2026-05", "2026-06", "2026-10")).toEqual([
      "2026-05", "2026-06", "2026-10",
    ]);
    expect(lifestyleEvidenceMonths("0001-01", "0001-02", "0001-03")).toEqual([
      "0001-01", "0001-02", "0001-03",
    ]);
    expect(shiftLifestyleMonth("0001-04", 1)).toBe("0001-05");
    expect(shiftLifestyleMonth("2026-12", 1)).toBe("2027-01");
    expect(shiftLifestyleMonth("9999-12", 1)).toBe("");
    expect(shiftLifestyleMonth("0001-01", -1)).toBe("");
  });
  it.each([
    ["2026-10", "2026-07", "2026-09"],
    ["2026-10", "2025-11", "2026-09"],
    ["0001-03", "0001-01", "0001-02"],
    ["2026-10", "2026-08", "2026-09"],
    ["2026-10", "2024-10", "2026-09"],
  ])("accepts target %s with references %s through %s", (target, start, end) => {
    expect(lifestyleSelectionError(target, start, end, "2026-11")).toBeNull();
  });
  it.each([
    ["", "2026-07", "2026-09"], ["2026-10", "", "2026-09"], ["2026-10", "2026-09", ""],
    ["2026-10", "2026-09", "2026-08"], ["2026-10", "2026-08", "2026-10"],
    ["2026-10", "2026-09", "2026-09"], ["2026-10", "2024-09", "2026-09"],
    ["0001-02", "0001-01", "0001-02"], ["2026-11", "2026-07", "2026-09"],
    ["2026-10\n", "2026-07", "2026-09"], ["2026-10", "2026-00", "2026-09"],
  ])("rejects invalid target/reference selection %j %j %j", (target, start, end) => {
    expect(lifestyleSelectionError(target, start, end, "2026-10")).not.toBeNull();
  });
  it("counts the inclusive reference range and rejects one or twenty-five months", () => {
    expect(lifestyleReferenceMonths("2026-08", "2026-09")).toHaveLength(2);
    expect(lifestyleReferenceMonths("2024-10", "2026-09")).toHaveLength(24);
    expect(lifestyleReferenceMonths("2024-09", "2026-09")).toEqual([]);
    expect(lifestyleSelectionError("2026-10", "2026-09", "2026-09", "2026-11"))
      .toMatch(/at least 2 consecutive/);
    expect(lifestyleSelectionError("2026-10", "2024-09", "2026-09", "2026-11"))
      .toMatch(/at most 24 consecutive/);
  });
  it("accepts only completed target months with enough calendar history", () => {
    expect(validLifestyleMonth("2026-09", "2026-10")).toBe(true);
    expect(validLifestyleMonth("2026-10", "2026-10")).toBe(false);
    expect(validLifestyleMonth("2027-01", "2027-02")).toBe(true);
  });
  it.each(["", "2026-11", "2026-00", "2026-13", "2026-1", "0000-10", "0001-02", "2026-10\n"])("rejects invalid target month %j", (raw) => {
    expect(validLifestyleMonth(raw, "2026-10")).toBe(false);
  });
});

describe("presentation boundary", () => {
  it("preserves signed/zero conventions and undefined versus zero percentages", () => {
    expect(formatLifestyleMoney("30", true)).toBe("+30 kr");
    expect(formatLifestyleMoney("-30", true)).toBe("-30 kr");
    expect(formatLifestyleMoney("-30")).toBe("-30 kr");
    expect(formatLifestyleMoney("-1234.25")).toBe("-1,234 kr");
    expect(formatLifestyleMoney("0", true)).toBe("0 kr");
    expect(formatLifestylePercent("0", "zero baseline")).toBe("0%");
    expect(formatLifestylePercent(null, "zero baseline")).toBe("Not calculable — zero baseline");
    expect(formatLifestylePercent("-20.555", "")).toBe("-20.56%");
  });
  it("uses finite decimal text for overflow, with full privacy masking", () => {
    const huge = `1${"0".repeat(310)}`;
    expect(formatLifestyleMoney(huge)).toMatch(/^10,000,/);
    expect(formatLifestyleMoney(huge, true)).toMatch(/^\+10,000,/);
    expect(formatLifestyleMoney(`-${huge}`, true)).toMatch(/^-10,000,/);
    expect(formatLifestyleMoney(huge)).not.toMatch(/Infinity|NaN/);
    expect(formatLifestylePercent(huge, "")).toBe(`${huge}%`);
    setAmountsHidden(true);
    for (const value of [huge, `-${huge}`, "0", "-43", "140"]) {
      expect(formatLifestyleMoney(value, true)).toBe("****");
      expect(formatLifestyleMoney(value)).toBe("****");
    }
    expect(formatLifestylePercent("27.27272727", "")).toBe("27.27%");
  });
});
