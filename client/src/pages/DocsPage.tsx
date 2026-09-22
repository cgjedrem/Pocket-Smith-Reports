// DocsPage — in-app documentation: install, run, and use the app locally.
// Static content only — no API calls. Mirrors the README quick start; the
// deep sync/CLI reference lives here instead of the README.

import type { ReactNode } from "react";

type Section = { id: string; label: string };

const SECTIONS: Section[] = [
  { id: "overview", label: "Overview" },
  { id: "getting-started", label: "Getting started" },
  { id: "install", label: "Install & run" },
  { id: "first-run", label: "First run" },
  { id: "using", label: "Using the app" },
  { id: "staged-sync", label: "Staged live sync" },
  { id: "report-cli", label: "Report CLI" },
  { id: "fixture", label: "Synthetic fixture contract" },
  { id: "releases", label: "Release notes" },
  { id: "testing", label: "Testing & QA" },
  { id: "privacy", label: "Data & privacy" },
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
        How to install, run, and use Pocket-Smith Reports on your own machine.
        The repository <code>docs/</code> folder holds design notes and policy
        deep-dives; this page is the practical guide.
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
          Pocket-Smith Reports is a local-first personal-finance reporting tool
          for PocketSmith. A FastAPI backend syncs your PocketSmith data into
          local JSON snapshots, and a React dashboard renders reports and a
          bills overview. Nothing leaves your machine: the API key and all
          synced data stay in local, git-ignored files.
        </p>
        <ul className="mb-3 list-disc space-y-1 pl-5">
          <li>Staged sync from the PocketSmith API (accounts → categories → transactions)</li>
          <li>Single-month reports as paired HTML + PDF</li>
          <li>12-month &ldquo;Mega&rdquo; reports with per-section navigation</li>
          <li>Bills dashboard with budget, economy, and savings views</li>
          <li>Settings for partners, accounts, and category mappings</li>
        </ul>
        <p className="mb-3">
          Tracked fixtures use neutral synthetic data only. Your live data
          never enters version control — see <code>docs/DATA_POLICY.md</code>.
        </p>
      </Section>

      <Section id="getting-started" title="Getting started">
        <p className="mb-3">You need:</p>
        <ul className="mb-3 list-disc space-y-1 pl-5">
          <li>
            Python 3.13+ and{" "}
            <a
              className="text-accent hover:underline"
              href="https://docs.astral.sh/uv/"
            >
              uv
            </a>{" "}
            (manages the backend virtualenv from <code>uv.lock</code>)
          </li>
          <li>Node.js 20+ and pnpm 10</li>
          <li>
            WeasyPrint native libraries (Pango, Cairo, GDK-PixBuf) and system
            fonts for PDF rendering — see below
          </li>
        </ul>
        <p className="mb-3">
          On Windows, install the WeasyPrint GTK runtime with the bundled
          script (the Python wheel does not ship the DLLs). Get the SHA-256
          only from the official MSYS2 release or a signed checksum source; the
          script verifies it before running the installer:
        </p>
        <CodeBlock>{`.\\scripts\\install-weasyprint-msys2.ps1 -ExpectedSha256 '<official-msys2-sha256>'`}</CodeBlock>
        <p className="mb-3">
          Use <code>-WhatIf</code> to preview. GPG verification remains a
          manual step. On Linux, install Pango, Cairo, and GDK-PixBuf plus
          system fonts with your package manager.
        </p>
      </Section>

      <Section id="install" title="Install & run">
        <CodeBlock>{`git clone https://github.com/cgjedrem/Pocket-Smith-Reports.git
cd Pocket-Smith-Reports
uv sync                # backend deps (pyproject.toml + uv.lock)
cd client
pnpm install           # client deps (pnpm-lock.yaml)`}</CodeBlock>
        <p className="mb-3">
          Start the backend (PowerShell, from the repository root). The client
          expects the API on port 8001:
        </p>
        <CodeBlock>{`.\\scripts\\run_api.ps1 -Port 8001`}</CodeBlock>
        <p className="mb-3">
          In a second terminal, start the frontend:
        </p>
        <CodeBlock>{`cd client
pnpm dev               # http://localhost:5174`}</CodeBlock>
        <p className="mb-3">
          The Vite dev server proxies <code>/api</code> to{" "}
          <code>http://localhost:8001</code>. Point it elsewhere with{" "}
          <code>VITE_API_URL</code>.
        </p>
      </Section>

      <Section id="first-run" title="First run">
        <ol className="mb-3 list-decimal space-y-1 pl-5">
          <li>
            Open the app and go to <strong>Settings</strong>. Paste your
            PocketSmith API key — it is stored as <code>API_KEY</code> in the
            repo-root <code>.env</code>, which is git-ignored and never sent
            back to the UI.
          </li>
          <li>
            Run your first sync from the <strong>Sync</strong> page (see{" "}
            <a className="text-accent hover:underline" href="#staged-sync">
              Staged live sync
            </a>
            ).
          </li>
          <li>
            Review <strong>Settings</strong> — partner labels, account
            ownership, excluded accounts, and category mappings.
          </li>
          <li>
            Generate your first report from <strong>Monthly Reports</strong>.
          </li>
        </ol>
      </Section>

      <Section id="using" title="Using the app">
        <ul className="mb-3 list-disc space-y-1 pl-5">
          <li>
            <strong>Sync</strong> — pull PocketSmith data for a month range;
            shows row counts and last-sync status. Syncs run in stages and fail
            closed on incomplete data.
          </li>
          <li>
            <strong>Monthly Reports</strong> — generate a single-month HTML +
            PDF report; regenerate or export any stored month.
          </li>
          <li>
            <strong>Mega Reports</strong> — build a 12-month report with
            per-section navigation and export.
          </li>
          <li>
            <strong>Bills</strong> — recurring payments dashboard with budget
            coverage, economy bar, and savings view.
          </li>
          <li>
            <strong>Settings</strong> — API key, partner labels, account
            ownership/exclusions, and category mappings.
          </li>
        </ul>
      </Section>

      <Section id="staged-sync" title="Staged live sync">
        <p className="mb-3">
          The sync API drives the staged CLI under the hood. Run stages from
          the repository root; they read only the repo-root <code>.env</code>{" "}
          and write only under <code>data/private/</code>. The legacy{" "}
          <code>src/pull-month-ps-paginate.py</code> is disabled and cannot
          write snapshots.
        </p>
        <p className="mb-3">
          <strong>1. Account catalog</strong> — probes every account for every
          requested month and writes metadata only:
        </p>
        <CodeBlock>{`PYTHONPATH=src python src/live_sync.py accounts --start 2025-08 --end 2026-07`}</CodeBlock>
        <p className="mb-3">
          Then create <code>data/private/account_mappings.json</code> covering
          exactly the catalog IDs (names must match the catalog; both partner
          labels nonempty and distinct; duplicate IDs fail before any API
          call):
        </p>
        <CodeBlock>{`{"schema_version":1,"partners":{"partner_a":{"label":"..."},"partner_b":{"label":"..."}},"accounts":{"ID":{"name":"exact account catalog name","owner":"partner_a","excluded":false}}}`}</CodeBlock>
        <p className="mb-3">
          <strong>2. Category catalog</strong> — fetch categories; human
          role/section mapping happens afterwards:
        </p>
        <CodeBlock>{`PYTHONPATH=src python src/live_sync.py categories --start 2025-08 --end 2026-07`}</CodeBlock>
        <p className="mb-3">
          <strong>3. Transactions</strong> — fetches every non-excluded mapped
          account for every month before writing anything; a fetch error
          publishes no new monthly snapshot:
        </p>
        <CodeBlock>{`PYTHONPATH=src python src/live_sync.py transactions --start 2025-08 --end 2026-07`}</CodeBlock>
        <p className="mb-3">
          An excluded account is never fetched by the transaction stage or
          rendered from live snapshots. <code>excluded: true</code> in the
          unified mapping is authoritative; <code>--exclude-account-id</code>{" "}
          only adds one-run exclusions.
        </p>
      </Section>

      <Section id="report-cli" title="Report CLI">
        <p className="mb-3">
          Builds can also run from the command line. Single-month (paired
          HTML/PDF published to <code>out/YYYYMM_partner_report.*</code>;{" "}
          <code>--name</code> overrides the basename; <code>--output-dir</code>{" "}
          is not supported):
        </p>
        <CodeBlock>{`python src/v4_pipeline/build.py --month 2026-04 --data-dir data --input-kind synthetic --detailed-section-map data/sample_apr_2026_detailed_section_mapping.json`}</CodeBlock>
        <p className="mb-3">
          Multi-month Mega build (validates every month in the inclusive range
          before publishing):
        </p>
        <CodeBlock>{`PYTHONPATH=src python -m mega.build_mega --start 2026-04 --end 2026-04 --data-dir data --input-kind synthetic --detailed-section-map data/sample_apr_2026_detailed_section_mapping.json`}</CodeBlock>
        <p className="mb-3">
          Every CLI build requires <code>--input-kind live</code> or{" "}
          <code>--input-kind synthetic</code>. Publishers serialize per name
          (30s wait limit), stage artifacts under{" "}
          <code>out/.published/NAME/</code>, and write{" "}
          <code>out/NAME.manifest.json</code> for consumers that need a
          coherent HTML/PDF pair during a concurrent publish.
        </p>
      </Section>

      <Section id="fixture" title="Synthetic fixture contract">
        <ul className="mb-3 list-disc space-y-1 pl-5">
          <li>Live source files use exactly <code>YYYY-MM_ps_raw.json</code> in <code>--data-dir</code>; synthetic files use exactly <code>sample_&lt;mon&gt;_&lt;year&gt;.json</code>. No filename fallback, glob lookup, or partial-period build.</li>
          <li>Every requested month must be readable valid JSON before publishing starts.</li>
          <li>Fixture transaction identifiers stay in the reserved synthetic range.</li>
          <li>Fixture labels use neutral <code>Partner A</code> / <code>Partner B</code> terminology.</li>
          <li>Fixture input uses normalized category accounting and literal boolean transfer flags when supplied.</li>
          <li>The loader owns account-to-partner attribution for fixture labels.</li>
        </ul>
      </Section>

      <Section id="releases" title="Release notes">
        <p className="mb-3">
          <strong>Report contract v2 &amp; canonical labels.</strong> Stored
          reports are stamped <code>contract_version: 2</code>; pre-change
          payloads are rejected with <strong>409 Conflict</strong> and must be
          regenerated (UI button or the generate endpoints). Partner labels
          from the unified account mapping are validated on every load and at
          the settings write path: duplicates, empty, overlong, or reserved{" "}
          <code>Partner A</code>/<code>Partner B</code> labels fail with HTTP
          400; an invalid label degrades only the affected partner to the
          placeholder with a visible warning. There are no hardcoded names
          anywhere in the app.
        </p>
        <p className="mb-3">
          <strong>Bills snapshot schema 5.</strong> Events carry additive{" "}
          <code>partner_id</code>/<code>partner_slot</code>; the API accepts{" "}
          <code>?partner_id=</code> (supersedes the label-based{" "}
          <code>?partner=</code>). Schema-4 snapshots still load but lack
          stable partner routing until rebuilt.
        </p>
        <p className="mb-3">
          <strong>Config migration.</strong> Old per-name personal sections in{" "}
          <code>detailed_section_mapping.json</code> must be renamed to{" "}
          <code>personal_partner_a</code>/<code>personal_partner_b</code>;
          until then every report build fails closed.
        </p>
      </Section>

      <Section id="testing" title="Testing & QA">
        <CodeBlock>{`uv run pytest src/mega/tests src/v4_pipeline/tests src/mom/tests -q
PYTHONPATH=src python -m pytest src/mega/tests/test_release_gate.py -q   # Mega release gate
cd client && pnpm build && pnpm test`}</CodeBlock>
        <p className="mb-3">
          The release gate uses only the committed synthetic fixture, builds
          the full report and every <code>--only</code> section, and validates
          the HTML/PDF artifacts with <code>pypdf</code>. Tests marked{" "}
          <code>pdf_renderer</code> need working native WeasyPrint libraries.
        </p>
      </Section>

      <Section id="privacy" title="Data & privacy">
        <ul className="mb-3 list-disc space-y-1 pl-5">
          <li>Everything runs locally; no data leaves your machine.</li>
          <li>
            Tracked files contain only deterministic synthetic data — neutral
            labels, synthetic IDs, deterministic payees.
          </li>
          <li>
            <code>.gitignore</code> blocks <code>data/private/</code>,{" "}
            <code>data/raw/</code>, <code>.env</code>, <code>out/</code>, keys,
            and local JSON exports.
          </li>
        </ul>
        <p className="mb-3">
          The full policy lives in <code>docs/DATA_POLICY.md</code>. Hardening
          work is tracked in <code>docs/production-hardening-loops.md</code>.
        </p>
      </Section>
    </div>
  );
}