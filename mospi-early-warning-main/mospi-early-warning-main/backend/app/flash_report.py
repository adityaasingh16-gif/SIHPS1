"""Build the MoSPI Flash Report PDF from the real OMS panel CSV.

The report generator (vendored under ``backend/flashreport``) needs WeasyPrint,
which on this workstation only imports inside the ``reportgen`` conda env.  This
module therefore stays lightweight (pure stdlib) and shells out to a Python
interpreter that can import the generator -- configured via
``FLASH_REPORT_PYTHON`` (default: the matching miniconda env).  The payload is
written to ``flashreport/data/generated/`` and the finished PDF to
``flashreport/out/``.
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
FLASHREPORT_DIR = BACKEND_DIR / "flashreport"
PANEL_CSV = BACKEND_DIR / "data" / "panel_mospi.csv"
GENERATED_DIR = FLASHREPORT_DIR / "data" / "generated"
OUT_DIR = FLASHREPORT_DIR / "out"

MONTHS = {
    "01": "JANUARY", "02": "FEBRUARY", "03": "MARCH", "04": "APRIL",
    "05": "MAY", "06": "JUNE", "07": "JULY", "08": "AUGUST",
    "09": "SEPTEMBER", "10": "OCTOBER", "11": "NOVEMBER", "12": "DECEMBER",
}

NE_STATES = {
    "Arunachal Pradesh", "Assam", "Manipur", "Meghalaya",
    "Mizoram", "Nagaland", "Sikkim", "Tripura",
}

# Map the panel's 22 sector buckets onto the six Harmonized Master List
# categories the Flash Report is organized by.
SECTOR_CATEGORY = {
    "Aviation & Aviation Infrastructure": "Transport & Logistics",
    "Inland Waterways": "Transport & Logistics",
    "Logistics Infrastructure": "Transport & Logistics",
    "Railways": "Transport & Logistics",
    "Roads & Highways": "Transport & Logistics",
    "Shipping": "Transport & Logistics",
    "Urban Public Transport": "Transport & Logistics",
    "Coal": "Energy",
    "Electricity Generation": "Energy",
    "Energy Storage": "Energy",
    "Oil & Gas": "Energy",
    "Transmission & Distribution": "Energy",
    "Waste & Water": "Water & Sanitation",
    "Water Resources": "Water & Sanitation",
    "Telecommunication": "Communication",
    "Education": "Social & Commercial",
    "Healthcare": "Social & Commercial",
    "Real Estate": "Social & Commercial",
    "Tourism, Hospitality & Wellness": "Social & Commercial",
    "Construction": "Other Sectors",
    "Metals & Mining": "Other Sectors",
    "Steel": "Other Sectors",
}

DEFAULT_ASSETS = {
    "emblem": "static/img/emblem.png",
    "org_logo": "static/img/org_logo.png",
    "cover_art": "static/img/cover_art.png",
    "skyline_art": "static/img/skyline_art.png",
    "qr_image": "static/img/qr_image.png",
}


class FlashReportBuildError(RuntimeError):
    """Raised when the Flash Report cannot be produced."""


def _num(value, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def _month_val(value) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 0


def _mmyy(m: str, y: str) -> str:
    mm = _month_val(m)
    yy = _month_val(y)
    if not mm or not yy:
        return ""
    return f"{mm:02d}/{yy}"


def _month_label(month: str) -> str:
    yyyy, mm = month.split("-")
    return f"{MONTHS.get(mm, mm)} {yyyy}"


def _available_months() -> list[str]:
    if not PANEL_CSV.exists():
        raise FlashReportBuildError(f"Panel CSV not found: {PANEL_CSV}")
    months: set[str] = set()
    with PANEL_CSV.open(encoding="utf-8", errors="replace", newline="") as fh:
        for row in csv.DictReader(fh):
            y, m = row.get("report_year", ""), row.get("report_month", "")
            if y and m:
                months.add(f"{_month_val(y):04d}-{_month_val(m):02d}")
    return sorted(months)


def _latest_month() -> str:
    months = _available_months()
    if not months:
        raise FlashReportBuildError(f"No data rows in {PANEL_CSV}")
    return months[-1]


def _build_projects(month: str) -> list[dict]:
    y, m = month.split("-")
    want_y, want_m = int(y), int(m)
    seen: dict[str, dict] = {}
    with PANEL_CSV.open(encoding="utf-8", errors="replace", newline="") as fh:
        for row in csv.DictReader(fh):
            if _month_val(row.get("report_year")) != want_y or _month_val(row.get("report_month")) != want_m:
                continue
            code = (row.get("project_code") or "").strip()
            if not code or code in seen:
                continue
            state = (row.get("state") or "").strip()
            rev = _num(row.get("revised_cost_crore"))
            exp = _num(row.get("cumulative_expenditure_crore"))
            fin = (exp / rev * 100.0) if rev > 0 else 0.0
            seen[code] = {
                "project_id": code,
                "project_name": row.get("project_name") or "",
                "agency": row.get("agency") or "",
                "ministry": row.get("ministry") or "Unknown",
                "sector": row.get("sector") or "",
                "category": SECTOR_CATEGORY.get((row.get("sector") or "").strip(), "Other Sectors"),
                "state": state,
                "is_north_east": state in NE_STATES,
                "approval_date": _mmyy(row.get("approval_month"), row.get("approval_year")),
                "start_date": _mmyy(row.get("start_month"), row.get("start_year")),
                "original_doc": _mmyy(row.get("target_doc_month"), row.get("target_doc_year")),
                "revised_doc": _mmyy(row.get("revised_doc_month"), row.get("revised_doc_year")),
                "actual_completion_date": "",
                "original_cost": _num(row.get("original_cost_crore")),
                "revised_cost": rev,
                "cumulative_expenditure": exp,
                "physical_progress_pct": _num(row.get("physical_progress_pct")),
                "financial_progress_pct": fin,
                "legacy_code": "",
                "pmgid": "",
                "status": "ongoing",
            }
    return list(seen.values())


def _build_payload(month: str, edition: int) -> dict:
    label = _month_label(month)
    projects = _build_projects(month)
    if not projects:
        raise FlashReportBuildError(
            f"No projects found for month {month}. Available months: {', '.join(_available_months())}."
        )
    return {
        "meta": {
            "edition_no": edition,
            "month_label": label,
            "month": month,
            "cost_threshold_text": "₹150 crore & above",
            "portal_url": "https://oms.mospi.gov.in",
            "data_cutoff_note": f"Data as available on the OMS portal (https://oms.mospi.gov.in) as on {label}.",
            "assets": DEFAULT_ASSETS,
            "report_title": f"{label} Flash Report",
            "program_name": "Infrastructure and Project Monitoring Division",
            "ministry_name": "Ministry of Statistics and Programme Implementation",
        },
        "projects": projects,
    }


def _renderer_python() -> str:
    configured = os.getenv("FLASH_REPORT_PYTHON")
    if configured:
        p = Path(configured)
        if p.exists():
            return str(p)
        raise FlashReportBuildError(f"FLASH_REPORT_PYTHON set to a missing file: {configured}")
    candidates = [
        Path(os.getenv("CONDA_PREFIX", "")) / "python.exe",
        Path.home() / "miniconda3" / "envs" / "reportgen" / "python.exe",
        Path("C:/ProgramData/miniconda3/envs/reportgen/python.exe"),
    ]
    for cand in candidates:
        if cand and cand.exists():
            return str(cand)
    found = shutil.which("python")
    if found:
        return found
    raise FlashReportBuildError(
        "Could not locate a Python interpreter with WeasyPrint. "
        "Set FLASH_REPORT_PYTHON to the 'reportgen' conda env python.exe."
    )


def _render(payload_path: Path, out_path: Path, edition: int) -> None:
    cmd = [
        _renderer_python(),
        "-m", "src.cli",
        "--input", str(payload_path),
        "--out", str(out_path),
        "--edition", str(edition),
        "--project-root", str(FLASHREPORT_DIR),
    ]
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(FLASHREPORT_DIR),
            env=env,
            capture_output=True,
            text=True,
            timeout=2400,
        )
    except subprocess.TimeoutExpired as exc:
        raise FlashReportBuildError("Flash Report build timed out after 40 minutes.") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise FlashReportBuildError(f"Flash Report build failed:\n{detail[-2000:]}")
    if not out_path.exists() or out_path.stat().st_size == 0:
        raise FlashReportBuildError("Flash Report build reported success but produced no PDF.")


_cache: dict[tuple, Path] = {}
_cache_ts: float = 0.0


def generate_pdf(month: str | None = None, edition: int | None = None) -> tuple[Path, str]:
    """Produce (pdf_path, month_label). Regenerates only when inputs change."""
    global _cache_ts
    month = month or _latest_month()
    if month not in _available_months():
        raise FlashReportBuildError(
            f"No panel data for month {month}. Available months: {', '.join(_available_months())}."
        )
    edition = edition or 1
    csv_mtime = PANEL_CSV.stat().st_mtime
    key = (month, edition, csv_mtime)
    if key in _cache and _cache[key].exists():
        return _cache[key], _month_label(month)

    if time.monotonic() - _cache_ts < 10:
        _cache.clear()

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload_path = GENERATED_DIR / f"{month}_flash.json"
    out_path = OUT_DIR / f"FlashReport_{_month_label(month).replace(' ', '_')}.pdf"
    payload_path.write_text(json.dumps(_build_payload(month, edition), ensure_ascii=False), encoding="utf-8")

    _render(payload_path, out_path, edition)

    _cache.clear()
    _cache[key] = out_path
    _cache_ts = time.monotonic()
    return out_path, _month_label(month)