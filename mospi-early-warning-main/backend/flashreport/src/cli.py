"""Command line entry point.

    python -m report_gen --input data/sample_2026_07.json \
                         --edition 489 --month 2026-07 \
                         --out out/FlashReport_July_2026.pdf

Structured logging goes to stderr; the final path, page count, size and build
time are logged at INFO level.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .render import build_report

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m report_gen",
        description="MoSPI Flash Report generator (Jinja2 + WeasyPrint).",
    )
    p.add_argument("--input", required=True,
                   help="Input JSON (or CSV + meta.json) with projects[] and meta.")
    p.add_argument("--out", required=True, help="Output PDF path.")
    p.add_argument("--theme", default=str(PROJECT_ROOT / "config" / "theme.yaml"),
                   help="theme YAML (default: config/theme.yaml)")
    p.add_argument("--edition", type=int, default=None,
                   help="Override the edition number from meta (e.g. 489).")
    p.add_argument("--month", default=None,
                   help="Override month from meta (e.g. 2026-07).")
    p.add_argument("--project-root", default=None,
                   help="Package root used to resolve asset/theme paths (default: parent of the input path's parent).")
    p.add_argument("--log", default="INFO", help="Log level (INFO/DEBUG/WARNING).")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )
    try:
        out = build_report(
            input_path=Path(args.input),
            out_path=Path(args.out),
            theme_path=Path(args.theme),
            edition=args.edition,
            month=args.month,
            project_root=Path(args.project_root) if args.project_root else None,
        )
    except Exception as exc:  # noqa: BLE001 - entry point, loud failures desired
        logging.getLogger("report_gen").error("Build failed: %s", exc)
        return 1
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())