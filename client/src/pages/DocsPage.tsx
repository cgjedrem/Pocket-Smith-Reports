// DocsPage — in-app user guide: how to use the app. Static content only,
// no API calls. Installation/setup lives in the README, not here.

import type { ReactNode } from "react";

type Section = { id: string; label: string };

const SECTIONS: Section[] = [
  { id: "overview", label: "Overview" },
  { id: "connect", label: "Connect & sync" },
  { id: "setup", label: "Set up accounts & labels" },
  { id: "monthly-reports", label: "Monthly reports" },
  { id: "mega-reports", label: "Mega reports (12 months)" },
  { id: "bills", label: "Bills dashboard" },
  { id: "settings", label: "Settings" },
  { id: "cli", label: "Command line" },
  { id: "faq", label: "Troubleshooting" },
];

function CodeBlock({ children }: { children: string }) {
  return (
    <pre className="mb-3 overflow-x-auto rounded-lg border border-border bg-card p-4 text-sm leading-relaxed">
      <code>{children}</code>
    </pre>
  );
}

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="mb-10">
      <h2 className="mb-3 mt-8 text-xl">{title}</h2>
      {children}
    </section>
  );
}

export function DocsPage() {
  return (
    <div className="mx-auto max-w-[820px]">
      <h1 className="mb-4">Docs</h1>
      <p className="mb-6 text-muted-foreground">
        How to use Pocket-Smith Reports — connect your account, sync, and
        build reports. (Install and run instructions are in the README.)
      </p>

      <nav
        aria-label="On this page"
        className="mb-8 rounded-lg border border-border bg-card p-4"
      >
        <p className="mb-2 text-sm font-semibold">On this page</p>
        <ul className="space-y-1 pl-5 text-sm">
          {SECTIONS.map((s) => (
            <li key={s.id}>
              <a className="text-accent hover:underline" href={`#${s.id}`}>
                {s.label}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      <Section id="overview" title="Overview">
        <p className="mb-3">
          Pocket-Smith Reports turns your PocketSmith data into readable PDF
          reports and a bills dashboard. Everything runs on your machine:
          your PocketSmith API key and all synced data stay in local,
          git-ignored files.
        </p>
        <p className="mb-3">A normal session looks like this:</p>
        <ol className="mb-3 list-decimal space-y-1 pl-5">
          <li><strong>Sync</strong> — pull a month range from PocketSmith.</li>
          <li><strong>Set up accounts</strong> — map accounts to partners, exclude what you don't want.</li>
          <li><strong>Build a report</strong> — a single month, or a 12-month Mega report.</li>
          <li><strong>Review Bills</strong> — check recurring payments against your budget.</li>
        </ol>
      </Section>

      <Section id="connect" title="Connect & sync">
        <p className="mb-3">
          Sync pulls your PocketSmith data into local JSON snapshots. It runs
          in stages — accounts, then categories, then transactions — and never
          writes partial data: if a fetch fails, no new snapshot is published.
        </p>
        <ol className="mb-3 list-decimal space-y-1 pl-5">
          <li>
            Open <strong>Settings</strong> and paste your PocketSmith API key.
            It is stored as <code>API_KEY</code> in the repo-root{" "}
            <code>.env</code> (git-ignored) and never shown again.
          </li>
          <li>
            Open <strong>Sync</strong>, choose a start and end month, and run
            the sync.
          </li>
          <li>
            Check the row counts and last-sync status shown on the page.
          </li>
        </ol>
        <p className="mb-3">
          Synced snapshots are written under <code>data/private/</code>, which
          is git-ignored.
        </p>
      </Section>

      <Section id="setup" title="Set up accounts & labels">
        <p className="mb-3">
          After your first sync, tell the app who owns each account before
          generating reports:
        </p>
        <ul className="mb-3 list-disc space-y-1 pl-5">
          <li>
            <strong>Partner labels</strong> — the two display names used across
            all reports. They must be distinct and non-empty.
          </li>
          <li>
            <strong>Account ownership</strong> — assign every synced account to
            a partner. Every report account must map to a partner, or the
            build fails closed.
          </li>
          <li>
            <strong>Exclusions</strong> — excluded accounts are never fetched
            by sync and never appear in reports.
          </li>
          <li>
            <strong>Category mappings</strong> — route categories into report
            sections (personal, savings, transfers, and so on).
          </li>
        </ul>
        <p className="mb-3">
          All of this lives in <strong>Settings</strong> and in{" "}
          <code>data/private/</code> (git-ignored).
        </p>
      </Section>

      <Section id="monthly-reports" title="Monthly reports">
        <p className="mb-3">
          A single-month report with spending, savings, and transfers. It is
          published as paired HTML and PDF.
        </p>
        <ol className="mb-3 list-decimal space-y-1 pl-5">
          <li>Open <strong>Monthly Reports</strong>.</li>
          <li>Pick a month and generate the report.</li>
          <li>Open it in the browser, or export the PDF.</li>
        </ol>
        <p className="mb-3">
          Reports are versioned (<code>contract_version: 2</code>). If the app
          rejects a stored report as outdated (409), regenerate it from the
          button on the page.
        </p>
      </Section>

      <Section id="mega-reports" title="Mega reports (12 months)">
        <p className="mb-3">
          A full-year report covering a 12-month range, with per-section
          navigation and export. The build validates every month in the range
          before publishing, so a missing month fails the whole build rather
          than producing a partial report.
        </p>
        <ol className="mb-3 list-decimal space-y-1 pl-5">
          <li>Open <strong>Mega Reports</strong>.</li>
          <li>Choose the start and end month and build.</li>
          <li>Navigate by section and export what you need.</li>
        </ol>
      </Section>

      <Section id="bills" title="Bills dashboard">
        <p className="mb-3">A dashboard for recurring payments:</p>
        <ul className="mb-3 list-disc space-y-1 pl-5">
          <li><strong>Budget</strong> — recurring bills against the budget.</li>
          <li><strong>Economy bar</strong> — a quick health view of fixed costs.</li>
          <li><strong>Savings</strong> — what's left after bills.</li>
        </ul>
      </Section>

      <Section id="settings" title="Settings">
        <p className="mb-3"><strong>Settings</strong> is the control center:</p>
        <ul className="mb-3 list-disc space-y-1 pl-5">
          <li><strong>API key</strong> — connect or rotate your PocketSmith key.</li>
          <li><strong>Partner labels</strong> — the two names used everywhere.</li>
          <li><strong>Accounts</strong> — ownership and exclusions.</li>
          <li><strong>Category mappings</strong> — route categories into sections.</li>
        </ul>
        <p className="mb-3">
          Invalid partner labels (duplicates, empty, overlong, or the reserved
          "Partner A"/"Partner B") are rejected with a visible error.
        </p>
      </Section>

      <Section id="cli" title="Command line">
        <p className="mb-3">
          Everything the app does can also run from the command line (from the
          repository root). Sync stages:
        </p>
        <CodeBlock>{`PYTHONPATH=src python src/live_sync.py accounts --start 2025-08 --end 2026-07
PYTHONPATH=src python src/live_sync.py categories --start 2025-08 --end 2026-07
PYTHONPATH=src python src/live_sync.py transactions --start 2025-08 --end 2026-07`}</CodeBlock>
        <p className="mb-3">Build a single-month or Mega report directly:</p>
        <CodeBlock>{`python src/v4_pipeline/build.py --month 2026-04 --data-dir data --input-kind synthetic --detailed-section-map data/sample_apr_2026_detailed_section_mapping.json
PYTHONPATH=src python -m mega.build_mega --start 2025-08 --end 2026-07 --data-dir data/private --input-kind live`}</CodeBlock>
        <p className="mb-3">
          Every build requires <code>--input-kind live</code> or{" "}
          <code>--input-kind synthetic</code>. Reports are published to{" "}
          <code>out/</code> as paired HTML and PDF.
        </p>
      </Section>

      <Section id="faq" title="Troubleshooting">
        <ul className="mb-3 list-disc space-y-2 pl-5">
          <li>
            <strong>"API_KEY is missing"</strong> — add your PocketSmith key in
            Settings, then sync again.
          </li>
          <li>
            <strong>Sync fails partway</strong> — stages fail closed; fix the
            error and re-run. No partial snapshot is kept.
          </li>
          <li>
            <strong>409 on an old report</strong> — regenerate it (button on
            the reports page).
          </li>
          <li>
            <strong>PDF won't render</strong> — the WeasyPrint native libraries
            are missing (see the README install steps).
          </li>
          <li>
            <strong>An account doesn't show up</strong> — it's either excluded
            or not mapped to a partner in Settings.
          </li>
        </ul>
      </Section>
    </div>
  );
}