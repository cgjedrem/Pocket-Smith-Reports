import importlib.util
import json
import sys
from pathlib import Path

import pytest

LIVE_SYNC = Path(__file__).resolve().parents[2] / "live_sync.py"


def _load_live_sync():
    spec = importlib.util.spec_from_file_location("live_sync", LIVE_SYNC)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _set_private_paths(monkeypatch: pytest.MonkeyPatch, live_sync, tmp_path: Path):
    monkeypatch.setattr(live_sync, "PRIVATE_DATA_DIR", tmp_path)
    monkeypatch.setattr(
        live_sync, "ACCOUNT_CATALOG_PATH", tmp_path / "account_catalog.json"
    )
    monkeypatch.setattr(
        live_sync, "CATEGORY_CATALOG_PATH", tmp_path / "category_catalog.json"
    )
    monkeypatch.setattr(
        live_sync, "ACCOUNT_MAPPING_PATH", tmp_path / "account_mappings.json"
    )


def _write_account_mapping(tmp_path: Path, accounts: dict[str, dict]):
    (tmp_path / "account_mappings.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "partners": {
                    "partner_a": {"label": "Alex"},
                    "partner_b": {"label": "Blair"},
                },
                "accounts": accounts,
            }
        ),
        encoding="utf-8",
    )


def _valid_account_mapping() -> dict:
    return {
        "schema_version": 1,
        "partners": {
            "partner_a": {"label": "Alex"},
            "partner_b": {"label": "Blair"},
        },
        "accounts": {"a": {"name": "A", "owner": "partner_a", "excluded": False}},
    }


def test_accounts_stage_saves_only_accounts_active_in_requested_period(
    tmp_path, monkeypatch
):
    live_sync = _load_live_sync()
    _set_private_paths(monkeypatch, live_sync, tmp_path)
    accounts = [
        {"id": "active", "name": "Active"},
        {"id": "inactive", "name": "Inactive"},
    ]
    monkeypatch.setattr(live_sync, "_accounts", lambda *_args: accounts)
    monkeypatch.setattr(
        live_sync,
        "ps_get_paginated",
        lambda path, *_args: [{"id": "txn"}] if "/active/" in path else [],
    )

    catalog = live_sync.run_accounts_stage("2026-04", "2026-05", "key", "user")

    assert catalog["accounts"] == [accounts[0]]
    assert json.loads((tmp_path / "account_catalog.json").read_text()) == catalog
    assert not list(tmp_path.glob("*_ps_raw.json"))


def test_categories_stage_saves_private_catalog(tmp_path, monkeypatch):
    live_sync = _load_live_sync()
    _set_private_paths(monkeypatch, live_sync, tmp_path)
    categories = [{"id": "food", "title": "Food"}]
    monkeypatch.setattr(live_sync, "ps_get", lambda *_args: categories)

    catalog = live_sync.run_categories_stage("2026-04", "2026-04", "key", "user")

    assert catalog == {"start": "2026-04", "end": "2026-04", "categories": categories}
    assert json.loads((tmp_path / "category_catalog.json").read_text()) == catalog


def test_transaction_stage_requires_complete_valid_account_maps_before_fetch(
    tmp_path, monkeypatch
):
    live_sync = _load_live_sync()
    _set_private_paths(monkeypatch, live_sync, tmp_path)
    (tmp_path / "account_catalog.json").write_text(
        json.dumps({"start": "2026-04", "end": "2026-04", "accounts": [{"id": "a"}]})
    )
    (tmp_path / "category_catalog.json").write_text(
        json.dumps({"start": "2026-04", "end": "2026-04", "categories": []})
    )
    _write_account_mapping(
        tmp_path, {"a": {"name": "A", "owner": "partner_a", "excluded": False}}
    )
    monkeypatch.setattr(
        live_sync, "ps_get_paginated", lambda *_args: pytest.fail("fetch before gate")
    )

    with pytest.raises(live_sync.LiveSyncError, match="names must match"):
        live_sync.run_transactions_stage("2026-04", "2026-04", "key", "user")

    assert not list(tmp_path.glob("*_ps_raw.json"))


def test_transaction_stage_rejects_duplicate_catalog_ids_before_map_or_fetch(
    tmp_path, monkeypatch
):
    live_sync = _load_live_sync()
    _set_private_paths(monkeypatch, live_sync, tmp_path)
    (tmp_path / "account_catalog.json").write_text(
        json.dumps(
            {
                "start": "2026-04",
                "end": "2026-04",
                "accounts": [
                    {"id": "duplicate", "name": "First"},
                    {"id": "duplicate", "name": "Second"},
                ],
            }
        )
    )
    (tmp_path / "category_catalog.json").write_text(
        json.dumps({"start": "2026-04", "end": "2026-04", "categories": []})
    )
    monkeypatch.setattr(
        live_sync,
        "load_unified_account_mapping",
        lambda *_args: pytest.fail("map read before duplicate catalog validation"),
    )
    monkeypatch.setattr(
        live_sync, "ps_get_paginated", lambda *_args: pytest.fail("fetch before gate")
    )

    with pytest.raises(live_sync.LiveSyncError, match="duplicate"):
        live_sync.run_transactions_stage("2026-04", "2026-04", "key")

    assert not list(tmp_path.glob("*_ps_raw.json"))


def test_transaction_cli_rejects_invalid_map_before_env_or_network(
    tmp_path, monkeypatch
):
    live_sync = _load_live_sync()
    _set_private_paths(monkeypatch, live_sync, tmp_path)
    (tmp_path / "account_catalog.json").write_text(
        json.dumps(
            {
                "start": "2026-04",
                "end": "2026-04",
                "accounts": [{"id": "a", "name": "A"}],
            }
        )
    )
    (tmp_path / "category_catalog.json").write_text(
        json.dumps({"start": "2026-04", "end": "2026-04", "categories": []})
    )
    _write_account_mapping(
        tmp_path, {"a": {"name": "Wrong", "owner": "partner_a", "excluded": False}}
    )
    requests = []
    monkeypatch.setattr(live_sync, "_read_env_api_key", lambda: requests.append("env"))
    monkeypatch.setattr(
        live_sync, "_current_user_id", lambda *_args: requests.append("me")
    )
    monkeypatch.setattr(
        live_sync, "ps_get_paginated", lambda *_args: requests.append("get")
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["live_sync.py", "transactions", "--start", "2026-04", "--end", "2026-04"],
    )

    with pytest.raises(SystemExit, match="2"):
        live_sync.main()

    assert requests == []
    assert not list(tmp_path.glob("*_ps_raw.json"))


def test_transaction_cli_does_not_resolve_current_user_id(tmp_path, monkeypatch):
    live_sync = _load_live_sync()
    _set_private_paths(monkeypatch, live_sync, tmp_path)
    (tmp_path / "account_catalog.json").write_text(
        json.dumps(
            {
                "start": "2026-04",
                "end": "2026-04",
                "accounts": [{"id": "a", "name": "A"}],
            }
        )
    )
    (tmp_path / "category_catalog.json").write_text(
        json.dumps({"start": "2026-04", "end": "2026-04", "categories": []})
    )
    _write_account_mapping(
        tmp_path, {"a": {"name": "A", "owner": "partner_a", "excluded": True}}
    )
    monkeypatch.setattr(live_sync, "_read_env_api_key", lambda: "key")
    monkeypatch.setattr(
        live_sync,
        "_current_user_id",
        lambda *_args: pytest.fail("transactions stage must not call /me"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["live_sync.py", "transactions", "--start", "2026-04", "--end", "2026-04"],
    )

    live_sync.main()

    assert (tmp_path / "2026-04_ps_raw.json").is_file()


@pytest.mark.parametrize(
    "accounts",
    [
        {},
        {
            "a": {"name": "A", "owner": "partner_a", "excluded": False},
            "stale": {"name": "Stale", "owner": "partner_b", "excluded": False},
        },
    ],
)
def test_transaction_stage_requires_exact_account_id_coverage_before_fetch(
    tmp_path, monkeypatch, accounts
):
    live_sync = _load_live_sync()
    _set_private_paths(monkeypatch, live_sync, tmp_path)
    (tmp_path / "account_catalog.json").write_text(
        json.dumps(
            {
                "start": "2026-04",
                "end": "2026-04",
                "accounts": [{"id": "a", "name": "A"}],
            }
        )
    )
    (tmp_path / "category_catalog.json").write_text(
        json.dumps({"start": "2026-04", "end": "2026-04", "categories": []})
    )
    _write_account_mapping(tmp_path, accounts)
    monkeypatch.setattr(
        live_sync, "ps_get_paginated", lambda *_args: pytest.fail("fetch before gate")
    )

    with pytest.raises(live_sync.LiveSyncError, match="cover exactly"):
        live_sync.run_transactions_stage("2026-04", "2026-04", "key", "user")


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda mapping: mapping.update({"schema_version": 2}), "schema version"),
        (lambda mapping: mapping["partners"].pop("partner_b"), "exactly both partners"),
        (
            lambda mapping: mapping["partners"]["partner_a"].update({"label": ""}),
            "partner label",
        ),
        (
            lambda mapping: mapping["partners"]["partner_b"].update({"label": "Alex"}),
            "distinct",
        ),
        (
            lambda mapping: mapping["accounts"]["a"].update({"owner": "other"}),
            "invalid owner",
        ),
        (
            lambda mapping: mapping["accounts"]["a"].update({"owner": []}),
            "invalid owner",
        ),
        (
            lambda mapping: mapping["accounts"]["a"].update({"excluded": 1}),
            "invalid exclusion",
        ),
        (
            lambda mapping: mapping["accounts"]["a"].update({"extra": True}),
            "invalid account fields",
        ),
    ],
)
def test_transaction_stage_rejects_invalid_unified_schema_before_fetch(
    tmp_path, monkeypatch, mutate, message
):
    live_sync = _load_live_sync()
    _set_private_paths(monkeypatch, live_sync, tmp_path)
    (tmp_path / "account_catalog.json").write_text(
        json.dumps(
            {
                "start": "2026-04",
                "end": "2026-04",
                "accounts": [{"id": "a", "name": "A"}],
            }
        )
    )
    (tmp_path / "category_catalog.json").write_text(
        json.dumps({"start": "2026-04", "end": "2026-04", "categories": []})
    )
    mapping = _valid_account_mapping()
    mutate(mapping)
    (tmp_path / "account_mappings.json").write_text(json.dumps(mapping))
    monkeypatch.setattr(
        live_sync, "ps_get_paginated", lambda *_args: pytest.fail("fetch before gate")
    )

    with pytest.raises(live_sync.LiveSyncError, match=message):
        live_sync.run_transactions_stage("2026-04", "2026-04", "key", "user")


def test_transaction_stage_requires_category_catalog_before_fetch(
    tmp_path, monkeypatch
):
    live_sync = _load_live_sync()
    _set_private_paths(monkeypatch, live_sync, tmp_path)
    (tmp_path / "account_catalog.json").write_text(
        json.dumps({"start": "2026-04", "end": "2026-04", "accounts": []})
    )
    monkeypatch.setattr(
        live_sync, "ps_get_paginated", lambda *_args: pytest.fail("fetch before gate")
    )

    with pytest.raises(live_sync.LiveSyncError, match="Category catalog"):
        live_sync.run_transactions_stage("2026-04", "2026-04", "key", "user")

    assert not list(tmp_path.glob("*_ps_raw.json"))


def test_transaction_stage_excludes_accounts_and_publishes_canonical_snapshots(
    tmp_path, monkeypatch
):
    live_sync = _load_live_sync()
    _set_private_paths(monkeypatch, live_sync, tmp_path)
    accounts = [
        {"id": "included", "name": "Included"},
        {"id": "excluded", "name": "Excluded"},
    ]
    (tmp_path / "account_catalog.json").write_text(
        json.dumps({"start": "2026-04", "end": "2026-05", "accounts": accounts})
    )
    categories = [{"id": "food", "title": "Food"}]
    (tmp_path / "category_catalog.json").write_text(
        json.dumps({"start": "2026-04", "end": "2026-05", "categories": categories})
    )
    _write_account_mapping(
        tmp_path,
        {
            "included": {"name": "Included", "owner": "partner_a", "excluded": False},
            "excluded": {"name": "Excluded", "owner": "partner_b", "excluded": True},
        },
    )
    calls = []

    def fetch(path, *_args):
        calls.append(path)
        return [
            {"id": f"txn-{len(calls)}", "category": {"id": "food", "title": "Food"}}
        ]

    monkeypatch.setattr(live_sync, "ps_get_paginated", fetch)
    snapshots = live_sync.run_transactions_stage("2026-04", "2026-05", "key", "user")

    assert calls == ["/transaction_accounts/included/transactions"] * 2
    assert sorted(path.name for path in tmp_path.glob("*_ps_raw.json")) == [
        "2026-04_ps_raw.json",
        "2026-05_ps_raw.json",
    ]
    assert snapshots["2026-04"]["categories"] == categories
    assert snapshots["2026-04"]["transactions"][0]["category"] == categories[0]


def test_transaction_fetch_failure_publishes_no_monthly_output(tmp_path, monkeypatch):
    live_sync = _load_live_sync()
    _set_private_paths(monkeypatch, live_sync, tmp_path)
    (tmp_path / "account_catalog.json").write_text(
        json.dumps(
            {
                "start": "2026-04",
                "end": "2026-05",
                "accounts": [{"id": "a", "name": "A"}],
            }
        )
    )
    (tmp_path / "category_catalog.json").write_text(
        json.dumps({"start": "2026-04", "end": "2026-05", "categories": []})
    )
    _write_account_mapping(
        tmp_path, {"a": {"name": "A", "owner": "partner_a", "excluded": False}}
    )
    calls = 0

    def fetch(*_args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("network failed")
        return []

    monkeypatch.setattr(live_sync, "ps_get_paginated", fetch)

    with pytest.raises(OSError, match="network failed"):
        live_sync.run_transactions_stage("2026-04", "2026-05", "key", "user")

    assert not list(tmp_path.glob("*_ps_raw.json"))


@pytest.mark.parametrize(
    "next_url",
    [
        "https://evil.example/v2/transaction_accounts/a/transactions?page=2",
        "http://api.pocketsmith.com/v2/transaction_accounts/a/transactions?page=2",
        "https://api.pocketsmith.com/v2/users/other/categories?page=2",
        "https://api.pocketsmith.com:bad/v2/transaction_accounts/a/transactions?page=2",
    ],
)
def test_paginated_fetch_rejects_untrusted_next_link_before_second_request(
    monkeypatch, next_url
):
    live_sync = _load_live_sync()
    requests = []

    class Response:
        headers = {"link": f'<{next_url}>; rel="next"'}

        def read(self):
            return b"[]"

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    def urlopen(request, **_kwargs):
        requests.append(request)
        return Response()

    monkeypatch.setattr(live_sync, "_api_open", urlopen)

    with pytest.raises(live_sync.LiveSyncError, match="pagination link"):
        live_sync.ps_get_paginated(
            "/transaction_accounts/a/transactions", {"start_date": "2026-04-01"}, "key"
        )

    assert len(requests) == 1


def test_paginated_fetch_rejects_cycle_before_repeating_request(monkeypatch):
    live_sync = _load_live_sync()
    first_url = "https://api.pocketsmith.com/v2/transaction_accounts/a/transactions?start_date=2026-04-01"
    requests = []

    class Response:
        headers = {"link": f'<{first_url}>; rel="next"'}

        def read(self):
            return b"[]"

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    def urlopen(request, **_kwargs):
        requests.append(request)
        return Response()

    monkeypatch.setattr(live_sync, "_api_open", urlopen)

    with pytest.raises(live_sync.LiveSyncError, match="repeats"):
        live_sync.ps_get_paginated(
            "/transaction_accounts/a/transactions", {"start_date": "2026-04-01"}, "key"
        )

    assert len(requests) == 1


def test_paginated_fetch_stops_at_page_cap_before_another_request(monkeypatch):
    live_sync = _load_live_sync()
    next_url = (
        "https://api.pocketsmith.com/v2/transaction_accounts/a/transactions?page=2"
    )
    requests = []

    class Response:
        headers = {"link": f'<{next_url}>; rel="next"'}

        def read(self):
            return b"[]"

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    def urlopen(request, **_kwargs):
        requests.append(request)
        return Response()

    monkeypatch.setattr(live_sync, "MAX_PAGINATION_PAGES", 1)
    monkeypatch.setattr(live_sync, "_api_open", urlopen)

    with pytest.raises(live_sync.LiveSyncError, match="page limit"):
        live_sync.ps_get_paginated(
            "/transaction_accounts/a/transactions", {"start_date": "2026-04-01"}, "key"
        )

    assert len(requests) == 1


def test_redirect_to_untrusted_target_is_rejected_before_key_can_be_resent():
    live_sync = _load_live_sync()
    request = live_sync._api_request(
        "https://api.pocketsmith.com/v2/me", "/me", "secret-key"
    )

    redirected_request = live_sync._NoRedirectHandler().redirect_request(
        request, None, 302, "Found", {}, "https://evil.example/collect"
    )

    assert request.get_header("X-developer-key") == "secret-key"
    assert redirected_request is None


def test_transaction_publish_failure_restores_all_prior_monthly_outputs(
    tmp_path, monkeypatch
):
    live_sync = _load_live_sync()
    _set_private_paths(monkeypatch, live_sync, tmp_path)
    months = [f"2026-{month:02d}" for month in range(1, 13)]
    targets = {month: tmp_path / f"{month}_ps_raw.json" for month in months}
    for month, target in targets.items():
        target.write_text(f'{{"previous": "{month}"}}\n', encoding="utf-8")
    snapshots = {month: {"month": month, "new": True} for month in months}
    real_replace = live_sync.os.replace

    def fail_second_publish(source, destination):
        if (
            Path(source).parent.name.startswith(".live-sync-stage-")
            and Path(destination) == targets[months[-1]]
        ):
            raise OSError("forced later publish failure")
        real_replace(source, destination)

    monkeypatch.setattr(live_sync.os, "replace", fail_second_publish)

    with pytest.raises(live_sync.LiveSyncError, match="prior snapshots restored"):
        live_sync._publish_transaction_snapshots(snapshots)

    assert {
        month: target.read_text(encoding="utf-8") for month, target in targets.items()
    } == {month: f'{{"previous": "{month}"}}\n' for month in months}
    assert not list(tmp_path.glob(".live-sync-recovery-*"))


def test_transaction_publish_rollback_failure_retains_recoverable_prior_snapshot(
    tmp_path, monkeypatch
):
    live_sync = _load_live_sync()
    _set_private_paths(monkeypatch, live_sync, tmp_path)
    months = ["2026-04", "2026-05"]
    targets = {month: tmp_path / f"{month}_ps_raw.json" for month in months}
    for month, target in targets.items():
        target.write_text(f'{{"previous": "{month}"}}\n', encoding="utf-8")
    snapshots = {month: {"month": month, "new": True} for month in months}
    real_replace = live_sync.os.replace

    def fail_publish_and_restore(source, destination):
        source_path = Path(source)
        destination_path = Path(destination)
        if (
            source_path.parent.name.startswith(".live-sync-stage-")
            and destination_path == targets[months[-1]]
        ):
            raise OSError("forced publish failure")
        if (
            source_path.parent.name.startswith(".live-sync-recovery-")
            and destination_path == targets[months[0]]
        ):
            raise OSError("forced restore failure")
        real_replace(source, destination)

    monkeypatch.setattr(live_sync.os, "replace", fail_publish_and_restore)

    with pytest.raises(live_sync.LiveSyncError, match="rollback failed"):
        live_sync._publish_transaction_snapshots(snapshots)

    recovery_dirs = list(tmp_path.glob(".live-sync-recovery-*"))
    assert len(recovery_dirs) == 1
    retained_snapshot = recovery_dirs[0] / targets[months[0]].name
    assert retained_snapshot.read_text(encoding="utf-8") == '{"previous": "2026-04"}\n'
