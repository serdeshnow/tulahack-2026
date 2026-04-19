from __future__ import annotations

import argparse
from pathlib import Path

from evals.config import E2EEvalConfig, load_yaml_config
from evals.runners.e2e import run_e2e_eval


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate the voice-redaction platform with a unified end-to-end pipeline."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    e2e_parser = subparsers.add_parser(
        "e2e", help="Run unified end-to-end evaluation with both metrics."
    )
    e2e_parser.add_argument("--config", required=True, type=Path)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "e2e":
        config = load_yaml_config(args.config, E2EEvalConfig)
        report = run_e2e_eval(config)
    else:
        parser.error(f"Unsupported command: {args.command}")

    print(report.stdout_summary())
    return 0
