"""Common-economy split settings tests — GET/PUT /api/settings/split.

Covers default-off response (missing config), successful PUT + persisted
round-trip, 422 on shares not summing to 100, 400 on unknown section /
out-of-range share, and atomic file write shape.
"""

from __future__ import annotations

import json
from pathlib import Path

from budget_api.services import storage


class TestGetSplitConfig:
    def test_missing_file_returns_default_off(self, client, tmp_private_dir: Path):
        resp = client.get("/api/settings/split")
        assert resp.status_code == 200
        assert resp.json() == {
            "enabled": False,
            "shares": {"partner_a": 50.0, "partner_b": 50.0},
            "sections": ["home", "common", "trips"],
            "labels": {"partner_a": "Partner A", "partner_b": "Partner B"},
        }
        # Never written to disk just by reading.
        assert not (tmp_private_dir / "split_config.json").exists()

    def test_reads_persisted_config(self, client, tmp_private_dir: Path):
        (tmp_private_dir / "split_config.json").write_text(
            json.dumps(
                {
                    "enabled": True,
                    "shares": {"partner_a": 60.0, "partner_b": 40.0},
                    "sections": ["home", "trips"],
                }
            ),
            encoding="utf-8",
        )
        resp = client.get("/api/settings/split")
        assert resp.status_code == 200
        assert resp.json() == {
            "enabled": True,
            "shares": {"partner_a": 60.0, "partner_b": 40.0},
            "sections": ["home", "trips"],
            "labels": {"partner_a": "Partner A", "partner_b": "Partner B"},
        }

    def test_custom_id_household_labels_resolved(self, client, tmp_private_dir: Path):
        """IMPORTANT fix (iteration 4, finding 5): the settings UI can't
        resolve slot->real-name labels from listPartners() alone (its keys
        are real IDs, e.g. "alex"/"sam", never slot names). GET now
        additionally resolves real labels via the same
        _partner_slot_map + label-loader path report_builder uses (sorted
        custom IDs -> partner_a/partner_b: "alex" < "sam" -> alex=partner_a).
        labels are display-only — never written into split_config.json.
        """
        (tmp_private_dir / "account_mappings.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "partners": {
                        "alex": {"label": "Alex"},
                        "sam": {"label": "Sam"},
                    },
                    "accounts": {},
                }
            ),
            encoding="utf-8",
        )
        resp = client.get("/api/settings/split")
        assert resp.status_code == 200
        body = resp.json()
        assert body["labels"] == {"partner_a": "Alex", "partner_b": "Sam"}
        # Enabling + persisting still doesn't leak labels onto disk.
        put_resp = client.put(
            "/api/settings/split",
            json={
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "sections": ["home"],
            },
        )
        assert put_resp.status_code == 200
        on_disk = json.loads(
            (tmp_private_dir / "split_config.json").read_text(encoding="utf-8")
        )
        assert "labels" not in on_disk
        # GET after PUT still resolves labels fresh (not from the write).
        assert client.get("/api/settings/split").json()["labels"] == {
            "partner_a": "Alex",
            "partner_b": "Sam",
        }

    def test_corrupt_file_returns_500(self, client, tmp_private_dir: Path):
        (tmp_private_dir / "split_config.json").write_text(
            "{not valid json", encoding="utf-8"
        )
        resp = client.get("/api/settings/split")
        assert resp.status_code == 500


class TestUpdateSplitConfig:
    def test_valid_update_200_and_persisted(self, client, tmp_private_dir: Path):
        resp = client.put(
            "/api/settings/split",
            json={
                "enabled": True,
                "shares": {"partner_a": 55.0, "partner_b": 45.0},
                "sections": ["home", "common"],
            },
        )
        assert resp.status_code == 200
        assert resp.json() == {
            "enabled": True,
            "shares": {"partner_a": 55.0, "partner_b": 45.0},
            "sections": ["home", "common"],
        }
        on_disk = json.loads(
            (tmp_private_dir / "split_config.json").read_text(encoding="utf-8")
        )
        assert on_disk == resp.json()
        # GET reflects the same persisted config (+ additive display-only
        # labels the PUT response doesn't carry — see TestGetSplitConfig).
        get_body = client.get("/api/settings/split").json()
        assert "labels" not in resp.json()
        assert {k: v for k, v in get_body.items() if k != "labels"} == resp.json()

    def test_disabling_still_validates_shares(self, client, tmp_private_dir: Path):
        """enabled=False still requires a valid shares/sections shape — the
        stored config stays coherent for whenever it's re-enabled."""
        resp = client.put(
            "/api/settings/split",
            json={
                "enabled": False,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "sections": [],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def test_shares_not_summing_to_100_rejected_422(self, client, tmp_private_dir: Path):
        resp = client.put(
            "/api/settings/split",
            json={
                "enabled": True,
                "shares": {"partner_a": 60.0, "partner_b": 30.0},
                "sections": ["home"],
            },
        )
        assert resp.status_code == 422
        assert "sum to exactly 100" in resp.json()["detail"]
        assert not (tmp_private_dir / "split_config.json").exists()

    def test_shares_sum_within_tolerance_accepted(self, client, tmp_private_dir: Path):
        resp = client.put(
            "/api/settings/split",
            json={
                "enabled": True,
                "shares": {"partner_a": 50.0000001, "partner_b": 49.9999999},
                "sections": ["home"],
            },
        )
        assert resp.status_code == 200

    def test_unknown_section_rejected_400(self, client, tmp_private_dir: Path):
        resp = client.put(
            "/api/settings/split",
            json={
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "sections": ["home", "personal_partner_a"],
            },
        )
        assert resp.status_code == 400
        assert "personal_partner_a" in resp.json()["detail"]
        assert not (tmp_private_dir / "split_config.json").exists()

    def test_share_out_of_range_rejected_400(self, client, tmp_private_dir: Path):
        resp = client.put(
            "/api/settings/split",
            json={
                "enabled": True,
                "shares": {"partner_a": 150.0, "partner_b": -50.0},
                "sections": [],
            },
        )
        assert resp.status_code == 400

    def test_nan_share_rejected_400(self, client, tmp_private_dir: Path):
        """Regression (iteration 4 CRITICAL fix): NaN compares false in
        every range/sum check (`NaN < 0` / `NaN > 100` / `abs(NaN - 100) >
        1e-6` are all False), so a bare comparison-based validator lets a
        NaN share through to a 200 + persisted NaN. Python's stdlib `json`
        parses the (non-standard-JSON) `NaN` literal by default, and
        httpx/FastAPI don't reject it upstream — the app-level validator
        must catch it. Raw body used because httpx's `json=` kwarg would
        reject a NaN float before it ever reaches the wire."""
        resp = client.put(
            "/api/settings/split",
            content=(
                b'{"enabled": true, "shares": {"partner_a": NaN, '
                b'"partner_b": 50.0}, "sections": ["home"]}'
            ),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        assert "finite" in resp.json()["detail"]
        assert not (tmp_private_dir / "split_config.json").exists()

    def test_infinity_share_rejected_400(self, client, tmp_private_dir: Path):
        resp = client.put(
            "/api/settings/split",
            content=(
                b'{"enabled": true, "shares": {"partner_a": Infinity, '
                b'"partner_b": 50.0}, "sections": ["home"]}'
            ),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        assert "finite" in resp.json()["detail"]
        assert not (tmp_private_dir / "split_config.json").exists()

    def test_negative_infinity_share_rejected_400(self, client, tmp_private_dir: Path):
        resp = client.put(
            "/api/settings/split",
            content=(
                b'{"enabled": true, "shares": {"partner_a": -Infinity, '
                b'"partner_b": 50.0}, "sections": ["home"]}'
            ),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        assert "finite" in resp.json()["detail"]
        assert not (tmp_private_dir / "split_config.json").exists()

    def test_missing_field_400(self, client, tmp_private_dir: Path):
        """Pydantic 422 -> custom app-level handler -> 400 (missing shares)."""
        resp = client.put("/api/settings/split", json={"enabled": True, "sections": []})
        assert resp.status_code == 400

    def test_atomic_write_json_shape(self, client, tmp_private_dir: Path):
        client.put(
            "/api/settings/split",
            json={
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "sections": ["common"],
            },
        )
        raw = storage.read_json(storage.SPLIT_CONFIG_PATH)
        assert raw == {
            "enabled": True,
            "shares": {"partner_a": 50.0, "partner_b": 50.0},
            "sections": ["common"],
        }
