"""
Knowledge-Graph builder for MoSPI Dhrishti.

Builds an explorable graph linking projects, ministries, implementing agencies,
sectors and the risk drivers (SHAP factors) that explain each project's latest
prediction. Also emits narrative, relationship-aware report sections.
"""

from collections import OrderedDict


def _add_node(nodes, ntype, nid, label, **meta):
    key = f"{ntype}:{nid}"
    if key not in nodes:
        nodes[key] = {"id": nid, "type": ntype, "label": label, "meta": meta}
    else:
        nodes[key]["meta"].update({k: v for k, v in meta.items() if v is not None})
    return key


def _add_edge(edges, key_a, key_b, etype):
    if key_a == key_b:
        return
    edge = f"{key_a}|{etype}|{key_b}"
    if edge in edges:
        return
    edges[edge] = {"source": key_a, "target": key_b, "type": etype}


def build_graph(db, project_id=None, ministry=None, limit=150):
    """Build {nodes, edges, meta} from the live database."""
    from sqlalchemy import and_, func

    from . import models

    nodes = OrderedDict()
    edges = OrderedDict()

    latest = (
        db.query(models.Prediction.project_id, func.max(models.Prediction.snapshot_month).label("m"))
        .group_by(models.Prediction.project_id)
        .subquery()
    )
    q = (
        db.query(models.Project, models.Prediction)
        .join(latest, models.Project.project_id == latest.c.project_id)
        .join(models.Prediction, and_(models.Prediction.project_id == latest.c.project_id, models.Prediction.snapshot_month == latest.c.m))
    )
    if project_id:
        q = q.filter(models.Project.project_id == project_id)
    if ministry:
        q = q.filter(models.Project.ministry.ilike(f"%{ministry}%"))
    q = q.order_by(models.Prediction.composite_risk_score.desc()).limit(limit)
    rows = q.all()

    for proj, pred in rows:
        p_key = _add_node(nodes, "project", proj.project_id, f"Project {proj.project_id}",
                          sector=proj.sector, ministry=proj.ministry,
                          score=round(pred.composite_risk_score, 1), tier=pred.risk_tier)
        agency = (proj.implementing_agency or "").strip() if proj.implementing_agency else ""
        m_key = _add_node(nodes, "ministry", proj.ministry, proj.ministry)
        s_key = _add_node(nodes, "sector", proj.sector, proj.sector)
        _add_edge(edges, p_key, m_key, "under_ministry")
        _add_edge(edges, p_key, s_key, "in_sector")

        if agency and agency.lower() not in ("nan", "none", "null", "-"):
            a_key = _add_node(nodes, "agency", agency, agency)
            _add_edge(edges, p_key, a_key, "implemented_by")
            nodes[p_key]["meta"]["agency"] = agency

        shap_rows = (
            db.query(models.SHAPExplanation)
            .filter(models.SHAPExplanation.prediction_id == pred.id)
            .order_by(models.SHAPExplanation.rank)
            .limit(3)
            .all()
        )
        for s in shap_rows:
            r_label = f"{s.factor_name} ({'increases risk' if 'increase' in s.direction else 'decreases risk'})"
            r_key = _add_node(nodes, "risk", s.factor_name, r_label, direction=s.direction)
            _add_edge(edges, p_key, r_key, "driven_by")

    deps = (
        db.query(models.ProjectDependency)
        .filter(models.ProjectDependency.relation_type.in_(["shared_agency", "shared_contractor"]))
        .all()
    )
    seen_proj = {proj.project_id for proj, _ in rows}
    for d in deps:
        if d.project_id not in seen_proj or d.related_project_id not in seen_proj:
            continue
        sa = f"project:{d.project_id}"
        sb = f"project:{d.related_project_id}"
        if sa in nodes and sb in nodes:
            _add_edge(edges, sa, sb, d.relation_type)

    return {
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
        "meta": {"projects": len(rows), "nodes": len(nodes), "edges": len(edges)},
    }


def build_report(db, project_id=None, ministry=None, limit=100) -> dict:
    """Narrative, relationship-aware report describing what the graph reveals."""
    from sqlalchemy import and_, func

    from . import models

    latest = (
        db.query(models.Prediction.project_id, func.max(models.Prediction.snapshot_month).label("m"))
        .group_by(models.Prediction.project_id)
        .subquery()
    )
    q = (
        db.query(models.Project, models.Prediction)
        .join(latest, models.Project.project_id == latest.c.project_id)
        .join(models.Prediction, and_(models.Prediction.project_id == latest.c.project_id, models.Prediction.snapshot_month == latest.c.m))
    )
    if project_id:
        q = q.filter(models.Project.project_id == project_id)
    if ministry:
        q = q.filter(models.Project.ministry.ilike(f"%{ministry}%"))
    q = q.order_by(models.Prediction.composite_risk_score.desc()).limit(limit)
    rows = q.all()

    total = len(rows)
    critical = [r for r in rows if r.Prediction.risk_tier == "Critical"]
    high = [r for r in rows if r.Prediction.risk_tier == "High"]

    sections = []
    header = "Knowledge-Graph Risk Report"
    if project_id:
        header += f" — Project {project_id}"
    elif ministry:
        header += f" — {ministry}"
    intro = (
        f"This report covers {total} project(s). {len(critical)} are in the Critical tier and "
        f"{len(high)} in the High tier. The graph links each project to its ministry, sector, "
        f"implementing agency and the SHAP risk drivers of its latest prediction, plus "
        f"shared-agency and shared-contractor links between projects."
    )
    sections.append({"heading": "Overview", "body": intro})

    agency_risk = {}
    for proj, pred in rows:
        key = proj.implementing_agency
        agency_risk.setdefault(key, {"count": 0, "worst": 0.0, "projects": []})
        agency_risk[key]["count"] += 1
        agency_risk[key]["worst"] = max(agency_risk[key]["worst"], pred.composite_risk_score)
        if pred.risk_tier in ("Critical", "High") and len(agency_risk[key]["projects"]) < 3:
            agency_risk[key]["projects"].append(proj.project_id)

    if agency_risk:
        top_agencies = sorted(agency_risk.items(), key=lambda kv: kv[1]["worst"], reverse=True)[:5]
        body_lines = ["Implementing agencies by peak risk exposure:"]
        for name, info in top_agencies:
            body_lines.append(
                f"- {name}: {info['count']} project(s), worst score {info['worst']:.1f}"
                + (f" (e.g. {', '.join(info['projects'])})" if info["projects"] else "")
            )
        sections.append({"heading": "Agency exposure", "body": "\n".join(body_lines)})

    risk_freq = {}
    for proj, pred in rows:
        shap_rows = (
            db.query(models.SHAPExplanation)
            .filter(models.SHAPExplanation.prediction_id == pred.id)
            .order_by(models.SHAPExplanation.rank)
            .limit(3)
            .all()
        )
        for s in shap_rows:
            key = (s.factor_name, s.direction)
            risk_freq[key] = risk_freq.get(key, 0) + 1

    if risk_freq:
        top_risks = sorted(risk_freq.items(), key=lambda kv: kv[1], reverse=True)[:6]
        body_lines = ["Most frequent risk drivers across these projects:"]
        for (name, direction), count in top_risks:
            body_lines.append(f"- {name} ({direction.replace('_', ' ')}): appears {count} time(s)")
        sections.append({"heading": "Dominant risk drivers", "body": "\n".join(body_lines)})

    if critical:
        body_lines = ["Highest-priority relationships to investigate:"]
        for proj, pred in critical[:5]:
            body_lines.append(
                f"- Project {proj.project_id}: score {pred.composite_risk_score:.1f} ({pred.risk_tier}); "
                f"{proj.sector} under {proj.ministry}, implemented by {proj.implementing_agency}."
            )
        sections.append({"heading": "Critical project relationships", "body": "\n".join(body_lines)})

    deps = (
        db.query(models.ProjectDependency)
        .filter(models.ProjectDependency.relation_type == "shared_contractor")
        .all()
    )
    dependent = {}
    for d in deps:
        if d.project_id not in {r.Project.project_id for r in rows}:
            continue
        dependent.setdefault(d.project_id, []).append(d.related_project_id)
    if dependent:
        body_lines = ["Projects sharing contractors with other flagged projects:"]
        for pid, rels in list(dependent.items())[:8]:
            body_lines.append(f"- {pid} shares a contractor with {', '.join(rels[:4])}")
        sections.append({"heading": "Contractor dependencies", "body": "\n".join(body_lines)})

    return {
        "title": header,
        "generated_for": {"project_id": project_id, "ministry": ministry, "projects": total},
        "sections": sections,
    }