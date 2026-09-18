"""
Shared pytest fixtures for the v4 pipeline tests.

Loads the synthetic Apr 2026 PS fixture (sample_apr_2026.json) and runs the
full data_loader → tally → wallet chain once per test session, exposing
the results as fixtures.
"""

import sys
from pathlib import Path

# Make sibling modules importable
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))  # v4_pipeline/

from data_loader import load
from tally import compute as tally_compute
from wallet import compute as wallet_compute

import pytest

SAMPLE_PATH = HERE.parent.parent.parent / "data" / "sample_apr_2026.json"


def pytest_configure(config):
    """Validate sample data exists at session start."""
    if not SAMPLE_PATH.exists():
        raise FileNotFoundError(
            f"Sample data not found at {SAMPLE_PATH}. "
            "Tests need data/sample_apr_2026.json to run."
        )


@pytest.fixture(scope="session")
def sample_path():
    return str(SAMPLE_PATH)


@pytest.fixture(scope="session")
def txns(sample_path):
    return load("2026-04", sample_path)


@pytest.fixture(scope="session")
def totals(txns):
    return tally_compute(txns)


@pytest.fixture(scope="session")
def wallet(totals, txns):
    return wallet_compute(totals, txns)
