"""Rendering engine.

Pipeline
-------
1. load theme + validated input (with previous-edition comparison payload)
2. compute every aggregate (overview, NE, categories, ministries, appendix tables)
3. schedule + render all charts to inline SVG (parallel)
4. render the COVER as its own one-page PDF (never numbered / no header)
5. render the BODY twice (two-pass): pass 1 locates each section/table anchor
   on its real page, pass 2 writes the true contents page-ranges
6. merge cover + body with pypdf, preserving WeasyPrint's outline/bookmarks

Determinism: no wall-clock data in content, stable sorts everywhere, charts
drawn once and reused.
"""
from __future__ import annotations

import io
import logging
import os
import sys
import time
from pathlib import Path

from . import aggregates as agg
from . import charts
from . import loaders
from . import toc
from .formatters import intl as _intl, mm_yyyy as _mm

log = logging.getLogger("report_gen.render")

# WeasyPrint on Windows needs the GTK/Pango DLLs that ship inside the conda
# env's Library\bin.  Bootstrap the DLL search path before importing it.
_lib_bin = Path(sys.prefix) / "Library" / "bin"
if _lib_bin.is_dir():
    os.environ["PATH"] = str(_lib_bin) + os.pathsep + os.environ.get("PATH", "")

from weasyprint import HTML as WeasyHTML  # noqa: E402
from pypdf import PdfReader, PdfWriter  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class FlashReportError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Jinja environment
# ---------------------------------------------------------------------------


def _make_env(templates_dir: Path, theme: dict):
    from jinja2 import Environment, FileSystemLoader, StrictUndefined

    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        undefined=StrictUndefined,
        autoescape=False,
    )
    env.filters.update(
        inr=lambda v: _inr(v),
        intl=lambda v: _intl(v),
        pct=lambda v: _pct(v),
        signed=lambda v: _signed(v),
        lakh_crore=lambda v: _inr_compact(v, 100_000),
        thousand_crore=lambda v: _inr_compact(v, 1_000),
        mm_yyyy=lambda v: _mm(v),
        month_label=lambda v: _month_label(v),
        ordinal=lambda v: _ordinal(v),
        num=lambda v: f"{v:,.1f}".rstrip("0").rstrip("."),
        slug=lambda v: _slug(v),
    )
    env.globals["theme"] = theme
    return env


def _inr(v):
    from .formatters import inr

    return inr(float(v))


def _pct(v):
    from .formatters import pct

    return pct(float(v), force_sign=False)


def _signed(v):
    from .formatters import signed

    return signed(float(v))


def _inr_compact(v, divisor):
    return f"{float(v) / divisor:,.1f}"


def _month_label(v):
    from .formatters import month_label

    return month_label(v)


def _ordinal(v):
    from .formatters import ordinal

    return ordinal(v)


# ---------------------------------------------------------------------------
# Document helpers
# ---------------------------------------------------------------------------


def _css(theme: dict, env) -> str:
    tpl = env.get_template("report.css.j2")
    return tpl.render(theme=theme)


def _render_html(env, template: str, ctx: dict) -> str:
    return env.get_template(template).render(**ctx)


def _render_pdf(html: str, base_url: str) -> bytes:
    doc = WeasyHTML(string=html, base_url=base_url).render()
    return doc.write_pdf()


def _render_document(html: str, base_url: str):
    return WeasyHTML(string=html, base_url=base_url).render()


# ---------------------------------------------------------------------------
# Aggregate prep
# ---------------------------------------------------------------------------


def _build_context(report, assets, theme, edition_override, month_override) -> dict:
    meta = report.meta
    if edition_override is not None:
        meta.edition_no = edition_override
    if month_override:
        meta.month = month_override
        meta.month_label = _month_label(month_override)
        meta.report_title = f"{_month_label(month_override)} Flash Report"

    overview = agg.build_overview(report)
    agg.reconcile(report, overview)  # fails loudly if totals disagree

    ne_input = InputReportProxy(report, ne_filter=True)
    ne_overview = agg.build_overview(ne_input) if ne_input.projects else overview.__class__(
        ongoing_count=0, line_ministries=0, north_east_count=0,
        original_cost=0, revised_cost=0, expenditure=0, on_track=0,
        avg_physical=0, avg_financial=0, cost_effectiveness_pct=0,
        completed_count=0, completed_cost=0, newly_added_count=0,
        newly_added_cost=0, mega_count=0, mega_value=0, major_count=0,
        major_value=0, buckets=[], completed_list=[], newly_added_list=[],
    )
    ne_categories = (
        agg.group_by(ne_input.ongoing, "category", "Category", report.categories)
        if ne_input.projects else []
    )

    categories = agg.by_category(report)
    ministries = agg.by_ministry(report, theme["layout"]["top_ministries"])
    ministry_pages = [agg.ministry_sub_groups(report, m.label) for m in ministries]

    # Appendix data
    t1 = agg._t1_t2_grouped(report.ongoing, "ministry")
    t2 = agg._t1_t2_grouped(report.ongoing, "state")
    t3 = agg.project_bands(report.completed)
    t4 = agg.project_bands(report.newly_added)
    t5 = agg._t1_t2_grouped(report.north_east, "ministry")
    t6 = agg.ministry_bands(report.ongoing)

    comp = agg.comparison(report)

    return {
        "meta": meta,
        "assets": assets,
        "overview": overview,
        "ne": ne_overview,
        "ne_categories": ne_categories,
        "categories": categories,
        "ministry_pages": ministry_pages,
        "tables": {"t1": t1, "t2": t2, "t3": t3, "t4": t4, "t5": t5, "t6": t6},
        "comparison": comp,
    }


class InputReportProxy:
    """Small adapter so :func:`aggregates.build_overview` can run on a subset
    (e.g. North-East only) without mutating the validated report."""

    def __init__(self, report, ne_filter: bool = False):
        self.report = report
        self.ne_filter = ne_filter

    @property
    def projects(self):
        if self.ne_filter:
            return [p for p in self.report.projects if p.is_north_east]
        return self.report.projects

    @property
    def ongoing(self):
        return [p for p in self.projects if p.status == "ongoing"]

    @property
    def completed(self):
        return [p for p in self.projects if p.status == "completed_this_month"]

    @property
    def newly_added(self):
        return [p for p in self.projects if p.status == "newly_added_this_month"]

    @property
    def north_east(self):
        return [p for p in self.projects if p.is_north_east]

    @property
    def categories(self):
        return self.report.categories


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------


def _make_charts(report, ctx, theme) -> dict:
    charts.reset()
    cols = theme["colors"]

    def cc(items):  # category/count/cost lists
        return [list(t) for t in items]

    cats = [(c.label, c.count, c.original_cost) for c in ctx["categories"]]

    # ---- Overview
    charts.schedule("overview_donut", charts.nested_donut, cats, theme)
    charts.schedule(
        "overview_combo",
        charts.combo_columns,
        [c.label for c in ctx["categories"]],
        [c.original_cost for c in ctx["categories"]],
        [c.revised_cost for c in ctx["categories"]],
        [c.expenditure for c in ctx["categories"]],
        [c.count for c in ctx["categories"]],
        theme,
    )
    pipeline = _pipeline_stages(report, ctx["overview"])
    charts.schedule("overview_funnel", charts.funnel, pipeline, theme)
    charts.schedule("overview_progress", charts.progress_columns, ctx["overview"].buckets, theme)
    bucket_81 = [p for p in report.ongoing if p.physical_progress_pct >= 81]
    mb = agg.group_by(bucket_81, "ministry", "Ministry")
    charts.schedule(
        "overview_minstack",
        charts.ministry_stack,
        [(g.label, g.original_cost) for g in mb],
        theme,
    )
    charts.schedule(
        "overview_megamajor",
        charts.mega_major_hbars,
        {
            "mega_value": ctx["overview"].mega_value,
            "mega_count": ctx["overview"].mega_count,
            "major_value": ctx["overview"].major_value,
            "major_count": ctx["overview"].major_count,
            "label": "National",
        },
        {
            "mega_value": ctx["ne"].mega_value,
            "mega_count": ctx["ne"].mega_count,
            "major_value": ctx["ne"].major_value,
            "major_count": ctx["ne"].major_count,
            "label": "North East",
        },
        theme,
    )
    if ctx["comparison"]:
        charts.schedule("overview_compare", charts.comparison_chart, ctx["comparison"], theme)

    # ---- North-East
    ne_cats = [(c.label, c.count, c.original_cost) for c in ctx.get("ne_categories", [])]
    if ne_cats:
        charts.schedule("ne_donut", charts.nested_donut, ne_cats, theme)
        charts.schedule(
            "ne_combo",
            charts.combo_columns,
            [c[0] for c in ne_cats],
            [c[2] for c in ne_cats],
            [c[2] for c in ne_cats],
            [c[2] for c in ne_cats],
            [c[1] for c in ne_cats],
            theme,
        )
    charts.schedule("ne_progress", charts.progress_columns, ctx["ne"].buckets, theme)

    # ---- Categories
    for c in ctx["categories"]:
        sectors = agg.group_by(c.projects, "sector", "Sector")
        key = _slug(c.label)
        charts.schedule(
            f"cat_{key}_combo",
            charts.combo_columns,
            [s.label for s in sectors],
            [s.original_cost for s in sectors],
            [s.revised_cost for s in sectors],
            [s.expenditure for s in sectors],
            [s.count for s in sectors],
            theme,
        )
        charts.schedule(f"cat_{key}_progress", charts.progress_columns, c.buckets, theme)

    # ---- Ministries
    for mp in ctx["ministry_pages"]:
        key = _slug(mp["ministry"])
        agencies = agg.group_by(mp["projects"], "agency", "Agency")
        charts.schedule(
            f"min_{key}_donut",
            charts.nested_donut,
            [(a.label, a.count, a.original_cost) for a in agencies],
            theme,
        )
        sectors = agg.group_by(mp["projects"], "sector", "Sector")
        charts.schedule(
            f"min_{key}_sector_donut",
            charts.nested_donut,
            [(s.label, s.count, s.original_cost) for s in sectors],
            theme,
        )
        charts.schedule(
            f"min_{key}_combo",
            charts.combo_columns,
            [a.label for a in agencies],
            [a.original_cost for a in agencies],
            [a.revised_cost for a in agencies],
            [a.expenditure for a in agencies],
            [a.count for a in agencies],
            theme,
        )
        charts.schedule(
            f"min_{key}_bubble",
            charts.bubble,
            [(s.label, s.count, s.original_cost) for s in agg.group_by(mp["projects"], "state", "State")],
            theme,
        )

    return charts.render_all()


def _pipeline_stages(report, overview):
    """Funnel stages:  project count + original cost by cost band."""
    rows = report.ongoing
    bands = [
        ("≥ ₹1000 cr", [p for p in rows if p.original_cost >= 1000]),
        ("₹500–1000 cr", [p for p in rows if 500 <= p.original_cost < 1000]),
        ("₹250–500 cr", [p for p in rows if 250 <= p.original_cost < 500]),
        ("< ₹250 cr", [p for p in rows if p.original_cost < 250]),
    ]
    return [
        (name, len(rs), sum(p.original_cost for p in rs))
        for name, rs in bands
    ]


def _slug(text: str) -> str:
    import re

    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return s or "x"


# ---------------------------------------------------------------------------
# Sections + two pass + merge
# --------------------------------------------------------------------------


def _section_tree(ctx, meta_display: str) -> list[dict]:
    """The contents tree for the body document. Page ranges auto-filled in
    pass 1; the placeholder keeps the very first (pass 1) render valid."""

    def entry(numeral, title, anchor, end, children=None):
        return {
            "numeral": numeral,
            "title": title,
            "anchor": anchor,
            "end": end,
            "pages": "",
            "children": children or [],
        }

    return [
        entry("I", "Overview & Highlights", "sec-overview-start", "sec-overview-end"),
        entry("II", "Special Focus : North Eastern Region", "sec-ne-start", "sec-ne-end"),
        entry("III", "As per Harmonized Master List (HML) - Category Analysis",
              "sec-hml-start", "sec-hml-end"),
        entry("IV", "Major Infrastructure Central Ministries & Departments",
              "sec-ministries-start", "sec-ministries-end"),
        entry("V", "Appendix : List of Tables", "sec-appendix-start", "sec-appendix-end",
              children=[
                  entry(None, "T1. Ministry-wise Ongoing Projects", "sec-t1-start", "sec-t1-end"),
                  entry(None, "T2. State-wise Ongoing Projects", "sec-t2-start", "sec-t2-end"),
                  entry(None, "T3. Projects Completed during the Month", "sec-t3-start", "sec-t3-end"),
                  entry(None, "T4. Newly Added Projects", "sec-t4-start", "sec-t4-end"),
                  entry(None, "T5. Ongoing Projects - North Eastern Region", "sec-t5-start", "sec-t5-end"),
                  entry(None, "T6. All Ongoing Projects", "sec-t6-start", "sec-t6-end"),
              ]),
    ]


def build_report(
    input_path: Path,
    out_path: Path,
    theme_path: Path | None = None,
    edition: int | None = None,
    month: str | None = None,
    project_root: Path | None = None,
) -> Path:
    """Build the full PDF report. Returns the output path."""
    t_start = time.perf_counter()
    for noisy in ("weasyprint", "weasyprint.progress", "fontTools", "fontTools.subset"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    theme_path = Path(theme_path or PROJECT_ROOT / "config" / "theme.yaml")
    templates_dir = PROJECT_ROOT / "templates"

    theme = loaders.load_theme(theme_path)
    charts._configure(theme["fonts"]["heading_stack"] + theme["fonts"]["body_stack"])

    report, assets = loaders.load_input(input_path, project_root)
    log.info("Loaded %d projects from %s", len(report.projects), input_path)

    ctx = _build_context(report, assets, theme, edition, month)
    env = _make_env(templates_dir, theme)
    css = _css(theme, env)
    ctx["css"] = css

    charts_map = _make_charts(report, ctx, theme)
    ctx["charts"] = charts_map
    ctx["tree"] = _section_tree(ctx, ctx["meta"].month_label)

    base_url = str(PROJECT_ROOT / "static")

    # ---- Pass 1: page map -------------------------------------------------
    body_html_1 = _render_html(env, "body.j2", ctx)
    doc1 = _render_document(body_html_1, base_url)
    anchor_ids = {e["anchor"] for e in _flatten(ctx["tree"])}
    anchor_ids |= {e["end"] for e in _flatten(ctx["tree"]) if e.get("end")}
    page_map = toc.extract_page_map(doc1, anchor_ids)
    toc.resolve(ctx["tree"], page_map)
    log.info("Pass 1 complete: %d anchors resolved across %d pages",
             len(page_map), len(doc1.pages))

    # ---- Pass 2: final body ------------------------------------------------
    body_html_2 = _render_html(env, "body.j2", ctx)
    body_pdf = _render_pdf(body_html_2, base_url)

    cover_html = _render_html(env, "cover.j2", ctx)
    cover_pdf = _render_pdf(cover_html, base_url)

    merged = _merge_pdfs(cover_pdf, body_pdf, ctx)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(merged)

    elapsed = time.perf_counter() - t_start
    n_pages = len(PdfReader(io.BytesIO(merged)).pages)
    size_mb = len(merged) / (1024 * 1024)
    log.info(
        "Wrote %s | %d pages | %.2f MB | built in %.1fs",
        out_path, n_pages, size_mb, elapsed,
    )
    if size_mb > 8:
        log.warning("Report size %.2f MB exceeds the 8 MB target; check raster assets.", size_mb)
    else:
        log.info("Size target OK (≤ 8 MB).")
    return out_path


def _flatten(tree: list[dict]):
    for e in tree:
        yield e
        yield from _flatten(e.get("children", []))


def _merge_pdfs(cover_pdf: bytes, body_pdf: bytes, ctx) -> bytes:
    """Concatenate the unnumbered cover with the numbered body.

    The body document is rendered independently so its ``counter(page)``
    naturally starts at 1 on the Contents page (cover stays unnumbered).
    WeasyPrint's CSS ``bookmark-*`` outline is preserved by ``append``.
    """
    meta = ctx["meta"]
    buf = io.BytesIO()
    writer = PdfWriter(buf)
    writer.append(PdfReader(io.BytesIO(cover_pdf)))
    writer.append(PdfReader(io.BytesIO(body_pdf)))
    writer.add_metadata({
        "/Title": meta.report_title or f"{meta.month_label} Flash Report",
        "/Author": meta.ministry_name,
        "/Subject": f"{meta.edition_no}th Flash Report on Central Sector Infrastructure Projects",
        "/Keywords": f"flash report, infra, {meta.month_label}, edition {meta.edition_no}",
        "/Creator": "MoSPI Flash Report Generator",
    })
    writer.write(buf)
    return buf.getvalue()