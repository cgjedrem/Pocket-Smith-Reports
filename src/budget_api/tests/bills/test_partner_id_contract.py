"""T045 bills partner_id/partner_slot contract tests.

Covers:
- builder emits additive partner_id + partner_slot (schema-5)
- router ?partner_id= filtering (+ supersede rule over legacy ?partner=)
- schema-4 snapshots deserialize with partner_id == "" defaults (no crash)
- legacy-order regression: reversed partners[] insertion order renders
  identically for both schema-4 (label tiebreak fallback) and schema-5
  (partner_id tiebreak) snapshots — no positional identity inference
"""

from __future__ import annotations

from budget_api.models.bills import BillsSnapshot
from budget_api.services import storage

from .test_events import _valid_event, _valid_snapshot_with_events, _write_snapshot


def _schema5_events() -> dict[str, list[dict]]:
    return {
        "Fixture A": [
            {
                **_valid_event(id="a1", date="2026-07-10", partner="Fixture A"),
                "partner_id": "partner_a",
                "partner_slot": "a",
            },
            {
                **_valid_event(id="a2", date="2026-07-15", type="salary", partner="Fixture A"),
                "partner_id": "partner_a",
                "partner_slot": "a",
            },
        ],
        "Fixture B": [
            {
                **_valid_event(id="b1", date="2026-07-10", partner="Fixture B"),
                "partner_id": "partner_b",
                "partner_slot": "b",
            },
        ],
    }


class TestPartnerIdFilter:
    def test_partner_id_filters_schema5_events(self, client, tmp_private_dir):
        payload = _valid_snapshot_with_events("2026-07", _schema5_events())
        payload["schema_version"] = 5
        _write_snapshot(tmp_private_dir, "2026-07", payload)
        response = client.get(
            "/api/bills/dashboard/events",
            params={"month": "2026-07", "partner_id": "partner_a"},
        )
        assert response.status_code == 200
        ids = [e["id"] for e in response.json()["events"]]
        assert ids == ["a1", "a2"]

    def test_partner_id_supersedes_legacy_label_param(self, client, tmp_private_dir):
        """Both params sent, conflicting → partner_id wins (deprecation cycle)."""
        payload = _valid_snapshot_with_events("2026-07", _schema5_events())
        payload["schema_version"] = 5
        _write_snapshot(tmp_private_dir, "2026-07", payload)
        response = client.get(
            "/api/bills/dashboard/events",
            params={"month": "2026-07", "partner": "Fixture B", "partner_id": "partner_a"},
        )
        assert response.status_code == 200
        ids = [e["id"] for e in response.json()["events"]]
        assert ids == ["a1", "a2"]

    def test_partner_id_on_schema4_snapshot_empty_not_500(self, client, tmp_private_dir):
        """Old snapshots carry no partner_id → filter yields zero rows, no crash."""
        payload = _valid_snapshot_with_events(
            "2026-07",
            {"Fixture A": [_valid_event(id="c1", partner="Fixture A")]},
        )
        _write_snapshot(tmp_private_dir, "2026-07", payload)
        response = client.get(
            "/api/bills/dashboard/events",
            params={"month": "2026-07", "partner_id": "partner_a"},
        )
        assert response.status_code == 200
        assert response.json() == {"events": [], "total": 0}


class TestLegacyOrderRegression:
    def test_schema4_reversed_partners_render_identically(self, client, tmp_private_dir):
        """Swapping partners[] insertion order must not change the response."""
        events = {
            "Fixture A": [_valid_event(id="a1", date="2026-07-10", partner="Fixture A")],
            "Fixture B": [_valid_event(id="b1", date="2026-07-10", partner="Fixture B")],
        }
        forward = _valid_snapshot_with_events("2026-07", events)
        reversed_ = _valid_snapshot_with_events("2026-07", dict(reversed(list(events.items()))))
        _write_snapshot(tmp_private_dir, "2026-07", forward)
        r1 = client.get("/api/bills/dashboard/events", params={"month": "2026-07"})
        _write_snapshot(tmp_private_dir, "2026-07", reversed_)
        r2 = client.get("/api/bills/dashboard/events", params={"month": "2026-07"})
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json() == r2.json()

    def test_schema5_reversed_partners_render_identically(self, client, tmp_private_dir):
        events = _schema5_events()
        forward = _valid_snapshot_with_events("2026-07", events)
        forward["schema_version"] = 5
        reversed_ = _valid_snapshot_with_events("2026-07", dict(reversed(list(events.items()))))
        reversed_["schema_version"] = 5
        _write_snapshot(tmp_private_dir, "2026-07", forward)
        r1 = client.get("/api/bills/dashboard/events", params={"month": "2026-07"})
        _write_snapshot(tmp_private_dir, "2026-07", reversed_)
        r2 = client.get("/api/bills/dashboard/events", params={"month": "2026-07"})
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json() == r2.json()


class TestSchema4Defaults:
    def test_schema4_deserializes_with_empty_partner_id(self):
        """BillsSnapshot on a pre-field payload → partner_id/partner_slot default."""
        payload = _valid_snapshot_with_events(
            "2026-07",
            {"Fixture A": [_valid_event(id="c1", partner="Fixture A")]},
        )
        payload["schema_version"] = 4
        snapshot = BillsSnapshot.model_validate(payload)
        assert snapshot.schema_version == 4
        assert snapshot.partners[0].partner_id == ""
        assert snapshot.partners[0].partner_slot == ""
        assert snapshot.partners[0].events[0].partner_id == ""

    def test_schema5_roundtrip_keeps_ids(self):
        payload = _valid_snapshot_with_events("2026-07", _schema5_events())
        payload["schema_version"] = 5
        slots = {"Fixture A": ("partner_a", "a"), "Fixture B": ("partner_b", "b")}
        for block in payload["partners"]:
            pid, slot = slots[block["partner"]]
            block["partner_id"] = pid
            block["partner_slot"] = slot
        snapshot = BillsSnapshot.model_validate(payload)
        by_id = {p.partner_id: p for p in snapshot.partners}
        assert by_id["partner_a"].partner_slot == "a"
        assert by_id["partner_b"].partner_slot == "b"
