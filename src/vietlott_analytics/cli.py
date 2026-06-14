from __future__ import annotations

import argparse
import json
from pathlib import Path

from .builder import build_research_site


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vietlott-research-report",
        description="Build statistical reports, predictions, and static-site data.",
    )
    parser.add_argument("--datasets-dir", type=Path, default=Path("datasets"))
    parser.add_argument("--site-dir", type=Path, default=Path("site"))
    parser.add_argument(
        "--prediction-ledger",
        type=Path,
        default=Path("predictions/ledger.jsonl"),
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    report = build_research_site(
        datasets_dir=args.datasets_dir,
        site_dir=args.site_dir,
        prediction_ledger_path=args.prediction_ledger,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
