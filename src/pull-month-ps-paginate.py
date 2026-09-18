#!/usr/bin/env python3
"""Retired one-month PocketSmith sync entry point."""

import argparse
import sys

MIGRATION_MESSAGE = (
    "Legacy one-month sync is disabled. Use the staged live sync instead: "
    "PYTHONPATH=src python src/live_sync.py transactions --start YYYY-MM --end YYYY-MM"
)


def main(argv: list[str] | None = None) -> int:
    """Hard-fail old sync before reading credentials or writing snapshots."""
    parser = argparse.ArgumentParser(
        description="Retired PocketSmith sync", add_help=False
    )
    parser.error(MIGRATION_MESSAGE)
    return 2


if __name__ == "__main__":
    sys.exit(main())
