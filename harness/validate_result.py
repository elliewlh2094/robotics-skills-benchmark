#!/usr/bin/env python3
"""Validate a result.json against harness/schemas/result.schema.yaml.

Usage:
    python harness/validate_result.py experiments/<exp_dir>/result.json
    python harness/validate_result.py --all

Programmatic use:
    from harness.validate_result import validate, iter_errors
    validate(result_dict)        # raises jsonschema.ValidationError
    msgs = iter_errors(result)   # list[str]; empty = valid
"""
from __future__ import annotations

import argparse
import functools
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft7Validator, ValidationError

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "harness" / "schemas" / "result.schema.yaml"
EXPERIMENTS_ROOT = REPO_ROOT / "experiments"


def _load_yaml(path: Path) -> dict:
    with path.open() as f:
        return yaml.safe_load(f)


@functools.lru_cache(maxsize=1)
def _validator() -> Draft7Validator:
    return Draft7Validator(_load_yaml(SCHEMA_PATH))


def validate(result: dict) -> None:
    """Raise jsonschema.ValidationError on the first schema violation."""
    _validator().validate(result)


def iter_errors(result: dict) -> list[str]:
    """Return human-readable error messages; empty list = valid."""
    return [
        f"{'.'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in _validator().iter_errors(result)
    ]


def _validate_path(path: Path) -> list[str]:
    with path.open() as f:
        result = json.load(f)
    return iter_errors(result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("result_path", nargs="?", help="Path to a result.json")
    parser.add_argument("--all", action="store_true",
                        help="Validate every experiments/*/result.json")
    args = parser.parse_args(argv)

    if args.all:
        paths = sorted(EXPERIMENTS_ROOT.glob("*/result.json"))
        if not paths:
            print(f"(no result.json files under {EXPERIMENTS_ROOT.relative_to(REPO_ROOT)}/)")
            return 0
    elif args.result_path:
        paths = [Path(args.result_path).resolve()]
    else:
        parser.error("provide a path or --all")
        return 2

    failed = 0
    for path in paths:
        try:
            errors = _validate_path(path)
        except (json.JSONDecodeError, OSError) as e:
            failed += 1
            print(f"FAIL {path} (could not load: {e})")
            continue
        rel = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
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
