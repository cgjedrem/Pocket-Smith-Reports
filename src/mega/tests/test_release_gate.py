"""Executable synthetic release gate for the public mega-report CLI."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from pypdf import PdfReader

from mega.registry import numbered_sections, section_by_id, valid_ids

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "data" / "sample_apr_2026.json"
SECTION_MAP = ROOT / "data" / "sample_apr_2026_detailed_section_mapping.json"


def _write_recommendations(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "generated_at": "2026-07-25T12:00:00Z",
                "period": {"start": "2026-04", "end": "2026-04"},
                "recommendations": [
                    {
                        "id": "fixture-recommendation",
                        "title": "Fixture recommendation",
                        "body": "Synthetic release-gate artifact.",
                        "severity": "low",
                        "evidence": ["Synthetic fixture"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_synthetic_configs(data_dir: Path) -> tuple[Path, Path]:
    owner_map = data_dir / "owners.json"
    label_map = data_dir / "labels.json"
    owner_map.write_text(
        json.dumps({"101": "partner_a", "102": "partner_b"}), encoding="utf-8"
    )
    label_map.write_text(
        json.dumps({"partner_a": "Alex", "partner_b": "Blair"}), encoding="utf-8"
    )
    return owner_map, label_map


def _run_cli(
    data_dir: Path,
    output_dir: Path,
    recommendations_artifact: Path,
    only: str | None = None,
    name: str = "release_gate",
    start: str = "2026-04",
    end: str = "2026-04",
    detailed_section_map: Path = SECTION_MAP,
    category_role_map: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        "-m",
        "mega.build_mega",
        "--start",
        start,
        "--end",
        end,
        "--data-dir",
        str(data_dir),
        "--input-kind",
        "synthetic",
        "--output-dir",
        str(output_dir),
        "--name",
        name,
        "--detailed-section-map",
        str(detailed_section_map),
        "--account-owner-map",
        str(data_dir / "owners.json"),
        "--partner-label-map",
        str(data_dir / "labels.json"),
        "--recommendations-artifact",
        str(recommendations_artifact),
    ]
    if only:
        command.extend(["--only", only])
    if category_role_map is not None:
        command.extend(["--category-role-map", str(category_role_map)])
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    environment.pop("POCKETSMITH_ACCOUNT_OWNER_MAP", None)
    return subprocess.run(
        command, cwd=ROOT, env=environment, text=True, capture_output=True, check=False
    )


def test_release_gate_cli_uses_required_synthetic_input_kind(tmp_path, monkeypatch):
    captured = {}

    def run(command, **kwargs):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", run)
    _run_cli(
        tmp_path / "data",
        tmp_path / "out",
        recommendations_artifact=tmp_path / "recommendations.json",
    )

    command = captured["command"]
    assert command[command.index("--input-kind") + 1] == "synthetic"


def _pdf_text(pdf_path: Path) -> str:
    pdf = pdf_path.read_bytes()
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1_024
    reader = PdfReader(pdf_path)
    assert len(reader.pages) >= 1
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _heading(number, section) -> str:
    labels = {"personal_partner_a": "Alex", "personal_partner_b": "Blair"}
    title = section.title.replace(
        "Partner A", labels.get(section.identifier, "Partner A")
    )
    title = title.replace("Partner B", labels.get(section.identifier, "Partner B"))
    return f"{number}. {title}"


@pytest.mark.pdf_renderer
def test_synthetic_release_gate_builds_full_report_and_every_registry_section(tmp_path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "out"
    data_dir.mkdir()
    shutil.copy(FIXTURE, data_dir / FIXTURE.name)
    _write_synthetic_configs(data_dir)
    _write_recommendations(data_dir / "recommendations.json")
    missing_recommendations = data_dir / "missing-recommendations.json"

    full = _run_cli(
        data_dir, output_dir, recommendations_artifact=missing_recommendations
    )
    assert full.returncode == 0, full.stderr
    full_html = output_dir / "release_gate.html"
    full_pdf = output_dir / "release_gate.pdf"
    assert full_html.is_file() and full_pdf.is_file()
    full_text = full_html.read_text(encoding="utf-8")
    assert ">10. Recommendations<" not in full_text
    active_without_recommendations = numbered_sections()
    for number, section in active_without_recommendations:
        assert _heading(number, section) in full_text
    full_pdf_text = _pdf_text(full_pdf)
    for number, section in active_without_recommendations:
        assert _heading(number, section) in full_pdf_text

    with_recommendations = _run_cli(
        data_dir,
        output_dir,
        recommendations_artifact=data_dir / "recommendations.json",
        name="release_gate_full_with_recs",
    )
    assert with_recommendations.returncode == 0, with_recommendations.stderr
    recommendations_html = (output_dir / "release_gate_full_with_recs.html").read_text(
        encoding="utf-8"
    )
    active_with_recommendations = numbered_sections(include_recommendations=True)
    for number, section in active_with_recommendations:
        assert _heading(number, section) in recommendations_html
    recommendations_pdf_text = _pdf_text(output_dir / "release_gate_full_with_recs.pdf")
    for number, section in active_with_recommendations:
        assert _heading(number, section) in recommendations_pdf_text

    for identifier in valid_ids(include_recommendations=True):
        result = _run_cli(
            data_dir,
            output_dir,
            recommendations_artifact=(
                data_dir / "recommendations.json"
                if identifier == "recommendations"
                else missing_recommendations
            ),
            only=identifier,
        )
        assert result.returncode == 0, f"{identifier}: {result.stderr}"
        html_path = output_dir / f"release_gate_{identifier}.html"
        pdf_path = output_dir / f"release_gate_{identifier}.pdf"
        assert html_path.is_file() and pdf_path.is_file()
        number, section = section_by_id(
            identifier,
            include_recommendations=identifier == "recommendations",
        )
        html = html_path.read_text(encoding="utf-8")
        expected_heading = _heading(number, section)
        assert expected_heading in html
        pdf_text = _pdf_text(pdf_path)
        assert expected_heading in pdf_text
        for other_number, other_section in numbered_sections(
            include_recommendations=True
        ):
            other_heading = _heading(other_number, other_section)
            if other_section.identifier != identifier:
                assert other_heading not in html
                assert other_heading not in pdf_text


def test_synthetic_release_gate_invalid_input_publishes_no_artifacts(tmp_path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "out"
    data_dir.mkdir()
    _write_synthetic_configs(data_dir)
    source = json.loads(FIXTURE.read_text(encoding="utf-8"))
    source["transactions"][0]["category"] = None
    (data_dir / FIXTURE.name).write_text(json.dumps(source), encoding="utf-8")

    result = _run_cli(
        data_dir,
        output_dir,
        recommendations_artifact=data_dir / "missing-recommendations.json",
    )

    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert not (output_dir / "release_gate.html").exists()
    assert not (output_dir / "release_gate.pdf").exists()


def test_synthetic_release_gate_preflights_all_months_before_publishing(tmp_path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "out"
    data_dir.mkdir()
    april = json.loads(FIXTURE.read_text(encoding="utf-8"))
    may = json.loads(json.dumps(april).replace("2026-04", "2026-05"))
    may["transactions"][0]["category"]["id"] = "unmapped-category"
    (data_dir / "sample_apr_2026.json").write_text(json.dumps(april), encoding="utf-8")
    (data_dir / "sample_may_2026.json").write_text(json.dumps(may), encoding="utf-8")
    _write_synthetic_configs(data_dir)
    (data_dir / "owners.json").write_text(
        json.dumps({"101": "partner_a", "102": "partner_b", "103": "partner_a"}),
        encoding="utf-8",
    )
    category_roles = data_dir / "category_roles.json"
    category_roles.write_text(
        json.dumps(
            {
                # Sample fixture categories are "1"/"2"/"3"-"11" (PR1 extended
                # coverage); map them all so April clears KPI role resolution
                # and May's "unmapped-category" reaches the detailed-section
                # validation instead.
                "1": "spend",
                "2": "spend",
                "3": "income",
                "4": "income",
                "5": "savings",
                "6": "spend",
                "7": "personal_spend",
                "8": "personal_spend",
                "9": "spend",
                "10": "exclude",
                "11": "exclude",
                "201": "income",
                "202": "income",
                "203": "income",
                "204": "savings",
                "205": "savings",
                "206": "spend",
                "207": "spend",
                "208": "spend",
                "209": "exclude",
                "210": "spend",
                "211": "spend",
                "212": "spend",
                "213": "personal_spend",
                "214": "personal_spend",
                "215": "spend",
                "216": "exclude",
            }
        ),
        encoding="utf-8",
    )

    result = _run_cli(
        data_dir,
        output_dir,
        recommendations_artifact=data_dir / "missing-recommendations.json",
        start="2026-04",
        end="2026-05",
        category_role_map=category_roles,
    )

    assert result.returncode == 1
    assert "Detailed section mapping has no section" in result.stderr
    assert not (output_dir / "release_gate.html").exists()
    assert not (output_dir / "release_gate.pdf").exists()
