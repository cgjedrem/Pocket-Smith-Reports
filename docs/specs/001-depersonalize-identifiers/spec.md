# Feature Specification: De-personalize identifiers for open-source launch

**Feature Branch**: `001-depersonalize-identifiers`

**Created**: 2026-09-16

**Status**: Draft

**Input**: User description: "Bring the repository to open-source readiness by removing personal identifiers from all tracked code, API contracts, fixtures, and user-facing strings. Display names must come from user-local configuration. Delivered as a visibly breaking internal API revision."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Repository contains no personal identifiers (Priority: P1)

As the maintainer preparing this repository for public release, I need every
tracked file — source code, API contracts, test fixtures, and user-facing
strings — free of personal identifiers (names, initials tied to specific
people), so that publishing the repository does not expose the household's
private identities.

**Why this priority**: This is the blocking condition for going open-source.
Without it the repository cannot be made public. Everything else about the
launch is gated on this property holding end to end.

**Independent Test**: Running a text search over tracked files (the entire
versioned tree) for each known personal identifier returns zero matches, while
the application still builds, all automated tests pass, and a generated report
displays partner labels resolved from configuration.

**Acceptance Scenarios**:

1. **Given** a clean checkout of the repository, **When** I search all tracked
   files for each personal identifier on the removal list, **Then** zero
   matches are found.
2. **Given** the de-personalized codebase with a user-local partner-label
   configuration present, **When** the application runs end to end, **Then**
   the configured names appear where partner identity is displayed and the
   tracked tree still contains no personal identifiers.
3. **Given** the de-personalized codebase with NO partner-label configuration
   (first run by a new user), **When** the application runs, **Then** neutral
   placeholder identities are displayed — never the original household's names.

---

### User Story 2 - Partner identity is configuration-driven (Priority: P2)

As a new user adopting this tool for my own household, I need to enter my own
partner names (or labels) once through configuration, and have every report,
dashboard, and section of the app reflect my choices — with no hardcoded names
and no code edits required.

**Why this priority**: P1 removes the old identities; P2 proves the tool is
genuinely usable by someone else. De-personalization that still leaves display
identity wired to two specific people would fail the open-source goal.

**Independent Test**: Configure two arbitrary, distinct partner labels via the
existing settings/configuration surface; generate a report and open the
dashboards; confirm both labels appear correctly in every partner-scoped
surface without modifying any tracked file.

**Acceptance Scenarios**:

1. **Given** a fresh setup with my own partner labels configured, **When** I
   generate a monthly report, **Then** all partner-scoped sections and column
   headers use my labels.
2. **Given** configured partner labels, **When** I open the bills dashboard and
   monthly reports views, **Then** no view displays the placeholder defaults
   and no view displays the original household's names.

---

### User Story 3 - Breaking change is discoverable and deliberate (Priority: P3)

As the maintainer, I need the rename of the stored/report contract to be a
deliberately visible breaking change: old stored data must not silently
misroute transactions, and the breakage/upgrade path must be obvious to anyone
running the app against pre-change data.

**Why this priority**: A silent failure that mislabels or misfiles someone's
transactions would be worse than an explicit break. Pre-change stored reports
are local-only and regenerable from source data, so an explicit break with an
obvious remedy is acceptable and preferred over hidden data corruption.

**Independent Test**: Point the new code at a stored report produced by the
pre-change code; confirm it fails loudly and clearly (not silently mislabels
rows), and that regenerating from source data produces a correct new-contract
report.

**Acceptance Scenarios**:

1. **Given** a report stored before the change, **When** the new application
   reads it, **Then** it either rejects it with a clear signal or regenerates
   it — it never renders the old personal sections as if they were still valid.
2. **Given** a pre-change stored report, **When** I trigger regeneration from
   source transactions, **Then** the resulting report validates against the
   new contract and renders fully.

---

## Edge Cases

- **No configuration present**: a first-time user has no partner labels file.
  The app must fall back to neutral placeholder identities (e.g., "Partner
  A"/"Partner B"), not the original household's names and not empty strings.
- **One-vs-two partner labels**: a household may have fewer than two partners
  configured. Surfaces built around exactly two partner columns must degrade
  gracefully rather than render the placeholder for a missing partner as if
  real.
- **Stored pre-change data**: existing local stored reports reference the old
  personal-section keys. The system must not silently render them under the
  new contract; regeneration is the remedy.
- **User-facing placeholder text that merely resembles a personal name**:
  placeholder/example values in fixtures and tests must be clearly synthetic
  (e.g., "Fixture A") and must not collide with any real person's name.
- **Configuration that itself contains personal identifiers**: configuration
  files are user-local and untracked; the requirement applies to the tracked
  tree, not to what a user types into their own config.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The tracked repository tree (source, contracts, fixtures, and
  in-app user-facing strings) MUST contain zero occurrences of any identifier
  on the agreed personal-identifier removal list.
- **FR-002**: All partner display names shown in reports, dashboards, and the
  UI MUST be resolved from user-local configuration, never hardcoded in
  tracked source.
- **FR-003**: When no partner-label configuration exists, the system MUST use
  neutral placeholder partner identities (not any prior household's names).
- **FR-004**: All identifiers internal to data contracts — section keys,
  enum/allow-list values, DTO fields, and fixture rows — that currently encode
  personal names MUST be replaced with partner-neutral identifiers.
- **FR-005**: The replacement MUST be applied consistently across every
  module that shares the contract, so no module writes a key another module
  does not read.
- **FR-006**: The change MUST be delivered as a knowingly breaking internal
  API/contract revision and MUST NOT silently coerce pre-change stored data
  into the new contract; the remedy is explicit regeneration from source data.
- **FR-007**: Tracked fixtures and test data MUST use clearly synthetic
  categories, payees, and owners, with no realistic personal names.
- **FR-008**: The full automated test suite MUST pass after the change without
  relaxing or deleting assertions; tests updated to the new identifiers MUST
  assert equivalent or stronger behavior.

### Key Entities *(include if feature involves data)*

- **Partner label**: a user-supplied display name for one member of the
  household, stored in user-local untracked configuration and surfaced in the
  UI; keyed by a stable partner-neutral identifier (e.g., first partner,
  second partner).
- **Personal-section key**: a stable, partner-neutral section identifier used
  across the report contract and stored data to identify each partner's
  personal-spending section; must not encode any person's name.
- **Stored report**: a persisted, user-local report artifact; its historical
  payloads contain old personal-section keys and are out of compatibility
  after this change (regeneration is the supported path).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A text search over all tracked files for every personal
  identifier on the removal list returns zero matches, verified from a clean
  checkout.
- **SC-002**: The complete automated test suite (backend and frontend) passes
  with the new identifiers, with no tests deleted or assertions weakened.
- **SC-003**: Configuring two arbitrary partner labels and running the app end
  to end shows both labels correctly on every partner-scoped surface, with no
  code changes.
- **SC-004**: Reading a pre-change stored report with the new code produces an
  explicit, understandable failure or a regeneration — never silently
  mislabeled content.
- **SC-005**: A first run with no partner-label configuration renders the
  neutral placeholders on partner-scoped surfaces and never the original
  household's names.

## Assumptions

- The list of personal identifiers to remove is the household's two personal
  names (in all casings), plus any code identifiers derived from them; an
  evidence pass confirms the final list before implementation.
- User-local configuration and stored data under the private data directory
  are untracked and out of scope for the tracked-tree requirement; their
  contents are the user's own.
- Git history will retain the old identifiers as historical commits for now;
  whether to scrub history is a separate launch-time decision and is out of
  scope for this feature.
- Partner display identity is strictly configuration-driven; no tracked file
  needs to "know" who the users are.
- Regenerating a report from source transactions is an available, working
  operation, so "regenerate" is a viable remedy for the breaking change.
