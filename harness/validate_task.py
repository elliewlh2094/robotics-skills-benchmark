#!/usr/bin/env python3
"""Validate a task instance YAML against tasks/schema.yaml.

Usage:
    python harness/validate_task.py tasks/instances/<task-id>/task.yaml
    python harness/validate_task.py --all
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml
from jsonschema import Draft7Validator

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "tasks" / "schema.yaml"
INSTANCES_DIR = REPO_ROOT / "tasks" / "instances"


def load_yaml(path: Path) -> dict:
    with path.open() as f:
        return yaml.safe_load(f)


def validate_one(task_path: Path, validator: Draft7Validator) -> list[str]:
    """Returns list of error messages; empty list = valid."""
    instance = load_yaml(task_path)
    return [
        f"{'.'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in validator.iter_errors(instance)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_path", nargs="?", help="Path to a task.yaml")
    parser.add_argument("--all", action="store_true", help="Validate every instance")
    args = parser.parse_args()

    schema = load_yaml(SCHEMA_PATH)
    validator = Draft7Validator(schema)

    if args.all:
        paths = sorted(INSTANCES_DIR.glob("*/task.yaml"))
    elif args.task_path:
        paths = [Path(args.task_path).resolve()]
    else:
        parser.error("Provide a task path or --all")
        return 2

    failed = 0
    for path in paths:
        errors = validate_one(path, validator)
        if errors:
            failed += 1
            print(f"FAIL {path.relative_to(REPO_ROOT)}")
            for err in errors:
                print(f"  - {err}")
        else:
            print(f"OK   {path.relative_to(REPO_ROOT)}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
