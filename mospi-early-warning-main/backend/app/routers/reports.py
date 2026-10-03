"""
Real-data report generator & download router.

Produces self-contained, print-ready HTML reports (browser "Save as PDF") and CSV
exports from the live database. All figures come from the real MoSPI panel trained
predictions already stored in the DB.
"""

import csv
import html
import io
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import crud, flash_report, models
from ..database import get_db

router = APIRouter(prefix="/reports", tags=["Reports"])

TIER_ORDER = {"Critical": 3, "High": 2, "Medium": 1, "Low": 0}
TIER_COLOR = {
    "Critical": "#dc2626",
    "High": "#f59e0b",
    "Medium": "#eab308",
    "Low": "#10b981",
}


def _esc(value):
    return html.escape(str(value if value is not None else "-"))


def _num(value, digits=1):
    if value is None:
        return "-"
    return f"{float(value):.{digits}f}"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")


def _latest(db: Session):
    return crud.get_latest_prediction_subquery(db)


def _stats(db: Session) -> dict:
    latest = _latest(db)
    rows = (
        db.query(models.Project, models.Prediction)
        .join(latest, models.Project.project_id == latest.c.project_id)
        .join(
            models.Prediction,
            models.Prediction.project_id == latest.c.project_id,
        )
        .filter(models.Prediction.snapshot_month == latest.c.max_month)
        .all()
    )
    scores = [pred.composite_risk_score for _, pred in rows]
    tiers = {}
    for _, pred in rows:
        tiers[pred.risk_tier] = tiers.get(pred.risk_tier, 0) + 1
    alerts = crud.get_alerts(db)
    severity = {}
    alert_type = {}
    for a in alerts:
        severity[a.severity] = severity.get(a.severity, 0) + 1
        alert_type[a.alert_type] = alert_type.get(a.alert_type, 0) + 1
    return {
        "n_projects": db.query(models.Project).count(),
        "n_snapshots": db.query(models.Snapshot).count(),
        "n_predictions": db.query(models.Prediction).count(),
        "n_shap": db.query(models.SHAPExplanation).count(),
        "avg_score": (sum(scores) / len(scores)) if scores else 0.0,
        "max_score": max(scores) if scores else 0.0,
        "tiers": tiers,
        "alerts_total": len(alerts),
        "severity": severity,
        "alert_type": alert_type,
    }


def _top_projects(db: Session, limit: int):
    latest = _latest(db)
    rows = (
        db.query(models.Project, models.Prediction)
        .join(latest, models.Project.project_id == latest.c.project_id)
        .join(
            models.Prediction,
            models.Prediction.project_id == latest.c.project_id,
        )
        .filter(models.Prediction.snapshot_month == latest.c.max_month)
        .order_by(models.Prediction.composite_risk_score.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "project_id": proj.project_id,
            "sector": proj.sector,
            "ministry": proj.ministry,
            "agency": proj.implementing_agency,
            "score": round(pred.composite_risk_score, 1),
            "tier": pred.risk_tier,
            "cost_prob": round(pred.cost_overrun_probability * 100, 1),
            "delay_prob": round(pred.delay_probability * 100, 1),
            "trend": pred.risk_trend,
        }
        for proj, pred in rows
    ]


def _ministry_risk(db: Session) -> list:
    latest = _latest(db)
    rows = (
        db.query(models.Project, models.Prediction)
        .join(latest, models.Project.project_id == latest.c.project_id)
        .join(
            models.Prediction,
            models.Prediction.project_id == latest.c.project_id,
        )
        .filter(models.Prediction.snapshot_month == latest.c.max_month)
        .all()
    )
    buckets = {}
    for proj, pred in rows:
        key = proj.ministry or "Unknown"
        entry = buckets.setdefault(key, {"projects": 0, "scores": [], "critical": 0, "worst": None})
        entry["projects"] += 1
        entry["scores"].append(pred.composite_risk_score)
        if pred.risk_tier == "Critical":
            entry["critical"] += 1
        if entry["worst"] is None or pred.composite_risk_score > entry["worst"][1]:
            entry["worst"] = (proj.project_id, pred.composite_risk_score)
    out = []
    for name, entry in buckets.items():
        out.append(
            {
                "ministry": name,
                "projects": entry["projects"],
                "avg": round(sum(entry["scores"]) / len(entry["scores"]), 1),
                "critical": entry["critical"],
                "worst_id": entry["worst"][0],
                "worst_score": round(entry["worst"][1], 1),
            }
        )
    out.sort(key=lambda r: (-r["avg"], -r["critical"]))
    return out


def _page(title: str, subtitle: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{_esc(title)}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; color: #0f172a; margin: 0; background: #f1f5f9; }}
  .sheet {{ max-width: 900px; margin: 24px auto; background: #fff; border: 1px solid #e2e8f0; border-radius: 14px; padding: 34px 40px 26px; }}
  .brand {{ display: flex; align-items: center; gap: 12px; border-bottom: 3px solid #4f46e5; padding-bottom: 16px; }}
  .brand .logo {{ width: 42px; height: 42px; border-radius: 10px; background: linear-gradient(135deg,#4f46e5,#7c3aed); color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 18px; }}
  .brand h1 {{ font-size: 20px; margin: 0; color: #1e293b; }}
  .brand p {{ margin: 2px 0 0; font-size: 12px; color: #64748b; }}
  .sub {{ color:#475569; margin: 12px 0 20px; font-size: 13px; }}
  .chips {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0 24px; }}
  .chip {{ background: #eef2ff; border: 1px solid #e0e7ff; color: #4338ca; border-radius: 999px; padding: 6px 12px; font-size: 12px; font-weight: 600; }}
  h2 {{ font-size: 15px; color: #1e293b; margin: 26px 0 10px; border-left: 4px solid #4f46e5; padding-left: 10px; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }}
  .card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px 14px; }}
  .card .k {{ font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: .05em; }}
  .card .v {{ font-size: 20px; font-weight: 800; color: #1e293b; margin-top: 2px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 8px 0 6px; font-size: 12px; }}
  th {{ text-align: left; background: #eef2ff; color: #3730a3; padding: 8px 10px; font-size: 11px; text-transform: uppercase; letter-spacing: .04em; }}
  td {{ padding: 8px 10px; border-bottom: 1px solid #e2e8f0; }}
  tr:nth-child(even) td {{ background: #f8fafc; }}
  .tier {{ display: inline-block; padding: 2px 8px; border-radius: 999px; color: #fff; font-size: 11px; font-weight: 700; }}
  .score {{ font-weight: 700; }}
  .footer {{ margin-top: 24px; padding-top: 12px; border-top: 1px solid #e2e8f0; font-size: 11px; color: #94a3b8; display: flex; justify-content: space-between; }}
  @media print {{
    body {{ background: #fff; }}
    .sheet {{ border: none; box-shadow: none; margin: 0; border-radius: 0; padding: 0; }}
    .no-print {{ display: none !important; }}
    a {{ text-decoration: none; color: inherit; }}
  }}
</style>
</head>
<body>
<div class="sheet">
  <div class="brand">
    <div class="logo">P</div>
    <div>
      <h1>Dhrishti · {_esc(title)}</h1>
      <p>MoSPI Central Sector Infrastructure Early-Warning &amp; Decision Support (SIH 26103)</p>
    </div>
  </div>
  <p class="sub">{_esc(subtitle)}</p>
  {body}
  <div class="footer">
    <span>Generated {_esc(_now())} · Real-data ML predictions (XGBoost + TreeSHAP, Platt-calibrated)</span>
    <span class="no-print"><a href="#" onclick="window.print();return false;">Print / Save as PDF</a></span>
  </div>
</div>
</body>
</html>"""


def _tier_chip(tier: str) -> str:
    color = TIER_COLOR.get(tier, "#64748b")
    return f'<span class="tier" style="background:{color}">{_esc(tier)}</span>'


def _table(headers, rows_html):
    thead = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    return f"<table><thead><tr>{thead}</tr></thead><tbody>{''.join(rows_html)}</tbody></table>"


def _executive_html(db: Session) -> str:
    s = _stats(db)
    tiers_html = "".join(
        f'<span class="chip">{_esc(t)}: {n} projects</span>'
        for t in ("Critical", "High", "Medium", "Low")
        if (n := s["tiers"].get(t, 0))
    )
    cards = f"""
    <div class="cards">
      <div class="card"><div class="k">Real Projects</div><div class="v">{s['n_projects']:,}</div></div>
      <div class="card"><div class="k">Snapshots</div><div class="v">{s['n_snapshots']:,}</div></div>
      <div class="card"><div class="k">Predictions</div><div class="v">{s['n_predictions']:,}</div></div>
      <div class="card"><div class="k">SHAP Records</div><div class="v">{s['n_shap']:,}</div></div>
      <div class="card"><div class="k">Avg Risk Score</div><div class="v">{_num(s['avg_score'])}</div></div>
      <div class="card"><div class="k">Worst Score</div><div class="v" style="color:#dc2626">{_num(s['max_score'])}</div></div>
      <div class="card"><div class="k">Active Alerts</div><div class="v" style="color:#dc2626">{s['alerts_total']}</div></div>
    </div>
    <h2>Risk Tier Distribution</h2>
    <div class="chips">{tiers_html}</div>
    <h2>Early-Warning Alerts</h2>
    <p style="font-size:12px;color:#475569">Critical: <b>{s['severity'].get('Critical', 0)}</b> · High: <b>{s['severity'].get('High', 0)}</b> · trend-increasing: <b>{s['alert_type'].get('trend_increasing', 0)}</b> · tier-crossings: <b>{s['alert_type'].get('tier_boundary_crossed', 0)}</b></p>
    """
    top = _top_projects(db, 10)
    rows = []
    for r in top:
        rows.append(
            "<tr>"
            f"<td><b>{_esc(r['project_id'])}</b></td>"
            f"<td>{_esc(r['sector'])}</td>"
            f"<td>{_esc(r['ministry'])}</td>"
            f"<td>{_esc(r['agency'])}</td>"
            f'<td class="score">{r["score"]}</td>'
            f"<td>{_tier_chip(r['tier'])}</td>"
            "</tr>"
        )
    cards += "<h2>Top 10 Riskiest Projects</h2>" + _table(
        ["Project", "Sector", "Ministry", "Agency", "Risk Score", "Tier"], rows
    )
    return cards


def _projects_table(db: Session, limit: int) -> str:
    top = _top_projects(db, limit)
    rows = []
    for r in top:
        rows.append(
            "<tr>"
            f"<td><b>{_esc(r['project_id'])}</b></td>"
            f"<td>{_esc(r['sector'])}</td>"
            f"<td>{_esc(r['ministry'])}</td>"
            f"<td>{_esc(r['agency'])}</td>"
            f'<td class="score">{r["score"]}</td>'
            f"<td>{_tier_chip(r['tier'])}</td>"
            f'<td>{r["cost_prob"]}%</td>'
            f'<td>{r["delay_prob"]}%</td>'
            f"<td>{_esc(r['trend'])}</td>"
            "</tr>"
        )
    return _table(
        ["Project", "Sector", "Ministry", "Agency", "Score", "Tier", "Cost O/R Prob", "Delay Prob", "Trend"],
        rows,
    )


def _alerts_table(db: Session) -> str:
    alerts = crud.get_alerts(db)
    rows = []
    for a in alerts:
        chip = (
            '<span class="tier" style="background:#dc2626">Critical</span>'
            if a.severity == "Critical"
            else '<span class="tier" style="background:#f59e0b">High</span>'
        )
        rows.append(
            "<tr>"
            f"<td><b>{_esc(a.project_id)}</b></td>"
            f"<td>{chip}</td>"
            f"<td>{_esc(a.message)}</td>"
            f'<td class="score">{a.composite_risk_score}</td>'
            f"<td>{_esc(a.alert_type)}</td><td>{_esc(a.timestamp)}</td>"
            "</tr>"
        )
    return _table(["Project", "Severity", "Message", "Score", "Type", "Time"], rows) if alerts else "<p>No active alerts.</p>"


def _ministries_table(db: Session) -> str:
    rows = []
    for r in _ministry_risk(db):
        rows.append(
            "<tr>"
            f"<td><b>{_esc(r['ministry'])}</b></td>"
            f'<td>{r["projects"]}</td>'
            f'<td class="score">{r["avg"]}</td>'
            f'<td style="color:#dc2626">{r["critical"]}</td>'
            f"<td>{_esc(r['worst_id'])} ({r['worst_score']})</td>"
            "</tr>"
        )
    return _table(["Ministry", "Projects", "Avg Risk", "Critical", "Worst Project"], rows)


def _project_html(db: Session, project_id: str) -> str:
    proj = db.query(models.Project).filter(models.Project.project_id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    pred = (
        db.query(models.Prediction)
        .filter(models.Prediction.project_id == project_id)
        .order_by(models.Prediction.snapshot_month.desc())
        .first()
    )
    if not pred:
        raise HTTPException(status_code=404, detail="No prediction for project")
    shap = (
        db.query(models.SHAPExplanation)
        .filter(models.SHAPExplanation.prediction_id == pred.id)
        .order_by(models.SHAPExplanation.rank)
        .all()
    )
    snap = (
        db.query(models.Snapshot)
        .filter(models.Snapshot.project_id == project_id, models.Snapshot.snapshot_month == pred.snapshot_month)
        .first()
    )
    cards = f"""
    <div class="cards">
      <div class="card"><div class="k">Project</div><div class="v" style="font-size:15px">{_esc(project_id)}</div></div>
      <div class="card"><div class="k">Sector</div><div class="v" style="font-size:15px">{_esc(proj.sector)}</div></div>
      <div class="card"><div class="k">Ministry</div><div class="v" style="font-size:15px">{_esc(proj.ministry)}</div></div>
      <div class="card"><div class="k">Agency</div><div class="v" style="font-size:15px">{_esc(proj.implementing_agency)}</div></div>
      <div class="card"><div class="k">Original Cost (₹ cr)</div><div class="v">{_num(proj.original_cost_crore, 0)}</div></div>
      <div class="card"><div class="k">Duration (months)</div><div class="v">{proj.original_duration_months}</div></div>
      <div class="card"><div class="k">Risk Score</div><div class="v" style="color:{TIER_COLOR.get(pred.risk_tier, '#0f172a')}">{_num(pred.composite_risk_score)}</div></div>
      <div class="card"><div class="k">Tier</div><div style="margin-top:4px">{_tier_chip(pred.risk_tier)}</div></div>
      <div class="card"><div class="k">Cost O/R Probability</div><div class="v">{_num(pred.cost_overrun_probability * 100, 1)}%</div></div>
      <div class="card"><div class="k">Delay Probability</div><div class="v">{_num(pred.delay_probability * 100, 1)}%</div></div>
    </div>
    """
    snap_rows = ""
    if snap:
        snap_rows = _table(
            ["Physical Progress", "Financial Progress", "Expenditure (₹ cr)", "Milestones", "Remarks"],
            [
                "<tr>"
                f"<td>{_num(snap.physical_progress_pct, 1)}%</td>"
                f"<td>{_num(snap.financial_progress_pct, 1)}%</td>"
                f"<td>{_num(snap.cumulative_expenditure_crore, 1)}</td>"
                f"<td>{snap.milestones_achieved} / {snap.milestones_planned}</td>"
                f"<td>{_esc(snap.remarks_text or '-')}</td>"
                "</tr>"
            ],
        )
        cards += "<h2>Latest Snapshot (month {})</h2>".format(snap.snapshot_month) + snap_rows
    shap_rows = []
    for s in shap:
        color = "#dc2626" if s.direction == "increases_risk" else "#10b981"
        lbl = "increases risk" if s.direction == "increases_risk" else "decreases risk"
        shap_rows.append(
            "<tr>"
            f"<td>#{s.rank} {_esc(s.factor_name)}</td>"
            f'<td class="score" style="color:{color}">{_num(s.impact_value)}</td>'
            f"<td>{_esc(lbl)}</td>"
            "</tr>"
        )
    if shap_rows:
        cards += "<h2>Risk Drivers (TreeSHAP attribution)</h2>" + _table(["Driver", "Impact", "Direction"], shap_rows)
    history = (
        db.query(models.Prediction)
        .filter(models.Prediction.project_id == project_id)
        .order_by(models.Prediction.snapshot_month.asc())
        .limit(24)
        .all()
    )
    hist_rows = []
    for p in history:
        hist_rows.append(
            "<tr>"
            f"<td>{p.snapshot_month}</td>"
            f'<td class="score">{_num(p.composite_risk_score)}</td>'
            f"<td>{_tier_chip(p.risk_tier)}</td>"
            f"<td>{_esc(p.risk_trend)}</td>"
            "</tr>"
        )
    if hist_rows:
        cards += "<h2>Risk Score History</h2>" + _table(["Month", "Score", "Tier", "Trend"], hist_rows)
    return cards


def _csv_response(filename: str, headers: list, rows: list) -> StreamingResponse:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/executive", response_class=HTMLResponse)
def report_executive(db: Session = Depends(get_db)):
    """Full-platform executive summary as a printable HTML report."""
    s = _stats(db)
    subtitle = (
        f"Executive Overview · {s['n_projects']:,} real projects · "
        f"{s['n_snapshots']:,} monthly snapshots · {s['n_predictions']:,} ML predictions"
    )
    return _page("Executive Risk Overview", subtitle, _executive_html(db))


@router.get("/projects")
def report_projects(
    db: Session = Depends(get_db),
    format: str = Query("html", pattern="^(html|csv)$"),
    limit: int = Query(200, ge=1, le=2000),
):
    """Ranked project risk table — printable HTML or CSV export."""
    rows = _top_projects(db, limit)
    if format == "csv":
        return _csv_response(
            "dhrishti_projects_risk.csv",
            ["project_id", "sector", "ministry", "agency", "risk_score", "risk_tier", "cost_overrun_prob_pct", "delay_prob_pct", "trend"],
            [[r["project_id"], r["sector"], r["ministry"], r["agency"], r["score"], r["tier"], r["cost_prob"], r["delay_prob"], r["trend"]] for r in rows],
        )
    subtitle = f"Ranked project risk register · top {len(rows)} projects by calibrated composite risk score"
    return _page("Project Risk Register", subtitle, _projects_table(db, limit))


@router.get("/alerts")
def report_alerts(
    db: Session = Depends(get_db),
    format: str = Query("html", pattern="^(html|csv)$"),
):
    """Active early-warning alert register — printable HTML or CSV export."""
    alerts = crud.get_alerts(db)
    if format == "csv":
        return _csv_response(
            "dhrishti_alerts.csv",
            ["alert_id", "project_id", "severity", "risk_tier", "composite_risk_score", "alert_type", "message", "timestamp"],
            [[a.id, a.project_id, a.severity, a.risk_tier, a.composite_risk_score, a.alert_type, a.message, a.timestamp] for a in alerts],
        )
    subtitle = f"Early-Warning Alert Register · {len(alerts)} active signals"
    return _page("Early-Warning Registers", subtitle, _alerts_table(db))


@router.get("/ministries", response_class=HTMLResponse)
def report_ministries(db: Session = Depends(get_db)):
    """Ministry-wise risk distribution report."""
    return _page(
        "Ministry Risk Distribution",
        "Average calibrated risk and critical-project count per ministry",
        _ministries_table(db),
    )


@router.get("/project/{project_id}", response_class=HTMLResponse)
def report_project(project_id: str, db: Session = Depends(get_db)):
    """Single-project diagnostic report: fundamentals, ML prediction, SHAP drivers, history."""
    return _page(f"Project {project_id}", "Single-project ML diagnostic & risk report", _project_html(db, project_id))


@router.get("/flash")
def report_flash(
    month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$",
                                 description="Report month YYYY-MM; defaults to the latest month in the panel"),
    edition: Optional[int] = Query(None, ge=1,
                                   description="Edition number; defaults to 1"),
):
    """MoSPI-style Flash Report rendered to PDF from the live OMS panel.

    First-hit generation shells out to the 'reportgen' conda env (WeasyPrint) and
    can take a minute or two; subsequent hits reuse the cached PDF.
    """
    try:
        pdf_path, label = flash_report.generate_pdf(month=month, edition=edition)
    except flash_report.FlashReportBuildError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    filename = f"FlashReport_{label.replace(' ', '_')}.pdf"
    return Response(
        pdf_path.read_bytes(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )