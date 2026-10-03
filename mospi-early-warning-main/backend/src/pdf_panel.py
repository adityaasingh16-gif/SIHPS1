"""
PDF Panel Extractor for MoSPI Dhrishti Flash Reports.

Parses monthly Flash Report PDFs (Table 6: All Ongoing Projects, plus
completed/new-project tables) into a flat panel DataFrame where every row is a
project-at-a-month snapshot. This becomes the real dataset for ML training.

Report schema (per Extraction):
  Sl.No | Project Name (Agency) (Project Code) (Legacy) (PMGID)
        | State | Date of Approval (Start Date) MM/YYYY
        | Original/Target DoC (Revised DoC) MM/YYYY
        | Original Cost / Revised Cost (Rs. Crore) | Cumulative Expenditure
        | Physical Progress (%)

Derived ML targets (computed from raw columns):
  cost_escalation_pct  = (revised_cost - original_cost) / original_cost * 100
  delay_months         = months between revised DoC and target DoC
  is_material_cost_overrun = cost_escalation_pct > MATERIAL_COST_OVERRUN_PCT
  is_deadline_missed       = delay_months > MISSED_DEADLINE_MONTHS
"""

import os
import re
import logging
import pdfplumber
import pandas as pd
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger("mospi_backend.pdf_panel")

TABLE6_HEADER = [
    "Sl.No",
    "Project Name",
    "State",
    "Date of Approval",
    "Target DoC",
    "Original Cost",
    "Cumulative Expenditure",
    "Physical Progress",
]

# Columns in an extracted Table 6 row (pdfplumber order)
# 0=Sl.No, 1=Project Name (Agency) (Code), 2=State, 3=Approval(Start),
# 4=Target(Revised) DoC, 5=Original/Revised Cost, 6=Cumulative Exp, 7=Physical %
N_SL = 0
N_NAME = 1
N_STATE = 2
N_APPROVAL = 3
N_DOC = 4
N_COST = 5
N_EXP = 6
N_PROG = 7

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}

# Full month names plus common 3-letter abbreviations, longest-first so full
# names ("june", "march") take precedence over prefixes ("jun", "mar").
_MONTH_LABELS = [
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
]
_MONTH_LABEL_RX = re.compile(
    r"(" + "|".join(sorted(_MONTH_LABELS, key=len, reverse=True)) + r")"
)


def _label_to_month(label: str) -> int:
    low = label.lower()
    if low in _MONTHS:
        return _MONTHS[low]
    return {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
        "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }.get(low, 0)


def report_month_from_filename(path: str) -> Tuple[int, int]:
    """Extract (month, year) from report filenames.

    Handles Flash Report names (FlashReport_July_2026.pdf,
    FlashReport_April2026.pdf) and Review Report names
    (ReviewReportSep25.pdf, Review Report Dec 25.pdf,
    CompleteReviewReportAugust2025.pdf).
    """
    base = os.path.basename(path)
    tokens = [t for t in re.split(r"[^A-Za-z0-9]+", base) if t]
    month = 0
    year = 0
    for tok in tokens:
        low = tok.lower()
        if month == 0:
            m = _MONTH_LABEL_RX.search(low)
            if m:
                month = _label_to_month(m.group(1))
        if year == 0:
            for m in re.finditer(r"((?:19|20)\d{2}|\d{2})", low):
                yy = int(m.group(1))
                year = yy if yy > 100 else 2000 + yy
                break
    return month, year


def _clean_cell(v) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return str(v).strip()
    s = str(v).replace("\x00", "").strip()
    return s if s and s != "-" else None


def _parse_mm_yyyy(text: Optional[str]) -> Optional[Tuple[int, int]]:
    """Parse 'MM/YYYY' -> (month, year). Handles '(07/2025)' and '07/2025'."""
    if not text:
        return None
    m = re.search(r"(\d{1,2})\s*/\s*(\d{4})", text)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _first_mm_yyyy(text: Optional[str]) -> Optional[Tuple[int, int]]:
    return _parse_mm_yyyy(text)


def _parenthesized_mm_yyyy(text: Optional[str]) -> Optional[Tuple[int, int]]:
    """Parse the LAST (MM/YYYY) in a cell, e.g. '(Revised DoC)'."""
    if not text:
        return None
    m = re.findall(r"\((\d{1,2})\s*/\s*(\d{4})\)", text)
    if not m:
        m = re.findall(r"(\d{1,2})\s*/\s*(\d{4})", text)
    if not m:
        return None
    mm, yy = m[-1]
    return int(mm), int(yy)


def _month_diff(start: Optional[Tuple[int, int]], end: Optional[Tuple[int, int]]) -> Optional[float]:
    if not start or not end:
        return None
    return (end[0] - start[0]) + 12 * (end[1] - start[1])


def _to_float(text: Optional[str]) -> Optional[float]:
    if text is None:
        return None
    s = text.replace(",", "").replace("₹", "").replace("Rs.", "").strip()
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _split_name_agency(code_text: Optional[str]) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Parses the Project Name / Agency / (Code) cell.
    Returns (name, agency, project_code).
    """
    if not code_text:
        return "", None, None
    lines = [ln.strip() for ln in code_text.split("\n") if ln.strip()]

    code = None
    code_m = re.search(r"\((\d{5,7})\)", "\n".join(lines))
    if code_m:
        code = code_m.group(1)

    name_lines = []
    agency = None
    for ln in lines:
        if re.match(r"^\(.*\)\s*$", ln) and ("[" in ln or "CO." in ln or "Ltd" in ln or "Limited" in ln or "Authority" in ln or "Corporation" in ln):
            agency = ln.strip("() ").strip()
            continue
        if code is not None and code in ln:
            continue
        if ln.startswith("(") and ln.endswith(")") and re.search(r"\d", ln):
            continue
        if not name_lines or len(ln) > 4:
            name_lines.append(ln)
        elif name_lines:
            name_lines[-1] += " " + ln
    name = " ".join(name_lines).strip()
    return name, agency, code


def _pad8(row) -> list:
    row = list(row)
    while len(row) < 8:
        row.append(None)
    return row[:8]


def _is_table6_header(row: list) -> bool:
    first = (_clean_cell(row[N_SL]) or "").strip().lower()
    prog = (_clean_cell(row[N_PROG]) or "").strip()
    return first in {"sl.no", "sl. no.", "sl. no", "sl no", "slno", "sl."} and "progress" in prog.lower()


def _is_section_header(row: list) -> Optional[str]:
    """Returns section text if the row is a lone ministry/sector header line."""
    if _clean_cell(row[N_SL]):
        return None
    cell = _clean_cell(row[N_NAME])
    if not cell:
        return None
    rest = [_clean_cell(row[i]) for i in (N_STATE, N_APPROVAL, N_DOC, N_COST, N_EXP, N_PROG)]
    if any(rest):
        return None
    return cell


def extract_table6_rows(page, department_hint: Optional[dict] = None) -> tuple:
    """
    Walks a page's tables for the *actual* Table 6 (All Ongoing Projects),
    which is anchored by its header row ["Sl.No", ..., "Physical Progress (%)"].
    Returns (project_row_dicts, section_headers_found).
    """
    tables = page.extract_tables()
    rows: List[Dict] = []
    section_headers: List[Dict] = []
    captured = False  # whether we've hit the Table 6 header on this page

    for table in tables:
        if not table:
            continue
        for raw in table:
            row = _pad8(raw)
            if not captured:
                if _is_table6_header(row):
                    captured = True
                continue

            if _is_table6_header(row):  # repeat header on continuation pages
                continue

            sect = _is_section_header(row)
            if sect:
                low = sect.lower()
                if ("ministry" in low or "national" in low or "directorate" in low or "department" in low):
                    section_headers.append({"ministry": sect, "sector": None})
                else:
                    section_headers.append({"sector": sect})
                if department_hint is not None:
                    department_hint.update(section_headers[-1])
                continue

            sl = _clean_cell(row[N_SL])
            name_cell = _clean_cell(row[N_NAME])
            if sl is None or "." in sl or not re.fullmatch(r"\d+", sl):
                continue
            if name_cell and "total" in name_cell.lower():
                continue

            name, agency, proj_code = _split_name_agency(name_cell)
            if not proj_code and not name:
                continue

            appr = _clean_cell(row[N_APPROVAL])
            doc = _clean_cell(row[N_DOC])
            cost = _clean_cell(row[N_COST])
            exp = _clean_cell(row[N_EXP])
            prog = _clean_cell(row[N_PROG])

            approval = _first_mm_yyyy(appr)
            start = _parenthesized_mm_yyyy(appr)
            target_doc = _first_mm_yyyy(doc)
            revised_doc = _parenthesized_mm_yyyy(doc)
            if target_doc == revised_doc:
                revised_doc = None  # no revision if identical to target

            costs = (cost or "").split("\n")
            original_cost = _to_float(costs[0]) if costs else None
            revised_cost = _to_float(costs[1]) if len(costs) > 1 else None
            if revised_cost is None:
                revised_cost = original_cost

            hint = department_hint or {}
            rows.append({
                "project_code": proj_code,
                "project_name": name,
                "agency": agency,
                "ministry": hint.get("ministry"),
                "sector": hint.get("sector"),
                "state": _clean_cell(row[N_STATE]),
                "approval_month": approval[0] if approval else None,
                "approval_year": approval[1] if approval else None,
                "start_month": start[0] if start else None,
                "start_year": start[1] if start else None,
                "target_doc_month": target_doc[0] if target_doc else None,
                "target_doc_year": target_doc[1] if target_doc else None,
                "revised_doc_month": revised_doc[0] if revised_doc else None,
                "revised_doc_year": revised_doc[1] if revised_doc else None,
                "original_cost_crore": original_cost,
                "revised_cost_crore": revised_cost,
                "cumulative_expenditure_crore": _to_float(exp),
                "physical_progress_pct": _to_float(prog),
            })
    return rows, section_headers


def parse_report(path: str, report_month: Optional[Tuple[int, int]] = None) -> pd.DataFrame:
    """Parses a single Flash Report PDF into a panel DataFrame."""
    if report_month is None:
        report_month = report_month_from_filename(path)
    rm, ry = report_month

    # State: current ministry/sector persists across project rows until a new
    # section header appears. Rows in Table 6 don't carry ministry/sector, so we
    # track them from the section headers interspersed between project rows.
    current = {"ministry": None, "sector": None}
    all_rows: List[Dict] = []
    records = []

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            rows, headers = extract_table6_rows(page, current)
            for hdr in headers:
                current.update(hdr)
            # Re-run after header scan so rows on the same page inherit headers
            for r in rows:
                if r["ministry"] is None:
                    r["ministry"] = current["ministry"]
                if r["sector"] is None:
                    r["sector"] = current["sector"]
                r["report_month"] = rm
                r["report_year"] = ry
                records.append(r)

    df = pd.DataFrame(records) if records else pd.DataFrame()
    if not df.empty:
        df = _derive_targets(df)
    return df


def _derive_targets(df: pd.DataFrame) -> pd.DataFrame:
    """Adds derived ML features/targets from raw report columns."""
    df["cost_escalation_pct"] = df.apply(
        lambda r: ((r["revised_cost_crore"] - r["original_cost_crore"]) / r["original_cost_crore"] * 100)
        if r["revised_cost_crore"] is not None and r["original_cost_crore"] else None,
        axis=1,
    )
    start = list(zip(df["approval_month"], df["approval_year"]))
    target = list(zip(df["target_doc_month"], df["target_doc_year"]))
    revised = list(zip(df["revised_doc_month"], df["revised_doc_year"]))
    df["planned_duration_months"] = [
        _month_diff(s, t) for s, t in zip(start, target)
    ]
    df["delay_months"] = [
        _month_diff(t, r) if (t and r) else None for t, r in zip(target, revised)
    ]
    df["is_material_cost_overrun"] = (df["cost_escalation_pct"] > 10.0).astype(int)
    df["is_deadline_missed"] = (df["delay_months"] > 3.0).astype(int)
    return df


def build_panel(dataset_dir: str) -> pd.DataFrame:
    """Parses every Flash Report PDF in a directory into one panel DataFrame."""
    files = sorted(
        f for f in os.listdir(dataset_dir)
        if f.lower().endswith(".pdf")
    )
    frames = []
    for fn in files:
        path = os.path.join(dataset_dir, fn)
        try:
            rm, ry = report_month_from_filename(path)
            if (rm, ry) == (0, 0):
                logger.warning("Skipping unparseable month filename: %s", fn)
                continue
            df = parse_report(path, (rm, ry))
            logger.info("%s: %d project rows (month %d/%d)", fn, len(df), rm, ry)
            frames.append(df)
        except Exception as e:
            logger.error("Failed to parse %s: %s", fn, e)
    if not frames:
        return pd.DataFrame()
    panel = pd.concat(frames, ignore_index=True)
    panel["snapshot_full"] = panel["report_year"] * 100 + panel["report_month"]
    return panel