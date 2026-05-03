#!/usr/bin/env python3
"""Validate one or more result.json files against harness/schemas/result.schema.yaml.

Usage:
    python harness/validate_result.py experiments/<dir>/result.json
    python harness/validate_result.py --all     # walks experiments/*/result.json

Mirrors harness/validate_task.py in shape. Used as a CLI tool today; the
runner also calls validate_result() inline from write_result(), so any file
that lands on disk via the runner is already schema-checked.
"""
from __future__ import annotations

import argparse
import json
import sys
from functools import lru_cache
from pathlib import Path

import yaml
from jsonschema import Draft7Validator

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "harness" / "schemas" / "result.schema.yaml"
EXPERIMENTS_DIR = REPO_ROOT / "experiments"


class ResultValidationError(ValueError):
    """Raised when a result dict fails schema validation."""


@lru_cache(maxsize=1)
def _validator() -> Draft7Validator:
    with SCHEMA_PATH.open() as f:
        schema = yaml.safe_load(f)
    return Draft7Validator(schema)


def format_errors(errors) -> list[str]:
    return [
        f"{'.'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in errors
    ]


def validate_result(result: dict) -> None:
    """Raise ResultValidationError if `result` doesn't match the schema."""
    errors = list(_validator().iter_errors(result))
    if errors:
        joined = "; ".join(format_errors(errors))
        raise ResultValidationError(joined)


def validate_one(result_path: Path) -> list[str]:
    """Returns list of error messages for one file; empty list = valid."""
    with result_path.open() as f:
        instance = json.load(f)
    return format_errors(_validator().iter_errors(instance))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result_path", nargs="?", help="Path to a result.json")
    parser.add_argument(
        "--all", action="store_true",
        help="Validate every result.json under experiments/",
    )
    args = parser.parse_args()

    if args.all:
        paths = sorted(EXPERIMENTS_DIR.glob("*/result.json"))
        if not paths:
            print(f"[validate_result] no result.json files found under {EXPERIMENTS_DIR}")
            return 0
    elif args.result_path:
        paths = [Path(args.result_path).resolve()]
    else:
        parser.error("Provide a result.json path or --all")
        return 2

    failed = 0
    for path in paths:
        try:
            errors = validate_one(path)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            failed += 1
            try:
                rel = path.relative_to(REPO_ROOT)
            except ValueError:
                rel = path
            print(f"FAIL {rel}")
            print(f"  - {type(e).__name__}: {e}")
            continue
        try:
            rel = path.relative_to(REPO_ROOT)
        except ValueError:
            rel = path
        if errors:
            failed += 1
            print(f"FAIL {rel}")
            for err in errors:
                print(f"  - {err}")
        else:
            print(f"OK   {rel}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
