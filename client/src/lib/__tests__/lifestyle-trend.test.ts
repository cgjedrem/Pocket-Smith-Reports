import { describe, expect, it } from "vitest";
import { lifestyleTrend, parseExactDecimal, type LifestyleTrendPoint } from "../lifestyle-trend";
import { lifestyleEvidenceMonths } from "../lifestyle-creep";

function trend(entries: Array<[string, string]>, target = entries.at(-1)![0]) {
  const result = lifestyleTrend(entries.map(([month, amount]) => ({ month, amount })), { month: target });
  if (result.status !== "ready") throw new Error(result.reason);
  return result;
}
function summary(points: LifestyleTrendPoint[]) {
  return points.map((point) => [point.month, point.trailingAverage, point.isAboveTrailingAverage]);
}

describe("lifestyleTrend trailing average", () => {
  it("uses up to three preceding months, excludes the current month and starts after two", () => {
    const result = trend([["2026-07", "100"], ["2026-08", "100"], ["2026-09", "130"], ["2026-10", "140"]]);
    expect(summary(result.points)).toEqual([
      ["2026-07", null, false],
      ["2026-08", null, false],
      ["2026-09", "100", true],
      ["2026-10", "110", true],
    ]);
    expect(result.points.map((point) => point.priorMonths)).toEqual([
      [], [], ["2026-07", "2026-08"], ["2026-07", "2026-08", "2026-09"],
    ]);
    expect(result.points.map((point) => point.average)).toEqual([null, null, 100, 110]);
    expect(result.points.at(-1)!.isTarget).toBe(true);
    expect(result.points.filter((point) => point.isTarget)).toHaveLength(1);
    expect(result.rows.every((row) => row.kind === "sample")).toBe(true);
    expect(result.plottable).toBe(true);
  });

  it("marks only strictly greater usage; equality is not above", () => {
    const result = trend([["2026-07", "100"], ["2026-08", "100.00"], ["2026-09", "100.000"], ["2026-10", "99.99"]]);
    expect(summary(result.points).map((row) => row[2])).toEqual([false, false, false, false]);
    expect(result.points[2].trailingAverage).toBe("100");
  });

  it("compares exactly instead of with the rounded display average", () => {
    const result = trend([["2026-01", "100"], ["2026-02", "100"], ["2026-03", "101"], ["2026-04", "100.3333334"], ["2026-05", "100.33333333"]], "2026-05");
    expect(result.points[3].trailingAverage).toBe("100.333333");
    expect(result.points[3].isAboveTrailingAverage).toBe(true);
    // Prior 100, 101, 100.3333334: exact mean 100.4444444666…
    expect(result.points[4].isAboveTrailingAverage).toBe(false);
  });

  it("supports the two-reference minimum: only the target can get an average", () => {
    const months = lifestyleEvidenceMonths("2026-08", "2026-09", "2026-10");
    const result = trend(months.map((month, index) => [month, String([50, 70, 61][index])]));
    expect(summary(result.points)).toEqual([["2026-08", null, false], ["2026-09", null, false], ["2026-10", "60", true]]);
  });

  it("supports 24 references plus target with a three-month window throughout", () => {
    const months = lifestyleEvidenceMonths("2024-10", "2026-09", "2026-10");
    expect(months).toHaveLength(25);
    const result = trend(months.map((month, index) => [month, String(index * 10)]));
    expect(result.points.filter((point) => point.trailingAverage !== null)).toHaveLength(23);
    expect(result.points.slice(3).every((point) => point.priorMonths.length === 3)).toBe(true);
    expect(result.points.at(-1)!.priorMonths).toEqual(["2026-07", "2026-08", "2026-09"]);
    expect(result.points.at(-1)!.trailingAverage).toBe("220");
    expect(result.points.slice(2).every((point) => point.isAboveTrailingAverage)).toBe(true);
  });

  it("breaks the series at an unselected gap and never averages across it", () => {
    const result = trend([["2026-01", "10"], ["2026-02", "10"], ["2026-03", "10"], ["2026-06", "999"]]);
    expect(result.rows.map((row) => row.key)).toEqual(["2026-01", "2026-02", "2026-03", "gap:2026-03:2026-06", "2026-06"]);
    const gap = result.rows[3];
    expect(gap).toMatchObject({ kind: "gap", missingMonths: 2, usage: null, average: null, afterMonth: "2026-03", beforeMonth: "2026-06" });
    const target = result.points.at(-1)!;
    expect(target).toMatchObject({ month: "2026-06", isTarget: true, trailingAverage: null, average: null, isAboveTrailingAverage: false, priorMonths: [] });
    expect(result.points[2].trailingAverage).toBe("10");
  });

  it("does not treat the last observed nonconsecutive months as consecutive", () => {
    const result = trend([["2026-01", "10"], ["2026-02", "10"], ["2026-03", "10"], ["2026-05", "40"]]);
    expect(result.rows.find((row) => row.kind === "gap")).toMatchObject({ missingMonths: 1 });
    expect(result.points.at(-1)!.trailingAverage).toBeNull();
  });

  it("rolls over month and year boundaries", () => {
    const result = trend([["2026-11", "10"], ["2026-12", "20"], ["2027-01", "30"], ["2027-02", "21"]], "2027-02");
    expect(result.rows.every((row) => row.kind === "sample")).toBe(true);
    expect(result.points.at(-1)!.priorMonths).toEqual(["2026-11", "2026-12", "2027-01"]);
    expect(result.points.at(-1)!.trailingAverage).toBe("20");
    expect(result.points.at(-1)!.isAboveTrailingAverage).toBe(true);
    expect(result.points[2].isAboveTrailingAverage).toBe(true);
  });

  it("orders unsorted samples chronologically", () => {
    const result = trend([["2026-09", "30"], ["2026-07", "10"], ["2026-08", "20"]], "2026-09");
    expect(result.points.map((point) => point.month)).toEqual(["2026-07", "2026-08", "2026-09"]);
  });

  it("handles zero and negative net usage strictly", () => {
    const negative = trend([["2026-07", "-50"], ["2026-08", "0"], ["2026-09", "-10"], ["2026-10", "-20"]]);
    expect(summary(negative.points)).toEqual([
      ["2026-07", null, false], ["2026-08", null, false], ["2026-09", "-25", true], ["2026-10", "-20", false],
    ]);
    expect(negative.points.map((point) => point.usage)).toEqual([-50, 0, -10, -20]);
    const zero = trend([["2026-07", "0"], ["2026-08", "-0"], ["2026-09", "0.00"]]);
    expect(zero.points[2]).toMatchObject({ trailingAverage: "0", isAboveTrailingAverage: false, average: 0 });
  });

  it("keeps exact markers for huge/precise values but refuses to plot lossy numbers", () => {
    const huge = trend([["2026-07", "90071992547409920"], ["2026-08", "90071992547409920"], ["2026-09", "90071992547409921"]]);
    expect(huge.points[2].isAboveTrailingAverage).toBe(true);
    expect(huge.points[2].trailingAverage).toBe("90071992547409920");
    expect(huge.plottable).toBe(false);
    expect(huge.points[0].usage).toBeNull();
    const tiny = trend([["2026-07", "1e-400"], ["2026-08", "0"], ["2026-09", "0"]]);
    expect(tiny.plottable).toBe(false);
    expect(tiny.points[0].usage).toBeNull();
    expect(tiny.points[2].isAboveTrailingAverage).toBe(false);
    const ok = trend([["2026-07", "12345.67"], ["2026-08", "1E+3"], ["2026-09", "0.5"]]);
    expect(ok.plottable).toBe(true);
    expect(ok.points.map((point) => point.usage)).toEqual([12345.67, 1000, 0.5]);
    expect(ok.points[2].trailingAverage).toBe("6672.835");
  });

  it("rejects coordinates whose decimal round trip loses distinguishing digits", () => {
    const result = trend([
      ["2026-07", "100.000"],
      ["2026-08", "100"],
      ["2026-09", "100.00000000000000000001"],
    ]);
    expect(result.points[2].isAboveTrailingAverage).toBe(true);
    expect(result.points[2].usage).toBeNull();
    expect(result.plottable).toBe(false);
    expect(trend([
      ["2026-07", "100.000"],
      ["2026-08", "100"],
      ["2026-09", "100.00"],
    ]).plottable).toBe(true);
  });

  it.each(["abc", "Infinity", "NaN", "", "1,5", "--1"])("fails visibly on invalid amount %j", (amount) => {
    const result = lifestyleTrend([{ month: "2026-07", amount }], { month: "2026-07" });
    expect(result).toEqual({ status: "invalid", reason: "The 2026-07 amount is not an exact decimal." });
  });

  it("rejects duplicate and non-calendar months", () => {
    expect(lifestyleTrend([{ month: "2026-07", amount: "1" }, { month: "2026-07", amount: "2" }], { month: "2026-07" }).status).toBe("invalid");
    expect(lifestyleTrend([{ month: "2026-13", amount: "1" }], { month: "2026-13" }).status).toBe("invalid");
  });

  it("parses exact decimals without binary rounding", () => {
    expect(parseExactDecimal("-12.340")).toEqual({ units: -12340n, scale: 3 });
    expect(parseExactDecimal("1E+3")).toEqual({ units: 1000n, scale: 0 });
    expect(parseExactDecimal("Infinity")).toBeNull();
  });
});
