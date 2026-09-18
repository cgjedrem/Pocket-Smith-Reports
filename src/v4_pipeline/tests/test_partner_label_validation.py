"""Tests for the canonical partner-label validator (contracts/partner-labels-config.md)."""

from accounting import DEFAULT_PARTNER_LABELS, validate_partner_labels


def test_none_input_returns_defaults_with_no_warnings():
    labels, warnings = validate_partner_labels(None)
    assert labels == DEFAULT_PARTNER_LABELS
    assert warnings == []


def test_valid_labels_pass_through_unchanged():
    labels, warnings = validate_partner_labels(
        {"partner_a": "Ada Example", "partner_b": "Ben Example"}
    )
    assert labels == {"partner_a": "Ada Example", "partner_b": "Ben Example"}
    assert warnings == []


def test_non_object_root_returns_placeholders_with_warning():
    labels, warnings = validate_partner_labels(["not", "a", "dict"])
    assert labels == DEFAULT_PARTNER_LABELS
    assert any("not an object" in warning for warning in warnings)


def test_missing_key_falls_back_for_that_partner_only():
    labels, warnings = validate_partner_labels({"partner_a": "Ada Example"})
    assert labels == {"partner_a": "Ada Example", "partner_b": "Partner B"}
    assert any("missing 'partner_b'" in warning for warning in warnings)


def test_non_string_value_falls_back_for_that_partner_only():
    labels, warnings = validate_partner_labels(
        {"partner_a": 123, "partner_b": "Ben Example"}
    )
    assert labels == {"partner_a": "Partner A", "partner_b": "Ben Example"}
    assert any("not a string" in warning for warning in warnings)


def test_long_label_is_truncated_with_warning():
    labels, warnings = validate_partner_labels(
        {"partner_a": "x" * 100, "partner_b": "Ben Example"}
    )
    assert labels["partner_a"] == "x" * 64
    assert labels["partner_b"] == "Ben Example"
    assert any("truncated" in warning for warning in warnings)


def test_duplicate_labels_reject_both_partners():
    labels, warnings = validate_partner_labels(
        {"partner_a": "Same Name", "partner_b": "same name"}
    )
    assert labels == DEFAULT_PARTNER_LABELS
    assert any("must be distinct" in warning for warning in warnings)


def test_reserved_placeholder_values_are_rejected():
    labels, warnings = validate_partner_labels(
        {"partner_a": "Partner A", "partner_b": "Ben Example"}
    )
    assert labels == {"partner_a": "Partner A", "partner_b": "Ben Example"}
    assert any("reserved placeholder" in warning for warning in warnings)


def test_empty_and_whitespace_labels_are_rejected():
    for bad in ("", "   "):
        labels, warnings = validate_partner_labels(
            {"partner_a": bad, "partner_b": "Ben Example"}
        )
        assert labels == {"partner_a": "Partner A", "partner_b": "Ben Example"}
        assert any("empty" in warning for warning in warnings)


def test_extra_keys_warn_and_are_ignored():
    labels, warnings = validate_partner_labels(
        {"partner_a": "Ada", "partner_b": "Ben", "partner_c": "Third"}
    )
    assert labels == {"partner_a": "Ada", "partner_b": "Ben"}
    assert any("unknown key" in warning for warning in warnings)


def test_html_payload_label_passes_validation_rendering_is_escaped_elsewhere():
    labels, warnings = validate_partner_labels(
        {"partner_a": "<img src=x onerror=alert(1)>", "partner_b": "Ben Example"}
    )
    assert labels["partner_a"] == "<img src=x onerror=alert(1)>"
    assert warnings == []
