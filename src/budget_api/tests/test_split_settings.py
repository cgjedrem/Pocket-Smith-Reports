"""Common-economy split settings tests — GET/PUT /api/settings/split,
category-level selection (Gate 2 evolution).

Covers default-off response (missing config, empty categories/sections),
successful PUT + persisted round-trip with `categories`, 422 on shares not
summing to 100, 400 on unknown category ID / out-of-range share, legacy
on-disk sections-only config auto-translating on GET, `sections` always
server-derived (never trusted verbatim from disk), and atomic file write
shape.

`write_categories` fixture (conftest) seeds category_catalog.json with a
nested int-ID tree (100/110/111/120/200) — load_category_parents
stringifies these, so category IDs in this file's JSON bodies are the
string forms ("110", "200", etc).
"""

from __future__ import annotations

import json
from pathlib import Path

from budget_api.services import storage

DETAILED_SECTION_MAPPING = {
    "category_sections": {"110": "home", "200": "common"},
    "account_roles": {},
}


def _write_detailed_section_mapping(tmp_private_dir: Path) -> None:
    (tmp_private_dir / "detailed_section_mapping.json").write_text(
        json.dumps(DETAILED_SECTION_MAPPING), encoding="utf-8"
    )


class TestGetSplitConfig:
    def test_missing_file_returns_default_off(self, client, tmp_private_dir: Path):
        resp = client.get("/api/settings/split")
        assert resp.status_code == 200
        assert resp.json() == {
            "enabled": False,
            "shares": {"partner_a": 50.0, "partner_b": 50.0},
            "categories": [],
            "sections": [],
            "labels": {"partner_a": "Partner A", "partner_b": "Partner B"},
            "warning": None,
        }
        # Never written to disk just by reading.
        assert not (tmp_private_dir / "split_config.json").exists()

    def test_reads_persisted_categories_config(self, client, tmp_private_dir: Path):
        """No detailed_section_mapping.json on disk -> sections can't be
        derived -> []. categories is still the source of truth returned
        as-is."""
        (tmp_private_dir / "split_config.json").write_text(
            json.dumps(
                {
                    "enabled": True,
                    "shares": {"partner_a": 60.0, "partner_b": 40.0},
                    "categories": ["110", "200"],
                }
            ),
            encoding="utf-8",
        )
        resp = client.get("/api/settings/split")
        assert resp.status_code == 200
        assert resp.json() == {
            "enabled": True,
            "shares": {"partner_a": 60.0, "partner_b": 40.0},
            "categories": ["110", "200"],
            "sections": [],
            "labels": {"partner_a": "Partner A", "partner_b": "Partner B"},
            "warning": None,
        }

    def test_sections_derived_from_categories_not_trusted_from_disk(
        self, client, tmp_private_dir: Path
    ):
        """A stale/wrong `sections` value on disk is ignored — GET always
        recomputes it from `categories` via the detailed section mapping."""
        _write_detailed_section_mapping(tmp_private_dir)
        (tmp_private_dir / "split_config.json").write_text(
            json.dumps(
                {
                    "enabled": True,
                    "shares": {"partner_a": 50.0, "partner_b": 50.0},
                    "categories": ["110", "200"],
                    "sections": ["this-is-stale-and-wrong"],
                }
            ),
            encoding="utf-8",
        )
        resp = client.get("/api/settings/split")
        assert resp.status_code == 200
        assert resp.json()["sections"] == ["home", "common"]

    def test_legacy_sections_only_config_translates_on_read(
        self, client, tmp_private_dir: Path
    ):
        """Pre-category-picker on-disk file (only `sections`, no
        `categories` key) is auto-translated via the leaf mapping on
        every GET — categories becomes the equivalent category-ID set,
        sections is (re-)derived from that."""
        _write_detailed_section_mapping(tmp_private_dir)
        (tmp_private_dir / "split_config.json").write_text(
            json.dumps(
                {
                    "enabled": True,
                    "shares": {"partner_a": 50.0, "partner_b": 50.0},
                    "sections": ["home"],
                }
            ),
            encoding="utf-8",
        )
        resp = client.get("/api/settings/split")
        assert resp.status_code == 200
        body = resp.json()
        assert body["categories"] == ["110"]
        assert body["sections"] == ["home"]

    def test_legacy_sections_only_config_missing_mapping_no_data_loss(
        self, client, tmp_private_dir: Path
    ):
        """IMPORTANT fix (iteration 4, finding 2): detailed_section_mapping
        or {} previously made this silently translate to categories=[],
        sections=[] on GET — indistinguishable from the user having
        deselected everything. No detailed_section_mapping.json seeded
        here (stale/absent sidecar file) — GET must instead surface the
        saved legacy sections as-is + a machine-readable warning, not lose
        the selection. Report-build time keeps the stricter raise (see
        v4_pipeline/tests/test_split.py::
        test_legacy_sections_without_mapping_raises) — that path computes
        real settlement numbers, so silently degrading there would be a
        silent miscalculation, not just a display gap."""
        (tmp_private_dir / "split_config.json").write_text(
            json.dumps(
                {
                    "enabled": True,
                    "shares": {"partner_a": 50.0, "partner_b": 50.0},
                    "sections": ["home", "trips"],
                }
            ),
            encoding="utf-8",
        )
        resp = client.get("/api/settings/split")
        assert resp.status_code == 200
        body = resp.json()
        assert body["categories"] == []
        assert body["sections"] == ["home", "trips"]  # preserved as-is
        assert body["warning"] is not None
        assert "detailed_section_mapping.json" in body["warning"]

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
                "categories": ["110"],
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
                "categories": ["110", "200"],
            },
        )
        assert resp.status_code == 200
        assert resp.json() == {
            "enabled": True,
            "shares": {"partner_a": 55.0, "partner_b": 45.0},
            "categories": ["110", "200"],
            "sections": [],  # no detailed_section_mapping.json on disk yet
        }
        on_disk = json.loads(
            (tmp_private_dir / "split_config.json").read_text(encoding="utf-8")
        )
        assert on_disk == resp.json()
        # GET reflects the same persisted config (+ additive display-only
        # labels/warning the PUT response doesn't carry — see
        # TestGetSplitConfig).
        get_body = client.get("/api/settings/split").json()
        assert "labels" not in resp.json()
        assert {
            k: v for k, v in get_body.items() if k not in ("labels", "warning")
        } == resp.json()

    def test_valid_update_derives_sections_when_mapping_present(
        self, client, tmp_private_dir: Path
    ):
        _write_detailed_section_mapping(tmp_private_dir)
        resp = client.put(
            "/api/settings/split",
            json={
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": ["110", "200"],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["sections"] == ["home", "common"]

    def test_disabling_still_validates_shares(self, client, tmp_private_dir: Path):
        """enabled=False still requires a valid shares/categories shape —
        the stored config stays coherent for whenever it's re-enabled."""
        resp = client.put(
            "/api/settings/split",
            json={
                "enabled": False,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": [],
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
                "categories": ["110"],
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
                "categories": ["110"],
            },
        )
        assert resp.status_code == 200

    def test_unknown_category_id_rejected_400(
        self, client, tmp_private_dir: Path, write_categories: Path
    ):
        resp = client.put(
            "/api/settings/split",
            json={
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": ["110", "does-not-exist"],
            },
        )
        assert resp.status_code == 400
        assert "does-not-exist" in resp.json()["detail"]
        assert not (tmp_private_dir / "split_config.json").exists()

    def test_unknown_category_id_skipped_when_no_catalog_on_disk(
        self, client, tmp_private_dir: Path
    ):
        """No category_catalog.json yet (fresh install) -> nothing to
        validate against, same permissive stance normalize_split_config
        takes — PUT still succeeds."""
        resp = client.put(
            "/api/settings/split",
            json={
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": ["anything-goes"],
            },
        )
        assert resp.status_code == 200

    def test_valid_category_id_accepted_with_catalog_present(
        self, client, tmp_private_dir: Path, write_categories: Path
    ):
        resp = client.put(
            "/api/settings/split",
            json={
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": ["110", "200"],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["categories"] == ["110", "200"]

    def test_duplicate_categories_deduped_preserving_order(
        self, client, tmp_private_dir: Path
    ):
        resp = client.put(
            "/api/settings/split",
            json={
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": ["200", "110", "200"],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["categories"] == ["200", "110"]

    def test_share_out_of_range_rejected_400(self, client, tmp_private_dir: Path):
        resp = client.put(
            "/api/settings/split",
            json={
                "enabled": True,
                "shares": {"partner_a": 150.0, "partner_b": -50.0},
                "categories": [],
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
                b'"partner_b": 50.0}, "categories": ["110"]}'
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
                b'"partner_b": 50.0}, "categories": ["110"]}'
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
                b'"partner_b": 50.0}, "categories": ["110"]}'
            ),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        assert "finite" in resp.json()["detail"]
        assert not (tmp_private_dir / "split_config.json").exists()

    def test_missing_field_400(self, client, tmp_private_dir: Path):
        """Pydantic 422 -> custom app-level handler -> 400 (missing shares)."""
        resp = client.put(
            "/api/settings/split", json={"enabled": True, "categories": []}
        )
        assert resp.status_code == 400

    def test_atomic_write_json_shape(self, client, tmp_private_dir: Path):
        _write_detailed_section_mapping(tmp_private_dir)
        client.put(
            "/api/settings/split",
            json={
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": ["200"],
            },
        )
        raw = storage.read_json(storage.SPLIT_CONFIG_PATH)
        assert raw == {
            "enabled": True,
            "shares": {"partner_a": 50.0, "partner_b": 50.0},
            "categories": ["200"],
            "sections": ["common"],
        }
