// Privacy store tests — contracts/privacy-store.md §1.
// Invariants I-1..I-4 + maskAmount rules. Module singleton is reset between
// tests via setAmountsHidden(false); init tests re-import a fresh module.

import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  formatKr,
  formatSignedKr,
} from "@/components/bills/finance-data";
import {
  compactNOK,
  formatNOK,
} from "@/components/mega-reports/sections/helpers";
import {
  AMOUNT_MASK,
  isAmountsHidden,
  maskAmount,
  setAmountsHidden,
  subscribe,
  toggleAmountsHidden,
} from "@/lib/privacy-store";

beforeEach(() => {
  localStorage.clear();
  setAmountsHidden(false);
});

describe("maskAmount", () => {
  it("passes through when visible", () => {
    expect(maskAmount("12,340 kr")).toBe("12,340 kr");
    expect(maskAmount("+2,000 kr")).toBe("+2,000 kr");
    expect(maskAmount("-1,500 kr")).toBe("-1,500 kr");
    expect(maskAmount("0 kr")).toBe("0 kr");
  });

  it('returns "****" when hidden — sign never leaks, zero is masked', () => {
    setAmountsHidden(true);
    expect(maskAmount("12,340 kr")).toBe(AMOUNT_MASK);
    expect(maskAmount("+2,000 kr")).toBe(AMOUNT_MASK);
    expect(maskAmount("-1,500 kr")).toBe(AMOUNT_MASK);
    expect(maskAmount("0 kr")).toBe(AMOUNT_MASK);
  });

  it('keeps "" empty in both states — absence never becomes a mask', () => {
    expect(maskAmount("")).toBe("");
    setAmountsHidden(true);
    expect(maskAmount("")).toBe("");
  });
});

// Coverage: contracts/privacy-store.md §3 — shared formatters mask at the
// last mile so every bills dashboard + mega report label is covered.
describe("formatter masking", () => {
  it("formatKr returns normal output when visible", () => {
    expect(formatKr(12340)).toBe(formatKr(12340));
    expect(formatKr(12340)).toContain("12,340");
    expect(formatKr(-1500)).toContain("-1,500");
  });

  it('formatKr returns "****" when hidden — negative, positive, zero', () => {
    setAmountsHidden(true);
    expect(formatKr(12340)).toBe(AMOUNT_MASK);
    expect(formatKr(-1500)).toBe(AMOUNT_MASK);
    expect(formatKr(0)).toBe(AMOUNT_MASK);
  });

  it("formatSignedKr masks signed-positive, negative, and zero when hidden", () => {
    setAmountsHidden(true);
    expect(formatSignedKr(2000)).toBe(AMOUNT_MASK);
    expect(formatSignedKr(-1500)).toBe(AMOUNT_MASK);
    expect(formatSignedKr(0)).toBe(AMOUNT_MASK);
  });

  it("formatSignedKr keeps the sign when visible", () => {
    expect(formatSignedKr(2000)).toMatch(/^\+/);
    expect(formatSignedKr(-1500)).toMatch(/^-/);
  });

  it('formatNOK returns "****" when hidden, nb-NO figure when visible', () => {
    const visible = formatNOK(12340.5);
    expect(visible).not.toBe(AMOUNT_MASK);
    setAmountsHidden(true);
    expect(formatNOK(12340.5)).toBe(AMOUNT_MASK);
    expect(formatNOK(-42)).toBe(AMOUNT_MASK);
    expect(formatNOK(0)).toBe(AMOUNT_MASK);
  });

  // Chart axes (contracts §3): compactNOK masks like every other amount.
  it('compactNOK returns "****" when hidden, M/k/int output when visible', () => {
    expect(compactNOK(1_000_000)).toBe("1.0M");
    expect(compactNOK(250_000)).toBe("250k");
    expect(compactNOK(999)).toBe("999");
    setAmountsHidden(true);
    expect(compactNOK(1_000_000)).toBe(AMOUNT_MASK);
    expect(compactNOK(250_000)).toBe(AMOUNT_MASK);
    expect(compactNOK(-250_000)).toBe(AMOUNT_MASK);
    expect(compactNOK(0)).toBe(AMOUNT_MASK);
  });
});

describe("store invariants", () => {
  it("starts visible by default", () => {
    expect(isAmountsHidden()).toBe(false);
  });

  it("toggleAmountsHidden flips and notifies each subscriber exactly once", () => {
    const a = vi.fn();
    const b = vi.fn();
    const unsubA = subscribe(a);
    const unsubB = subscribe(b);

    toggleAmountsHidden();
    expect(isAmountsHidden()).toBe(true);
    expect(a).toHaveBeenCalledTimes(1);
    expect(b).toHaveBeenCalledTimes(1);

    toggleAmountsHidden();
    expect(isAmountsHidden()).toBe(false);
    expect(a).toHaveBeenCalledTimes(2);
    expect(b).toHaveBeenCalledTimes(2);

    unsubA();
    unsubB();
  });

  it("setAmountsHidden notifies subscribers exactly once", () => {
    const listener = vi.fn();
    const unsub = subscribe(listener);
    setAmountsHidden(true);
    expect(isAmountsHidden()).toBe(true);
    expect(listener).toHaveBeenCalledTimes(1);
    unsub();
  });

  it("unsubscribed listeners stop receiving notifications", () => {
    const listener = vi.fn();
    const unsub = subscribe(listener);
    unsub();
    toggleAmountsHidden();
    expect(listener).not.toHaveBeenCalled();
  });

  // I-1: same value across calls until a mutation (useSyncExternalStore-safe).
  it("isAmountsHidden() is stable between mutations", () => {
    const first = isAmountsHidden();
    const second = isAmountsHidden();
    expect(first).toBe(second);
    toggleAmountsHidden();
    expect(isAmountsHidden()).toBe(!first);
  });

  // I-3: mutation writes localStorage BEFORE notifying subscribers.
  it('writes localStorage["psr:hide-amounts"]="1" before notifying', () => {
    let observedAtNotify: string | null = null;
    const unsub = subscribe(() => {
      observedAtNotify = localStorage.getItem("psr:hide-amounts");
    });
    setAmountsHidden(true);
    expect(localStorage.getItem("psr:hide-amounts")).toBe("1");
    expect(observedAtNotify).toBe("1");
    setAmountsHidden(false);
    expect(localStorage.getItem("psr:hide-amounts")).toBe("0");
    unsub();
  });

  // I-2: fresh module init reads the persisted flag.
  it.each([
    ["1", true],
    ["0", false],
    ["garbage", false],
  ])('fresh init with stored "%s" starts hidden=%s', async (stored, expected) => {
    localStorage.setItem("psr:hide-amounts", stored);
    vi.resetModules();
    const fresh = await import("@/lib/privacy-store");
    expect(fresh.isAmountsHidden()).toBe(expected);
    vi.resetModules();
  });

  it("fresh init with nothing stored starts visible", async () => {
    vi.resetModules();
    const fresh = await import("@/lib/privacy-store");
    expect(fresh.isAmountsHidden()).toBe(false);
    vi.resetModules();
  });

  // I-2: init never throws when localStorage is unavailable.
  it("init throws nothing when localStorage is unavailable", async () => {
    vi.resetModules();
    const original = window.localStorage;
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      get() {
        throw new Error("storage disabled");
      },
    });
    try {
      const fresh = await import("@/lib/privacy-store");
      expect(() => fresh.isAmountsHidden()).not.toThrow();
      expect(fresh.isAmountsHidden()).toBe(false);
      expect(() => fresh.toggleAmountsHidden()).not.toThrow();
    } finally {
      Object.defineProperty(window, "localStorage", {
        configurable: true,
        value: original,
      });
      vi.resetModules();
    }
  });
});
