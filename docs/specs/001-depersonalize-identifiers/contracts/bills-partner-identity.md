# Contract: Bills Partner Identity (schema_version 5)

**Applies to**: `data/private/bills_dashboard_{month}.json` snapshots and the bills read API (`src/budget_api/routers/bills.py`).
**Problem being fixed**: today the display label from config is the ONLY partner identifier in the payload (`bills_builder._partner_label()` at :163-166; `BillsEvent.partner: str`, `PartnerBills.partner: str`), and six+ client components do `partner === "Christian"` for color/filter/pivot logic — an LG-007 violation and a personal identifier hardcoded in tracked source.

## Payload delta (additive, defaults — repo compat convention)

| Location | Addition |
|---|---|
| `BillsEvent` | `partner_id: str = ""` — arbitrary stable id (pure passthrough of the `account_mappings.json` partner key); plus `partner_slot: "a" \| "b" \| ""` — BE-assigned deterministic style/order slot (sorted `partner_id` order); slots are capped at two — a hypothetical third+ partner degrades to the neutral slot `""` (still keyed by `partner_id`) |
| `PartnerBills` (per-month partner block) | `partner_id: str = ""` and `partner_slot: str = ""` — same |
| snapshot root | `schema_version: 4 → 5` |

The label field `partner` remains (render-only). The builder stamps `partner_id` from the internal `partner_id` it already threads through (`_all_partner_ids`, `bills_builder.py:169-172`) — a passthrough, not a derivation — and computes `partner_slot` once, centrally, from sorted `partner_id` order so every consumer sees identical slots.

## Read API delta

```text
GET /api/bills/dashboard/events?partner_id=partner_a
```

- `partner_id` filter parameter REPLACES the label-based `partner` parameter for new clients; matching by exact partner id, case-sensitive.
- The legacy label parameter, if still received, is matched exactly as before for one deprecation cycle, but the shipped client no longer sends it. Sort ties key on `partner_id`.

## Client contract

- Identity/grouping/filter logic (query params, filter state, event grouping) keys on `partner_id`; order/styling logic (CSS class `bg-partner-a`/`bg-partner-b`, sparkline colors, series position) keys on `partner_slot` — **never** on the display string and never on an array position read client-side.
- Display strings come from the same payload's label field (render-only) or from `partner_labels` in report payloads.
- `F2Partner = "Christian" | "Rasma"` (`client/src/types/api.ts:113`) is deleted; the type becomes `{ partner_id: string; partner_slot: "a" | "b"; label: string }`.

## Legacy snapshot handling

Schema-4 snapshots (no `partner_id`/`partner_slot`) remain readable — the bills router never 500s on old files (repo convention) — but their partner identity is **not recoverable safely**: the per-month `partners[]` array order in legacy payloads is insertion order (`_all_partner_ids()` returns mapping keys unsorted), so any positional inference can silently swap the two partners' rows, colors, and pivots on re-render. The client therefore renders schema-4 snapshots in **identity-neutral mode**: single neutral color for partner-scoped series, partner filter hidden, and a "regenerate to restore per-partner view" hint. Positional identity inference is explicitly forbidden; regenerating (re-sync) is the only path that populates real ids/slots. `??`-guards stay for shape compat. Because the labels in old snapshots may be the old household's names, the LG-004 local-artifact purge covers them pre-launch regardless.

## Tests that pin this contract

- Builder unit test: emitted events/partner blocks carry `partner_id` alongside `partner`; `partner_slot` is the sorted-id slot.
- Router test: `?partner_id=` filtering returns only that partner's events.
- Client tests: color/filter logic driven by `partner_slot`/`partner_id`; a renamed label does not change attribution (the regression LG-007 exists to prevent).
- Snapshot model test: schema-4 JSON deserializes with `partner_id == ""` defaults (no 500, no crash) and renders in identity-neutral mode (no partner-color classes, no partner filter).
- Legacy-order regression test: a schema-4 snapshot whose `partners[]` insertion order is `[second_id, first_id]` renders identically to one with `[first_id, second_id]` — i.e., no positional identity inference exists.
