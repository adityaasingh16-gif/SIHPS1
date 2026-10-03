"""Data aggregation layer.

Every number in the report is derived here from the validated :class:`InputReport`.
``ReconciliationError`` is raised when the appendix grand totals disagree with the
KPI cards, so a bad dataset can never produce a silently wrong edition.
"""
from __future__ import annotations

from collections import Counter, OrderedDict
from dataclasses import dataclass, field

from .models import InputReport
from .formatters import pct as _pct


class ReconciliationError(ValueError):
    """Grand totals disagree between independently derived aggregations."""


@dataclass
class MoneyKPI:
    label: str
    value: float
    colour: str = "navy"


@dataclass
class CountKPI:
    label: str
    value: int
    colour: str = "navy"


@dataclass
class Bucket:
    name: str
    count: int
    original_cost: float
    revised_cost: float
    expenditure: float
    avg_physical: float
    avg_financial: float


@dataclass
class OverviewAgg:
    ongoing_count: int
    line_ministries: int
    north_east_count: int
    original_cost: float
    revised_cost: float
    expenditure: float
    on_track: int
    avg_physical: float
    avg_financial: float
    cost_effectiveness_pct: float          # expenditure / revised cost * 100
    completed_count: int
    completed_cost: float
    newly_added_count: int
    newly_added_cost: float
    mega_count: int
    mega_value: float
    major_count: int
    major_value: float
    buckets: list[Bucket] = field(default_factory=list)
    completed_list: list = field(default_factory=list)
    newly_added_list: list = field(default_factory=list)


@dataclass
class GroupAgg:
    key: str
    label: str
    count: int
    original_cost: float
    revised_cost: float
    expenditure: float
    avg_physical: float
    mega_count: int = 0
    mega_value: float = 0.0
    major_count: int = 0
    major_value: float = 0.0
    buckets: list[Bucket] = field(default_factory=list)
    projects: list = field(default_factory=list)


def _rounded(value: float) -> float:
    return round(value, 4)


def _sum(values: list[float]) -> float:
    return _rounded(sum(values))


def build_buckets(projects: list) -> list[Bucket]:
    edges = [(0, 20), (21, 40), (41, 60), (61, 80), (81, 100)]
    out: list[Bucket] = []
    for lo, hi in edges:
        rows = [p for p in projects if lo <= p.physical_progress_pct <= hi]
        n = len(rows)
        out.append(
            Bucket(
                name=f"{lo}-{hi}" if lo else "0-20",
                count=n,
                original_cost=_rounded(sum(p.original_cost for p in rows)),
                revised_cost=_rounded(sum(p.revised_cost for p in rows)),
                expenditure=_rounded(sum(p.cumulative_expenditure for p in rows)),
                avg_physical=_rounded(sum(p.physical_progress_pct for p in rows) / n) if n else 0,
                avg_financial=_rounded(sum(p.financial_progress_pct for p in rows) / n) if n else 0,
            )
        )
    return out


def build_overview(report: InputReport) -> OverviewAgg:
    ongoing = report.ongoing
    completed_list = sorted(report.completed, key=lambda p: (p.project_id,))
    newly_list = sorted(report.newly_added, key=lambda p: (p.project_id,))

    orig = _sum([p.original_cost for p in ongoing])
    rev = _sum([p.revised_cost for p in ongoing])
    exp = _sum([p.cumulative_expenditure for p in ongoing])
    pct_val = _rounded(exp / rev * 100) if rev > 0 else 0.0
    mega = [p for p in ongoing if p.is_mega]
    major = [p for p in ongoing if not p.is_mega]

    return OverviewAgg(
        ongoing_count=len(ongoing),
        line_ministries=len({p.ministry for p in ongoing}),
        north_east_count=len([p for p in ongoing if p.is_north_east]),
        original_cost=orig,
        revised_cost=rev,
        expenditure=exp,
        on_track=len([p for p in ongoing if p.physical_progress_pct >= 80]),
        avg_physical=_rounded(sum(p.physical_progress_pct for p in ongoing) / len(ongoing)) if ongoing else 0,
        avg_financial=_rounded(sum(p.financial_progress_pct for p in ongoing) / len(ongoing)) if ongoing else 0,
        cost_effectiveness_pct=pct_val,
        completed_count=len(completed_list),
        completed_cost=_sum([p.original_cost for p in completed_list]),
        newly_added_count=len(newly_list),
        newly_added_cost=_sum([p.original_cost for p in newly_list]),
        mega_count=len(mega),
        mega_value=_sum([p.original_cost for p in mega]),
        major_count=len(major),
        major_value=_sum([p.original_cost for p in major]),
        buckets=build_buckets(ongoing),
        completed_list=completed_list,
        newly_added_list=newly_list,
    )


def group_by(projects: list, key: str, label: str, order: list[str] | None = None) -> list[GroupAgg]:
    grouped: dict[str, list] = OrderedDict()
    for p in projects:
        grouped.setdefault(getattr(p, key), []).append(p)

    keys = order if order else sorted(grouped)
    out: list[GroupAgg] = []
    for k in keys:
        rows = grouped.get(k, [])
        agg = GroupAgg(
            key=k,
            label=k if k else "(unspecified)",
            count=len(rows),
            original_cost=_sum([p.original_cost for p in rows]),
            revised_cost=_sum([p.revised_cost for p in rows]),
            expenditure=_sum([p.cumulative_expenditure for p in rows]),
            avg_physical=_rounded(sum(p.physical_progress_pct for p in rows) / len(rows)) if rows else 0.0,
            mega_count=len([p for p in rows if p.is_mega]),
            mega_value=_sum([p.original_cost for p in rows if p.is_mega]),
            major_count=len([p for p in rows if not p.is_mega]),
            major_value=_sum([p.original_cost for p in rows if not p.is_mega]),
            buckets=build_buckets(rows),
            projects=sorted(rows, key=lambda p: (-p.original_cost, p.project_id)),
        )
        out.append(agg)
    return out


def by_category(report: InputReport) -> list[GroupAgg]:
    return group_by(report.ongoing, "category", "Category", report.categories)


def by_ministry(report: InputReport, top_n: int = 5) -> list[GroupAgg]:
    counts: Counter = Counter(p.ministry for p in report.ongoing)
    order = [m for m, _ in counts.most_common(top_n)]
    return group_by(report.ongoing, "ministry", "Ministry", order)


def ministry_sub_groups(report: InputReport, ministry: str) -> dict:
    rows = [p for p in report.ongoing if p.ministry == ministry]
    by_agency = group_by(rows, "agency", "Agency")
    by_sector = group_by(rows, "sector", "Sector")
    by_state = group_by(rows, "state", "State")
    return {
        "ministry": ministry,
        "projects": sorted(rows, key=lambda p: (-p.original_cost, p.project_id)),
        "count": len(rows),
        "original_cost": _sum([p.original_cost for p in rows]),
        "revised_cost": _sum([p.revised_cost for p in rows]),
        "expenditure": _sum([p.cumulative_expenditure for p in rows]),
        "agency_counts": [(g.label, g.count, g.original_cost) for g in by_agency],
        "sector_counts": [(g.label, g.count, g.original_cost) for g in by_sector],
        "state_counts": [(g.label, g.count, g.original_cost) for g in by_state],
    }


def _t1_t2_grouped(projects: list, level1: str, order: list[str] | None = None):
    """Build a list of {band, sector_list} for the rowspan-grouped T1/T2 tables."""
    l1 = OrderedDict()
    for p in projects:
        l1.setdefault(getattr(p, level1), []).append(p)
    keys = order if order else sorted(l1)
    bands = []
    for k in keys:
        rows = l1[k]
        by_sector = OrderedDict()
        for p in rows:
            by_sector.setdefault(p.sector, []).append(p)
        band = {
            "name": k,
            "count": len(rows),
            "original_cost": _sum([p.original_cost for p in rows]),
            "revised_cost": _sum([p.revised_cost for p in rows]),
            "expenditure": _sum([p.cumulative_expenditure for p in rows]),
            "sectors": [
                {
                    "name": s,
                    "count": len(srows),
                    "original_cost": _sum([p.original_cost for p in srows]),
                    "revised_cost": _sum([p.revised_cost for p in srows]),
                    "expenditure": _sum([p.cumulative_expenditure for p in srows]),
                    "avg_physical": _rounded(sum(p.physical_progress_pct for p in srows) / len(srows)),
                }
                for s, srows in by_sector.items()
            ],
        }
        bands.append(band)
    return bands


def project_bands(projects: list) -> list[dict]:
    """Ministry -> sector bands, each sector carrying its project rows (T3/T4)."""
    by_ministry: OrderedDict[str, list] = OrderedDict()
    for p in projects:
        by_ministry.setdefault(p.ministry, []).append(p)
    bands = []
    for m, rows in by_ministry.items():
        by_sector: OrderedDict[str, list] = OrderedDict()
        for p in rows:
            by_sector.setdefault(p.sector, []).append(p)
        sector_list = [
            {
                "name": s,
                "count": len(srows),
                "original_cost": _sum([p.original_cost for p in srows]),
                "revised_cost": _sum([p.revised_cost for p in srows]),
                "expenditure": _sum([p.cumulative_expenditure for p in srows]),
                "projects": sorted(srows, key=lambda p: (-p.original_cost, p.project_id)),
            }
            for s, srows in by_sector.items()
        ]
        bands.append(
            {
                "name": m,
                "count": len(rows),
                "original_cost": _sum([p.original_cost for p in rows]),
                "revised_cost": _sum([p.revised_cost for p in rows]),
                "expenditure": _sum([p.cumulative_expenditure for p in rows]),
                "sectors": sector_list,
            }
        )
    return bands


def ministry_bands(projects: list) -> list[dict]:
    """Ministry bands carrying direct project rows + per-band totals (T6)."""
    by_ministry: OrderedDict[str, list] = OrderedDict()
    for p in projects:
        by_ministry.setdefault(p.ministry, []).append(p)
    bands = []
    for m, rows in by_ministry.items():
        rows = sorted(rows, key=lambda p: (-p.original_cost, p.project_id))
        bands.append(
            {
                "name": m,
                "count": len(rows),
                "original_cost": _sum([p.original_cost for p in rows]),
                "revised_cost": _sum([p.revised_cost for p in rows]),
                "expenditure": _sum([p.cumulative_expenditure for p in rows]),
                "projects": rows,
            }
        )
    return bands


def reconcile(report: InputReport, overview: OverviewAgg) -> None:
    """Cross-check that every appendix total matches the KPI cards.

    Raises :class:`ReconciliationError` with a precise diff on any mismatch.
    """
    ongoing = report.ongoing
    problems: list[str] = []

    def check(what, got, want, tolerance: float = 0.51):
        if abs(got - want) > tolerance:
            problems.append(f"{what}: got {got:,.2f} but expected {want:,.2f} (Δ {got - want:,.2f})")

    counts = Counter(p.status for p in report.projects)
    # KPI cards
    check("Ongoing count", overview.ongoing_count, len(ongoing))
    check("Ongoing original cost", overview.original_cost, _sum([p.original_cost for p in ongoing]))
    check("Ongoing revised cost", overview.revised_cost, _sum([p.revised_cost for p in ongoing]))
    check("Ongoing expenditure", overview.expenditure, _sum([p.cumulative_expenditure for p in ongoing]))
    check("Completed count", overview.completed_count, counts["completed_this_month"])
    check("Newly added count", overview.newly_added_count, counts["newly_added_this_month"])

    # Appendix grand totals (T1 ministry-wise, T2 state-wise) must equal KPI totals.
    t1 = _t1_t2_grouped(ongoing, "ministry")
    t2 = _t1_t2_grouped(ongoing, "state")
    check("T1 grand total (original)", _sum([b["original_cost"] for b in t1]), overview.original_cost)
    check("T2 grand total (original)", _sum([b["original_cost"] for b in t2]), overview.original_cost)
    check("T1 grand total (revised)", _sum([b["revised_cost"] for b in t1]), overview.revised_cost)
    check("T2 grand total (expenditure)", _sum([b["expenditure"] for b in t2]), overview.expenditure)
    check("T1 sector subtotal sum", _sum([s["original_cost"] for b in t1 for s in b["sectors"]]), overview.original_cost)

    # Per-category totals must add up to the national total too.
    cat_orig = _sum([c.original_cost for c in by_category(report)])
    check("Category sum (original)", cat_orig, overview.original_cost)

    # Line ministries: count of ministries appearing in T1 bands.
    check("Line ministries", overview.line_ministries, len(t1))

    if problems:
        raise ReconciliationError("KPI/appendix totals do not reconcile:\n- " + "\n- ".join(problems))


def comparison(report: InputReport) -> dict | None:
    """Same-month-10-years-ago comparison from the optional previous payload."""
    prev = report.previous
    if prev is None:
        return None
    now = build_overview(report)
    old = build_overview(prev)
    return {
        "available": True,
        "old": {
            "projects": old.ongoing_count,
            "value": old.original_cost,
            "expenditure": old.expenditure,
        },
        "new": {
            "projects": now.ongoing_count,
            "value": now.original_cost,
            "expenditure": now.expenditure,
        },
        "deltas": {
            "projects": now.ongoing_count - old.ongoing_count,
            "value": now.original_cost - old.original_cost,
            "expenditure": now.expenditure - old.expenditure,
            "projects_pct": _pct((now.ongoing_count - old.ongoing_count) / old.ongoing_count * 100) if old.ongoing_count else "n/a",
            "value_pct": _pct((now.original_cost - old.original_cost) / old.original_cost * 100) if old.original_cost else "n/a",
            "expenditure_pct": _pct((now.expenditure - old.expenditure) / old.expenditure * 100) if old.expenditure else "n/a",
        },
        "note": f"Comparison with {prev.meta.month_label} edition",
    }