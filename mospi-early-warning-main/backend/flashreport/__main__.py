"""Entry point: ``python -m report_gen`` (run from the parent of this folder)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())