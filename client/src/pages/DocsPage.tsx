// DocsPage — in-app user guide: how to use the app. Static content only,
// no API calls. Illustrations are pseudo-components (mock UI rendered with
// the same design system), never real screenshots. Installation/setup lives
// in the README, not here.

import type { ReactNode } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Banknote,
  CalendarDays,
  CheckCircle2,
  FileText,
  Files,
  Info,
  KeyRound,
  LayoutDashboard,
  RefreshCw,
  Settings2,
  Tags,
  Terminal,
  Users,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

type SectionMeta = { id: string; label: string; icon: typeof FileText };

const SECTIONS: SectionMeta[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "connect", label: "Connect & sync", icon: RefreshCw },
  { id: "setup", label: "Set up accounts & labels", icon: Users },
  { id: "monthly-reports", label: "Monthly reports", icon: FileText },
  { id: "mega-reports", label: "Mega reports (12 months)", icon: Files },
  { id: "bills", label: "Bills dashboard", icon: Banknote },
  { id: "settings", label: "Settings", icon: Settings2 },
  { id: "cli", label: "Command line", icon: Terminal },
  { id: "faq", label: "Troubleshooting", icon: AlertTriangle },
];

/* ---------- primitives ---------- */

function CodeBlock({ children }: { children: string }) {
  return (
    <pre className="mb-3 overflow-x-auto rounded-lg border border-border bg-card p-4 text-sm leading-relaxed">
      <code>{children}</code>
    </pre>
  );
}

function Section({
  id,
  title,
  icon: Icon,
  children,
}: {
  id: string;
  title: string;
  icon: typeof FileText;
  children: ReactNode;
}) {
  return (
    <section id={id} className="mb-12 scroll-mt-24">
      <h2 className="mb-4 mt-10 flex items-center gap-2 text-xl">
        <Icon className="size-5 text-accent" aria-hidden />
        {title}
      </h2>
      {children}
    </section>
  );
}

function Step({ n, children }: { n: number; children: ReactNode }) {
  return (
    <li className="flex gap-3">
      <span
        aria-hidden
        className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold text-accent-foreground"
      >
        {n}
      </span>
      <div className="pb-1">{children}</div>
    </li>
  );
}

function Callout({
  kind = "info",
  children,
}: {
  kind?: "info" | "warn";
  children: ReactNode;
}) {
  const Icon = kind === "warn" ? AlertTriangle : Info;
  return (
    <div
      className={cn(
        "mb-3 flex gap-3 rounded-lg border p-4 text-sm",
        kind === "warn"
          ? "border-destructive/40 bg-destructive/10"
          : "border-border bg-card",
      )}
    >
      <Icon
        aria-hidden
        className={cn(
          "mt-0.5 size-4 shrink-0",
          kind === "warn" ? "text-destructive" : "text-accent",
        )}
      />
      <div>{children}</div>
    </div>
  );
}

/** Caption under a pseudo-component so readers know it is illustrative. */
function Example({ children }: { children: ReactNode }) {
  return (
    <figure className="mb-4">
      <div aria-hidden className="pointer-events-none select-none">
        {children}
      </div>
      <figcaption className="mt-1 text-xs text-muted-foreground">
        Example — illustration only, not interactive.
      </figcaption>
    </figure>
  );
}

/* ---------- pseudo-components (mock UI) ---------- */

function MockSyncCard() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <RefreshCw className="size-4" aria-hidden /> Sync
        </CardTitle>
        <CardDescription>Pull PocketSmith data into local snapshots</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">Start month</p>
            <div className="flex h-9 items-center gap-2 rounded-md border border-border bg-background px-3 text-sm">
              <CalendarDays className="size-4 text-muted-foreground" aria-hidden />
              Aug 2025
            </div>
          </div>
          <ArrowRight className="mb-2 size-4 text-muted-foreground" aria-hidden />
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">End month</p>
            <div className="flex h-9 items-center gap-2 rounded-md border border-border bg-background px-3 text-sm">
              <CalendarDays className="size-4 text-muted-foreground" aria-hidden />
              Jul 2026
            </div>
          </div>
          <Button size="sm">Run sync</Button>
        </div>
        <Separator />
        <div className="flex flex-wrap gap-2 text-xs">
          <Badge variant="secondary">accounts · done</Badge>
          <Badge variant="secondary">categories · done</Badge>
          <Badge>transactions · done</Badge>
          <Badge variant="outline">4,213 rows</Badge>
          <Badge variant="outline" className="gap-1">
            <CheckCircle2 className="size-3" aria-hidden /> last sync just now
          </Badge>
        </div>
      </CardContent>
    </Card>
  );
}

function MockSettingsCard() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <KeyRound className="size-4" aria-hidden /> Settings
        </CardTitle>
        <CardDescription>API key, partner labels, accounts</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">PocketSmith API key</p>
          <div className="flex h-9 items-center rounded-md border border-border bg-background px-3 font-mono text-sm tracking-widest text-muted-foreground">
            ••••••••••••••••••••
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">Partner A label</p>
            <div className="flex h-9 items-center rounded-md border border-border bg-background px-3 text-sm">
              Alex
            </div>
          </div>
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">Partner B label</p>
            <div className="flex h-9 items-center rounded-md border border-border bg-background px-3 text-sm">
              Sam
            </div>
          </div>
        </div>
        <div className="rounded-md border border-border">
          <div className="flex items-center justify-between px-3 py-2 text-sm">
            <span>Fixture A Checking</span>
            <Badge variant="secondary">Alex</Badge>
          </div>
          <Separator />
          <div className="flex items-center justify-between px-3 py-2 text-sm">
            <span>Fixture B Savings</span>
            <Badge variant="secondary">Sam</Badge>
          </div>
          <Separator />
          <div className="flex items-center justify-between px-3 py-2 text-sm text-muted-foreground">
            <span>Old joint account</span>
            <Badge variant="outline">excluded</Badge>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function MockReportCard() {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <FileText className="size-4" aria-hidden /> April 2026
          </CardTitle>
          <CardDescription>Single-month report</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2 text-xs">
            <Badge variant="secondary">HTML</Badge>
            <Badge variant="secondary">PDF</Badge>
          </div>
          <div className="flex gap-2">
            <Button size="sm">Open</Button>
            <Button size="sm" variant="outline">
              Export PDF
            </Button>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Files className="size-4" aria-hidden /> Aug 2025 – Jul 2026
          </CardTitle>
          <CardDescription>Mega report · 12 months</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-1.5 text-xs">
            <Badge variant="outline">Spending</Badge>
            <Badge variant="outline">Savings</Badge>
            <Badge variant="outline">Transfers</Badge>
            <Badge variant="outline">Personal</Badge>
          </div>
          <div className="flex gap-2">
            <Button size="sm">Open</Button>
            <Button size="sm" variant="outline">
              Export section
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function MockBillsPreview() {
  const rows = [
    { name: "Rent", amount: "12,500", state: "covered" },
    { name: "Power", amount: "890", state: "covered" },
    { name: "Streaming", amount: "249", state: "unpaid" },
  ] as const;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Banknote className="size-4" aria-hidden /> Bills · September
        </CardTitle>
        <CardDescription>Recurring payments vs budget</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-1.5">
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>Budget coverage</span>
            <span>86%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-secondary">
            <div className="h-full w-[86%] rounded-full bg-accent" />
          </div>
        </div>
        <div className="rounded-md border border-border">
          {rows.map((r, i) => (
            <div key={r.name}>
              {i > 0 && <Separator />}
              <div className="flex items-center justify-between px-3 py-2 text-sm">
                <span>{r.name}</span>
                <span className="flex items-center gap-2">
                  <span className="text-muted-foreground">{r.amount}</span>
                  {r.state === "covered" ? (
                    <Badge variant="secondary" className="gap-1">
                      <CheckCircle2 className="size-3" aria-hidden /> covered
                    </Badge>
                  ) : (
                    <Badge variant="destructive">unpaid</Badge>
                  )}
                </span>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

/* ---------- page ---------- */

export function DocsPage() {
  return (
    <div className="mx-auto max-w-6xl">
      <h1 className="mb-4">Docs</h1>
      <p className="mb-8 max-w-[720px] text-muted-foreground">
        How to use Pocket-Smith Reports — connect your account, sync, and
        build reports. The cards below are illustrations of the real screens.
        (Install and run instructions are in the README.)
      </p>

      <div className="grid gap-10 lg:grid-cols-[220px_minmax(0,1fr)]">
        {/* Sticky sidebar TOC */}
        <nav aria-label="On this page" className="hidden lg:block">
          <div className="sticky top-20 space-y-1 border-l border-border">
            <p className="mb-2 pl-4 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              On this page
            </p>
            {SECTIONS.map((s) => (
              <a
                key={s.id}
                href={`#${s.id}`}
                className="block py-1 pl-4 text-sm text-muted-foreground transition-colors hover:text-foreground"
              >
                {s.label}
              </a>
            ))}
          </div>
        </nav>

        <div>
          {/* Mobile TOC */}
          <nav
            aria-label="Page contents"
            className="mb-8 rounded-lg border border-border bg-card p-4 lg:hidden"
          >
            <p className="mb-2 text-sm font-semibold">On this page</p>
            <ul className="grid grid-cols-2 gap-1 text-sm">
              {SECTIONS.map((s) => (
                <li key={s.id}>
                  <a className="text-accent hover:underline" href={`#${s.id}`}>
                    {s.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>

          <Section id="overview" title="Overview" icon={LayoutDashboard}>
            <p className="mb-3">
              Pocket-Smith Reports turns your PocketSmith data into readable
              PDF reports and a bills dashboard. Everything runs on your
              machine: your PocketSmith API key and all synced data stay in
              local, git-ignored files.
            </p>
            <ol className="mb-3 space-y-2">
              <Step n={1}>
                <strong>Sync</strong> — pull a month range from PocketSmith.
              </Step>
              <Step n={2}>
                <strong>Set up accounts</strong> — map accounts to partners,
                exclude what you don't want.
              </Step>
              <Step n={3}>
                <strong>Build a report</strong> — a single month, or a
                12-month Mega report.
              </Step>
              <Step n={4}>
                <strong>Review Bills</strong> — check recurring payments
                against your budget.
              </Step>
            </ol>
            <Callout>
              Nothing leaves your machine. The API talks only to PocketSmith
              and to <code>localhost</code>.
            </Callout>
          </Section>

          <Section id="connect" title="Connect & sync" icon={RefreshCw}>
            <p className="mb-3">
              Sync pulls your PocketSmith data into local JSON snapshots. It
              runs in stages — accounts, then categories, then transactions —
              and never writes partial data: if a fetch fails, no new snapshot
              is published.
            </p>
            <Example>
              <MockSyncCard />
            </Example>
            <ol className="mb-3 space-y-2">
              <Step n={1}>
                Open <strong>Settings</strong> and paste your PocketSmith API
                key. It is stored as <code>API_KEY</code> in the repo-root{" "}
                <code>.env</code> (git-ignored) and never shown again.
              </Step>
              <Step n={2}>
                Open <strong>Sync</strong>, choose a start and end month, and
                run the sync.
              </Step>
              <Step n={3}>
                Check the row counts and last-sync status shown on the page.
              </Step>
            </ol>
            <Callout kind="warn">
              Synced snapshots land in <code>data/private/</code>{" "}
              (git-ignored). If a stage fails, fix the error and re-run — no
              partial snapshot is kept.
            </Callout>
          </Section>

          <Section id="setup" title="Set up accounts & labels" icon={Users}>
            <p className="mb-3">
              After your first sync, tell the app who owns each account before
              generating reports:
            </p>
            <Example>
              <MockSettingsCard />
            </Example>
            <ul className="mb-3 list-disc space-y-1 pl-5">
              <li>
                <strong>Partner labels</strong> — the two display names used
                across all reports. They must be distinct and non-empty.
              </li>
              <li>
                <strong>Account ownership</strong> — assign every synced
                account to a partner. Every report account must map to a
                partner, or the build fails closed.
              </li>
              <li>
                <strong>Exclusions</strong> — excluded accounts are never
                fetched by sync and never appear in reports.
              </li>
              <li>
                <strong>Category mappings</strong>{" "}
                <Tags className="inline size-3.5 align-[-2px] text-muted-foreground" aria-hidden />{" "}
                — route categories into report sections (personal, savings,
                transfers, and so on).
              </li>
            </ul>
            <p className="mb-3">
              All of this lives in <strong>Settings</strong> and in{" "}
              <code>data/private/</code> (git-ignored).
            </p>
          </Section>

          <Section id="monthly-reports" title="Monthly reports" icon={FileText}>
            <p className="mb-3">
              A single-month report with spending, savings, and transfers. It
              is published as paired HTML and PDF.
            </p>
            <Example>
              <MockReportCard />
            </Example>
            <ol className="mb-3 space-y-2">
              <Step n={1}>
                Open <strong>Monthly Reports</strong>.
              </Step>
              <Step n={2}>Pick a month and generate the report.</Step>
              <Step n={3}>Open it in the browser, or export the PDF.</Step>
            </ol>
            <Callout>
              Reports are versioned (<code>contract_version: 2</code>). If the
              app rejects a stored report as outdated (409), regenerate it
              from the button on the page.
            </Callout>
          </Section>

          <Section id="mega-reports" title="Mega reports (12 months)" icon={Files}>
            <p className="mb-3">
              A full-year report covering a 12-month range, with per-section
              navigation and export. The build validates every month in the
              range before publishing, so a missing month fails the whole
              build rather than producing a partial report.
            </p>
            <ol className="mb-3 space-y-2">
              <Step n={1}>
                Open <strong>Mega Reports</strong>.
              </Step>
              <Step n={2}>Choose the start and end month and build.</Step>
              <Step n={3}>Navigate by section and export what you need.</Step>
            </ol>
          </Section>

          <Section id="bills" title="Bills dashboard" icon={Banknote}>
            <p className="mb-3">A dashboard for recurring payments:</p>
            <Example>
              <MockBillsPreview />
            </Example>
            <ul className="mb-3 list-disc space-y-1 pl-5">
              <li>
                <strong>Budget</strong> — recurring bills against the budget.
              </li>
              <li>
                <strong>Economy bar</strong> — a quick health view of fixed
                costs.
              </li>
              <li>
                <strong>Savings</strong> — what's left after bills.
              </li>
            </ul>
          </Section>

          <Section id="settings" title="Settings" icon={Settings2}>
            <p className="mb-3">
              <strong>Settings</strong> is the control center:
            </p>
            <ul className="mb-3 list-disc space-y-1 pl-5">
              <li>
                <strong>API key</strong> — connect or rotate your PocketSmith
                key.
              </li>
              <li>
                <strong>Partner labels</strong> — the two names used
                everywhere.
              </li>
              <li>
                <strong>Accounts</strong> — ownership and exclusions.
              </li>
              <li>
                <strong>Category mappings</strong> — route categories into
                sections.
              </li>
            </ul>
            <Callout kind="warn">
              Invalid partner labels (duplicates, empty, overlong, or the
              reserved "Partner A"/"Partner B") are rejected with a visible
              error.
            </Callout>
          </Section>

          <Section id="cli" title="Command line" icon={Terminal}>
            <p className="mb-3">
              Everything the app does can also run from the command line (from
              the repository root). Sync stages:
            </p>
            <CodeBlock>{`PYTHONPATH=src python src/live_sync.py accounts --start 2025-08 --end 2026-07
PYTHONPATH=src python src/live_sync.py categories --start 2025-08 --end 2026-07
PYTHONPATH=src python src/live_sync.py transactions --start 2025-08 --end 2026-07`}</CodeBlock>
            <p className="mb-3">
              Build a single-month or Mega report directly:
            </p>
            <CodeBlock>{`python src/v4_pipeline/build.py --month 2026-04 --data-dir data --input-kind synthetic --detailed-section-map data/sample_apr_2026_detailed_section_mapping.json
PYTHONPATH=src python -m mega.build_mega --start 2025-08 --end 2026-07 --data-dir data/private --input-kind live`}</CodeBlock>
            <p className="mb-3">
              Every build requires <code>--input-kind live</code> or{" "}
              <code>--input-kind synthetic</code>. Reports are published to{" "}
              <code>out/</code> as paired HTML and PDF.
            </p>
          </Section>

          <Section id="faq" title="Troubleshooting" icon={AlertTriangle}>
            <ul className="mb-3 list-disc space-y-2 pl-5">
              <li>
                <strong>"API_KEY is missing"</strong> — add your PocketSmith
                key in Settings, then sync again.
              </li>
              <li>
                <strong>Sync fails partway</strong> — stages fail closed; fix
                the error and re-run. No partial snapshot is kept.
              </li>
              <li>
                <strong>409 on an old report</strong> — regenerate it (button
                on the reports page).
              </li>
              <li>
                <strong>PDF won't render</strong> — the WeasyPrint native
                libraries are missing (see the README install steps).
              </li>
              <li>
                <strong>An account doesn't show up</strong> — it's either
                excluded or not mapped to a partner in Settings.
              </li>
            </ul>
          </Section>
        </div>
      </div>
    </div>
  );
}