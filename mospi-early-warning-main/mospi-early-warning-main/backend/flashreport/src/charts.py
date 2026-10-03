"""Chart generation:  every figure is authored with matplotlib's figure API
(not pyplot) and exported once to an inline SVG string.  Charts are drawn in
parallel where possible via :func:`render_all`.

Colour sources come exclusively from ``theme['colors']``; number labels use the
:mod:`formatters` helpers so axis text matches the report's number system.
"""
from __future__ import annotations

import io
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import matplotlib

matplotlib.use("Agg")
from matplotlib.figure import Figure  # noqa: E402

from .formatters import intl, thousand_crore  # noqa: E402

log = logging.getLogger("report_gen.charts")


def _configure(font_list: list[str]) -> None:
    from matplotlib import font_manager

    installed = {f.name for f in font_manager.fontManager.ttflist}
    chosen = [f for f in font_list if f in installed]
    rc = matplotlib.rcParams
    rc["font.family"] = (chosen or ["DejaVu Sans"]) + ["DejaVu Sans"]
    rc["svg.fonttype"] = "path"
    rc["font.size"] = 9
    rc["axes.linewidth"] = 0.75
    rc["savefig.facecolor"] = "none"  # allow CSS background to show through
    rc["savefig.transparent"] = True


def _new_figure(width_in: float, height_in: float) -> Figure:
    fig = Figure(figsize=(width_in, height_in), dpi=100)
    return fig


def _svg(fig: Figure) -> str:
    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight", pad_inches=0.02)
    svg = buf.getvalue()
    # Strip the XML declaration line so the SVG inlines cleanly in HTML.
    if svg.startswith("<?xml"):
        svg = svg.split("?>", 1)[1].lstrip()
    return svg


def _style_axes(ax, navy: str, note_grey: str, size: int = 8.5) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#C9CBD1")
    ax.tick_params(colors=note_grey, labelsize=size - 0.5)
    ax.yaxis.get_offset_text().set_color("#8A8A8E")
    ax.title.set_color(navy)
    ax.grid(axis="y", color="#E5E6EA", linewidth=0.6, alpha=0.7)


def _autopct_labels(values: list[float]) -> list[str]:
    total = sum(values)
    return [f"{v / total * 100:.1f}%" if total else "0%" for v in values]


# ---------------------------------------------------------------------------
# 1. Nested donut - outer ring: original cost, inner ring: project count
# ---------------------------------------------------------------------------


def nested_donut(items: list[tuple[str, int, float]], theme: dict) -> str:
    """items: (label, count, cost_crore)."""
    cols = theme["colors"]
    navy = cols["navy"]
    grey = cols["note_grey"]
    series = [cols["chart_dark_teal"], cols["chart_gold"], cols["chart_light_teal"],
              cols["chart_red"], "#7A5FA8", "#4C86C6", "#9BB19C", "#D16363"]
    fig = _new_figure(6.8, 3.4)
    ax = fig.add_subplot(111)
    labels = [it[0] for it in items]
    counts = [it[1] for it in items]
    costs = [it[2] for it in items]
    if len(items) > len(series):
        series = (series * (len(items) // len(series) + 1))[: len(items)]

    wedge_outer, _ = ax.pie(
        costs, radius=1.0, colors=series, startangle=90, counterclock=False,
        wedgeprops=dict(width=0.30, edgecolor="white", linewidth=1.5),
    )
    wedge_inner, _ = ax.pie(
        counts, radius=0.65, colors=series, startangle=90, counterclock=False,
        wedgeprops=dict(width=0.28, edgecolor="white", linewidth=1.2, alpha=0.85),
    )
    _ = wedge_outer, wedge_inner
    ax.text(0, 0, "₹ crore", ha="center", va="center", fontsize=8, color=grey,
            fontstyle="italic")

    # Legend swatches at the side
    ax.legend(
        handles=[matplotlib.patches.Patch(facecolor=c, label=l) for l, c in zip(labels, series)],
        loc="center left", bbox_to_anchor=(-0.42, 0.5), frameon=False, fontsize=7,
        handlelength=1.0, handleheight=1.0,
    )
    ax.set_title("Sector Share - Original Cost (outer) & Project Count (inner)",
                 fontsize=9.5, pad=10)
    _style_axes(ax, navy, grey)
    ax.set_axis_off()
    return _svg(fig)


# ---------------------------------------------------------------------------
# 2. Combo chart - clustered columns + secondary-line project count
# ---------------------------------------------------------------------------


def combo_columns(groups: list[str], original: list[float], revised: list[float],
                  expenditure: list[float], counts: list[int], theme: dict,
                  unit="₹ crore") -> str:
    cols = theme["colors"]
    grey = cols["note_grey"]
    import numpy as np

    fig = _new_figure(6.8, 3.5)
    ax = fig.add_subplot(111)
    x = np.arange(len(groups))
    w = 0.25
    ax.bar(x - w, original, w, label="Original", color=cols["chart_dark_teal"])
    ax.bar(x, revised, w, label="Revised", color=cols["chart_light_teal"])
    ax.bar(x + w, expenditure, w, label="Expenditure", color=cols["chart_gold"])
    ax2 = ax.twinx()
    ax2.plot(x, counts, color=cols["chart_red"], marker="o", linewidth=1.6,
             label="Project count")
    ax2.set_ylim(0, max(counts) * 1.25 if counts else 1)
    ax.axhline(0, color="#8A8A8E", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(groups, rotation=0, fontsize=7.5)
    ax.set_ylabel(unit, fontsize=8)
    ax2.set_ylabel("Count", fontsize=8)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v/1000:.0f}k" if abs(v) >= 1000 else f"{v:,.0f}")
    ax2.yaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.34), ncol=4, frameon=False, fontsize=7.5)
    ax2.legend(loc="center right", frameon=False, fontsize=7)
    _style_axes(ax, cols["navy"], grey)
    _style_axes(ax2, cols["navy"], grey)
    ax2.spines[["left", "bottom"]].set_visible(False)
    return _svg(fig)


# ---------------------------------------------------------------------------
# 3. Funnel chart with leader-line labels "(count, ₹ cost)"
# ---------------------------------------------------------------------------


def funnel(stages: list[tuple[str, int, float]], theme: dict) -> str:
    cols = theme["colors"]
    grey = cols["note_grey"]
    counts = [s[1] for s in stages]
    labels = [f"{s[1]} / {intl(s[2])}" for s in stages]  # "(count, ₹ cost)"
    names = [s[0] for s in stages]
    fig = _new_figure(6.8, 3.3)
    ax = fig.add_subplot(111)
    width_scale = max(counts) or 1
    vals = [c / width_scale for c in counts]
    for i, (nm, v, ls, lbl) in enumerate(zip(names, vals, [cols["chart_dark_teal"], cols["chart_light_teal"], cols["chart_gold"], cols["chart_red"]], labels)):
        ax.barh(i, v, left=(1 - v) / 2, height=0.72, color=ls, align="center",
                edgecolor="white")
        ax.text(0.5, i, f"{nm}  ({lbl})", ha="center", va="center", fontsize=8,
                color="white", fontweight="bold")
    ax.invert_yaxis()
    ax.set_yticks([])
    ax.set_xticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    _ = fig  # placeholder label style
    ax.set_title("Project Pipeline by Stage", fontsize=9.5, color=cols["navy"])
    return _svg(fig)


# ---------------------------------------------------------------------------
# 4. Clustered physical vs financial progress columns
# ---------------------------------------------------------------------------


def progress_columns(buckets: list, theme: dict) -> str:
    cols = theme["colors"]
    grey = cols["note_grey"]
    import numpy as np

    fig = _new_figure(6.8, 3.3)
    ax = fig.add_subplot(111)
    names = [b.name for b in buckets]
    phys = [b.count for b in buckets]
    x = np.arange(len(names))
    w = 0.38
    b1 = ax.bar(x - w / 2, phys, w, label="Project count", color=cols["chart_dark_teal"])
    for rect, v in zip(b1, phys):
        ax.text(rect.get_x() + rect.get_width() / 2, rect.get_height() + 1.2,
                f"{v}", ha="center", va="bottom", fontsize=7.5,
                color=cols["navy"], fontweight="bold")
    ax2 = ax.twinx()
    b2 = ax2.bar(x + w / 2, [b.avg_physical for b in buckets], w * 0.8,
                 label="Avg physical", color=cols["chart_gold"], alpha=0.85)
    for rect, b in zip(b2, buckets):
        ax2.text(rect.get_x() + rect.get_width() / 2, rect.get_height() + 0.8,
                 f"{b.avg_financial:.0f}", ha="center", va="bottom", fontsize=6.5,
                 color=cols["chart_red"])
    ax.set_xticks(x)
    ax.set_xticklabels([f"{b.name}%" for b in buckets], fontsize=8)
    ax.set_ylabel("Projects", fontsize=8)
    ax2.set_ylabel("Avg progress %", fontsize=8)
    ax.set_ylim(0, max(phys) * 1.2 if phys else 1)
    ax2.set_ylim(0, 100)
    ax.legend(loc="upper center", bbox_to_anchor=(0.32, -0.18), ncol=2, frameon=False, fontsize=7)
    ax2.legend(loc="upper center", bbox_to_anchor=(0.72, -0.18), frameon=False, fontsize=7)
    _style_axes(ax, cols["navy"], grey)
    _style_axes(ax2, cols["navy"], grey)
    ax2.spines[["left", "bottom"]].set_visible(False)
    return _svg(fig)


# ---------------------------------------------------------------------------
# 5. Bubble chart - state on x, cost on y, size = project count
# ---------------------------------------------------------------------------


def bubble(states: list[tuple[str, int, float]], theme: dict) -> str:
    cols = theme["colors"]
    grey = cols["note_grey"]
    import numpy as np

    fig = _new_figure(6.8, 3.6)
    ax = fig.add_subplot(111)
    states = sorted(states, key=lambda s: -s[2])[:18]
    names = [s[0] for s in states]
    counts = np.array([s[1] for s in states])
    costs = [s[2] for s in states]
    x = np.arange(len(names))
    sizes = 80 + (counts / max(counts)) * 380
    ax.scatter(x, costs, s=sizes, color=cols["chart_dark_teal"], alpha=0.8,
               edgecolor="white", linewidth=1.2)
    for xi, nm, c, cost in zip(x, names, counts, costs):
        short = nm.split()[-1] if len(nm) <= 18 else nm[:16] + "…"
        ax.text(xi, cost * 1.02, f"{short} ({c}, ₹{thousand_crore(cost)})",
                ha="center", va="bottom", fontsize=6.2, color=grey, rotation=35)
    ax.set_xticks(x)
    ax.set_xticklabels(["" for _ in names], fontsize=6)
    ax.set_ylabel("₹ thousand crore", fontsize=8)
    ax.set_ylim(0, max(costs) * 1.35 if costs else 1)
    ax.set_title("State-wise Presence (size = projects)", fontsize=9.5, color=cols["navy"])
    _style_axes(ax, cols["navy"], grey)
    return _svg(fig)


# ---------------------------------------------------------------------------
# 6. Single stacked column - ministry distribution in the 81-100% bucket
# ---------------------------------------------------------------------------


def ministry_stack(items: list[tuple[str, float]], theme: dict) -> str:
    cols = theme["colors"]
    fig = _new_figure(6.8, 2.6)
    ax = fig.add_subplot(111)
    total = sum(v for _, v in items)
    series = [cols["chart_dark_teal"], cols["chart_light_teal"], cols["chart_gold"],
              cols["chart_red"], "#7A5FA8", "#4C86C6", "#9BB19C", "#D16363"]
    items = [it for it in items if it[1] > 0]
    left = 0.0
    for i, (nm, v) in enumerate(items):
        col = series[i % len(series)]
        ax.bar(0, v, bottom=left if i else None, color=col, width=0.6, edgecolor="white",
               label=f"{nm} - {v:.1f}")
        share = v / total * 100 if total else 0
        ax.text(0, left + v / 2, f"{nm} {share:.1f}%", rotation=90, ha="center",
                va="center", fontsize=7, color="white", fontweight="bold")
        left += v
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("Ministry Distribution in 81-100% Progress Bucket",
                 fontsize=9.5, color=cols["navy"])
    return _svg(fig)


# ---------------------------------------------------------------------------
# 7. Two stacked horizontal bars - Mega vs Major (national / north-east)
# ---------------------------------------------------------------------------


def mega_major_hbars(national: dict, north_east: dict, theme: dict) -> str:
    cols = theme["colors"]
    grey = cols["note_grey"]
    import numpy as np

    fig = _new_figure(6.8, 2.6)
    ax = fig.add_subplot(111)
    rows = [national, north_east]
    y = np.arange(2)
    mega = [r["mega_value"] for r in rows]
    major = [r["major_value"] for r in rows]
    ax.barh(y + 0.19, mega, height=0.32, color=cols["chart_dark_teal"], label="Mega")
    ax.barh(y - 0.19, major, height=0.32, color=cols["chart_gold"], label="Major")
    for yy, r in zip(y, rows):
        ax.text(r["mega_value"], yy + 0.19, f" {r['mega_count']}", va="center", fontsize=7.5, color=cols["navy"])
        ax.text(r["major_value"], yy - 0.19, f" {r['major_count']}", va="center", fontsize=7.5, color=cols["navy"])
    ax.set_yticks(y)
    ax.set_yticklabels(["National", north_east.get("label", "North East")], fontsize=8)
    ax.set_xlabel("₹ crore", fontsize=8)
    ax.legend(loc="lower right", frameon=False, fontsize=7.5)
    _style_axes(ax, cols["navy"], grey)
    return _svg(fig)


# ---------------------------------------------------------------------------
# 8. Three-bar comparison - same month, 10 years ago vs now
# ---------------------------------------------------------------------------


def comparison_chart(comp: dict, theme: dict) -> str:
    cols = theme["colors"]
    grey = cols["note_grey"]
    import numpy as np

    fig = _new_figure(6.8, 3.2)
    ax = fig.add_subplot(111)
    labels = ["Project volume", "Total value\n(₹ crore)", "Cum. expenditure\n(₹ crore)"]
    old = [comp["old"]["projects"], comp["old"]["value"], comp["old"]["expenditure"]]
    new = [comp["new"]["projects"], comp["new"]["value"], comp["new"]["expenditure"]]
    x = np.arange(3)
    w = 0.32
    ax.bar(x - w / 2, old, w, label="10 years ago", color=cols["card_bg"],
           edgecolor=cols["chart_dark_teal"], linewidth=1)
    ax.bar(x + w / 2, new, w, label="This month", color=cols["chart_dark_teal"])
    for xi, o, n in zip(x, old, new):
        ax.text(xi - w / 2, o * 1.05, f"{o:,.0f}", ha="center", fontsize=7, color=grey)
        ax.text(xi + w / 2, n * 1.05, f"{n:,.0f}", ha="center", fontsize=7, color=cols["navy"])
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7.5)
    ax.set_yticks([])
    ax.legend(loc="upper left", frameon=False, fontsize=7.5)
    _style_axes(ax, cols["navy"], grey)
    return _svg(fig)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

_JOBS: list = []


def reset() -> None:
    """Clear the shared job queue (used between test runs)."""
    _JOBS.clear()


def schedule(name: str, fn, *args, **kwargs) -> None:
    _JOBS.append((name, fn, args, kwargs))


def render_all(n_workers: int = 4) -> dict[str, str]:
    """Render every scheduled chart to an inline SVG, in parallel."""
    out: dict[str, str] = {}
    jobs = list(_JOBS)
    _JOBS.clear()
    if len(jobs) > 2:
        with ThreadPoolExecutor(max_workers=n_workers) as pool:
            futures = {pool.submit(fn, *args, **kwargs): name for name, fn, args, kwargs in jobs}
            for fut in as_completed(futures):
                name = futures[fut]
                out[name] = fut.result()
    else:
        for name, fn, args, kwargs in jobs:
            out[name] = fn(*args, **kwargs)
    return out