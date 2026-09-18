"""Copy a local PocketSmith export into the ignored private-data directory."""

import argparse
import shutil
from pathlib import Path

import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PRIVATE_DATA_DIR = REPOSITORY_ROOT / "data" / "private"
SOURCE_DIR = REPOSITORY_ROOT / "src"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from input_contract import InputContractError, monthly_filename


def _source_path(value: str) -> Path:
    source = Path(value).expanduser().resolve()
    if not source.is_file():
        raise argparse.ArgumentTypeError(f"Source export not found: {source}")
    return source


def _export_month(value: str) -> str:
    try:
        monthly_filename(value, "live")
    except InputContractError as error:
        raise argparse.ArgumentTypeError(str(error)) from error
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source", type=_source_path, help="Local PocketSmith JSON export"
    )
    parser.add_argument(
        "--month", type=_export_month, required=True, help="Export month (YYYY-MM)"
    )
    return parser


def parse_args() -> argparse.Namespace:
    return _parser().parse_args()


def main() -> None:
    parser = _parser()
    args = parser.parse_args()
    destination = PRIVATE_DATA_DIR / monthly_filename(args.month, "live")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(args.source, destination)
    except OSError as error:
        parser.error(f"Could not save local export to {destination}: {error}")
    print(f"Saved local export to {destination}")


if __name__ == "__main__":
    main()
