# Windows PowerShell Environment

All development on this machine runs on **Windows with PowerShell** (5.1 and 7+).
Commands, scripts, and agent instructions MUST honor these rules.

## Shell Syntax

- PowerShell does NOT support POSIX chaining operators (`&&`, `||`). Chain commands
  with `;` and gate on success with `if ($?) { ... }`.
- Do not assume a bash shell exists. If a tool truly needs POSIX features, document
  the Git Bash/WSL fallback explicitly instead of writing bash-only snippets inline.
- PowerShell (Windows PowerShell 5.1) has no heredoc. Feed inline scripts via
  piped here-strings or `-c` arguments.
- Every `powershell` tool invocation starts a fresh process: `Set-Location`,
  environment variables, and alias state do not persist between calls. Re-establish
  context per call.

## Paths and Files

- Use Windows-style paths with backslashes when addressing this machine directly;
  inside committed files (package.json scripts, CI config, docs) prefer
  forward-slash paths only where the tooling normalizes them (Node, git).
- Write text files as UTF-8 without BOM. `Out-File`/`>` in Windows PowerShell 5.1
  default to UTF-16LE — always pass `-Encoding utf8` or use another tool when a
  file will be consumed by cross-platform tooling.

## npm Scripts and CI

- `package.json` scripts and CI steps MUST be cross-platform. Prefer Node-based
  script files (`node scripts/x.mjs`) over inline shell when logic is non-trivial.
- Never require a developer to hand-edit their shell profile to work on the repo.

## Rationale

Mixed shell conventions caused repeated CI/local divergence (pinned Next.js +
pnpm stack on this machine is Windows-hosted). One shell dialect, stated once,
applied everywhere.
