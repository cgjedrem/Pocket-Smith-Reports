// Shared nav tree builder for mega report — used by MegaReportNav + export dialog.
// Mirrors section structure: 13 top-level sections, dynamic sub-items for
// Common, Personal A/B, Trips, CC Paydowns, Appendices.
// Personal titles resolve from report.partner_labels — no hardcoded names.

import { partnerLabel, slugify } from "@/components/mega-reports/sections/helpers";
import type { MegaReportResponse } from "@/types/mega_report";

export interface NavSubItem {
  id: string;
  title: string;
}

export interface NavItem {
  id: string;
  number: string | number;
  title: string;
  children?: NavSubItem[];
}

// Static top-level nav structure. Personal titles need the report for
// partner_labels, so pass it in.
function buildStaticItems(report: MegaReportResponse): NavItem[] {
  return [
    {
      id: "kpi",
      number: 1,
      title: "KPIs",
      children: [{ id: "salary-allocation", title: "Salary allocation" }],
    },
    { id: "income", number: 2, title: "Income" },
    {
      id: "savings",
      number: 3,
      title: "Savings",
      children: [{ id: "investment-net-per-month", title: "Investment net" }],
    },
    { id: "home", number: 4, title: "Home" },
    { id: "common", number: 5, title: "Common" },
    {
      id: "personal-partner-a",
      number: 6,
      title: `Personal ${partnerLabel(report, "partner_a")}`,
    },
    {
      id: "personal-partner-b",
      number: 7,
      title: `Personal ${partnerLabel(report, "partner_b")}`,
    },
    {
      id: "trips",
      number: 8,
      title: "Trips",
      children: [
        { id: "trips-common-overview", title: "Common-only overview" },
        { id: "trips-by-partner", title: "Trips by partner" },
        { id: "trips-by-subcategory", title: "By sub-category (per trip)" },
      ],
    },
    { id: "recommendations", number: 9, title: "Recommendations" },
    { id: "monthlies", number: 10, title: "Monthly KPI" },
    {
      id: "cc-paydowns",
      number: 11,
      title: "CC paydowns",
      children: [
        { id: "cc-paydowns-by-card", title: "By card with cumulative" },
        { id: "cc-paydowns-per-month", title: "Per month (per card)" },
      ],
    },
    { id: "excluded", number: 12, title: "Excluded" },
    { id: "appendices", number: 13, title: "Appendices" },
  ];
}

// Build per-section subcat nav items for the Appendices section.
function buildAppendixSubItems(report: MegaReportResponse): NavSubItem[] {
  const appendix = report.appendix_transactions;
  if (!appendix) return [];
  const allTxns = Object.values(appendix).flat();
  const SECTION_ORDER = [
    "income",
    "savings",
    "home",
    "common",
    "personal_partner_a",
    "personal_partner_b",
    "trips",
  ] as const;

  const allFlat: NavSubItem[] = [];
  for (const sec of SECTION_ORDER) {
    const secTxns = allTxns.filter((t) => t._detailed_section === sec);
    if (secTxns.length === 0) continue;

    if (sec === "trips") {
      const buckets = new Map<string, number>();
      for (const t of secTxns) {
        const label = t._trip_label?.trim() || "(no trip label)";
        buckets.set(label, (buckets.get(label) ?? 0) + 1);
      }
      const trips = report.detail_agg.trips ?? [];
      const order = trips.map((t) => t.label);
      const sortedLabels = Array.from(buckets.keys()).sort((a, b) => {
        const ai = order.indexOf(a);
        const bi = order.indexOf(b);
        if (ai !== -1 && bi !== -1) return ai - bi;
        if (ai !== -1) return -1;
        if (bi !== -1) return 1;
        if (a === "(no trip label)") return 1;
        if (b === "(no trip label)") return -1;
        return a.localeCompare(b);
      });
      for (const label of sortedLabels) {
        allFlat.push({
          id: `appendices-subcat-${sec}-${slugify(label)}-root`,
          title: label,
        });
      }
      continue;
    }

    const mainMap = new Map<
      string,
      { mainTitle: string; subs: { title: string; anchor: string }[] }
    >();
    for (const t of secTxns) {
      const mainId = String(t._main_category?.id ?? "0");
      const mainTitle = t._main_category?.title ?? "Uncategorised";
      const mainSlug = slugify(mainTitle);
      const subTitle = t._subcategory?.title ?? "(root)";
      const subSlug = subTitle === "(root)" ? "root" : slugify(subTitle);
      // Include mainId in the anchor so two main cats that share a title
      // (e.g. "Travel" in two different main ids) don't collide — both the
      // nav <li key> and the subsection anchor rely on this being unique.
      const anchor = `appendices-subcat-${sec}-${mainId}-${mainSlug}-${subSlug}`;
      if (!mainMap.has(mainId)) {
        mainMap.set(mainId, { mainTitle, subs: [] });
      }
      const entry = mainMap.get(mainId)!;
      if (!entry.subs.some((s) => s.anchor === anchor)) {
        entry.subs.push({ title: subTitle, anchor });
      }
    }
    const sortedMains = Array.from(mainMap.entries()).sort(([a], [b]) =>
      a.localeCompare(b),
    );
    for (const [, { mainTitle, subs }] of sortedMains) {
      const sortedSubs = [...subs].sort((a, b) => {
        const aRoot = a.title === "(root)";
        const bRoot = b.title === "(root)";
        if (aRoot !== bRoot) return aRoot ? -1 : 1;
        return a.title.localeCompare(b.title);
      });
      for (const s of sortedSubs) {
        allFlat.push({
          id: s.anchor,
          title: s.title === "(root)" ? mainTitle : `${mainTitle} › ${s.title}`,
        });
      }
    }
  }
  return allFlat;
}

// Common cats — exclude empty + reimbs, sort by total spend desc.
function buildCommonSubItems(report: MegaReportResponse): NavSubItem[] {
  const cats = Object.values(report.detail_agg.cats ?? {}).filter(
    (c) => c.section === "common" && !c.is_reimbursement,
  );
  const visible = cats.filter(
    (c) =>
      c.total.some((v) => v) ||
      c.partner_a_paid.some((v) => v) ||
      c.partner_b_paid.some((v) => v),
  );
  const ranked = visible
    .map((c) => ({
      title: c.title,
      total: c.total.reduce((a, v) => a + v, 0),
    }))
    .sort((a, b) => b.total - a.total);
  return ranked.map((c) => ({
    id: `common-subcat-${slugify(c.title)}`,
    title: c.title,
  }));
}

// Personal cats — per-partner subcat nav.
function buildPersonalSubItems(
  report: MegaReportResponse,
  partner: "partner_a" | "partner_b",
): NavSubItem[] {
  const months = report.detail_agg.months ?? [];
  const targetSection = partner === "partner_a" ? "personal_partner_a" : "personal_partner_b";
  const cats = Object.values(report.detail_agg.cats ?? {}).filter(
    (c) => c.section === targetSection && !c.is_reimbursement,
  );
  const visible = cats.filter((c) => {
    const paidKey = partner === "partner_a" ? "partner_a_paid" : "partner_b_paid";
    const recKey = partner === "partner_a" ? "partner_a_received" : "partner_b_received";
    return months.some((_, i) => {
      const v = (c[paidKey][i] ?? 0) - (c[recKey][i] ?? 0);
      return v !== 0;
    });
  });
  const partnerSlug = partner === "partner_a" ? "partner-a" : "partner-b";
  const ranked = visible
    .map((c) => {
      const paidKey = partner === "partner_a" ? "partner_a_paid" : "partner_b_paid";
      const recKey = partner === "partner_a" ? "partner_a_received" : "partner_b_received";
      const total = months.reduce(
        (a, _, i) => a + ((c[paidKey][i] ?? 0) - (c[recKey][i] ?? 0)),
        0,
      );
      return { title: c.title, total };
    })
    .sort((a, b) => Math.abs(b.total) - Math.abs(a.total));
  return ranked.map((c, idx) => ({
    id: `personal-subcat-${partnerSlug}-${slugify(c.title)}-${idx}`,
    title: c.title,
  }));
}

// Build full nav tree — top-level sections + dynamic sub-items.
export function buildNavItems(report: MegaReportResponse): NavItem[] {
  const items = buildStaticItems(report);
  const commonSubs = buildCommonSubItems(report);
  const partnerASubs = buildPersonalSubItems(report, "partner_a");
  const partnerBSubs = buildPersonalSubItems(report, "partner_b");
  const appendixSubs = buildAppendixSubItems(report);
  for (const item of items) {
    if (item.id === "common" && commonSubs.length > 0) {
      item.children = commonSubs;
    } else if (item.id === "personal-partner-a" && partnerASubs.length > 0) {
      item.children = partnerASubs;
    } else if (item.id === "personal-partner-b" && partnerBSubs.length > 0) {
      item.children = partnerBSubs;
    } else if (item.id === "appendices" && appendixSubs.length > 0) {
      item.children = appendixSubs;
    }
  }
  return items;
}