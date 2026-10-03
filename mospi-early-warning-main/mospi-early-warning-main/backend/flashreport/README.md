# MoSPI Flash Report Generator

Generates the monthly **Flash Report** PDF (cover, auto-paginated Contents,
section dividers, KPI dashboards with inline SVG charts, and six appendix
tables) from a single validated data payload.

## Setup

Work is done on Windows. WeasyPrint needs its GTK/Pango runtime to import.

1. Create a conda environment (Python 3.12+):

   ```bat
   conda create -n reportgen python=3.12 -y
   conda activate reportgen
   ```

2. Install dependencies:

   ```bat
   pip install -r requirements.txt
   ```

3. Verify WeasyPrint imports. Its DLLs live next to the Python runtime and are
   added to `PATH` automatically by `src/render.py` before import:

   ```bat
   python -c "import weasyprint; print(weasyprint.__version__)"
   ```

## Usage

```bat
python -m src.cli ^
  --input data\sample_2026_07.json ^
  --edition 489 ^
  --month 2026-07 ^
  --out out\FlashReport_July_2026.pdf
```

Arguments:

- `--input`: validated report payload (JSON, pydantic-validated).
- `--edition` / `--month`: override the edition number and ISO month on the
  cover, the Contents header and the running footer.
- `--out`: output PDF path (default `FlashReport_<Month>_<Year>.pdf`).
- `--config-dir`: root of `config/theme.yaml` and `templates/` if run from a
  different directory.

The same build is available as a package entrypoint:

```bat
python -m report_gen --input data\sample_2026_07.json --edition 489 --month 2026-07
```

## Data contract

The payload must match `src/models.py::InputReport`:

- `meta`: edition, month label, cutoff note, portal URL, asset paths.
- `projects`: list of `Project` rows with `status` in
  `ongoing | completed_this_month | newly_added_this_month`. Dates are
  `MM/YYYY` (or `YYYY-MM`; normalised by the formatters). Cost fields may be
  strings with thousand separators; numeric coercion handles `-`, `nil`, `N/A`.
- `previous` (optional): same-shaped payload for the same month 10 years ago,
  enabling the comparison panel.

Assets (`emblem`, `org_logo`, `cover_art`, `skyline_art`, `qr_image`) are
resolved to `file://` URIs relative to the input file. Every asset referenced
must exist; missing files raise `InputLoadError`.

## What gets reconciled

`src/aggregates.py::reconcile` cross-checks before rendering:

- KPI ongoing/completed/newly-added counts and costs against the raw payload.
- Appendix T1 (ministry-wise) and T2 (state-wise) grand totals against the
  KPI cards.
- Per-category cost sum against the national total, and line-ministry count
  against the T1 band list.

Any disagreement raises `ReconciliationError` and the build stops - a bad
dataset can never silently produce an edition.

## Two-pass page numbering

`src/toc.py` renders the body once, walks WeasyPrint's box tree to locate
every section/table anchor, then renders again with the real page ranges in
the Contents and the PDF outline (from CSS bookmarks). The cover is rendered
as a separate document and merged with pypdf (`src/render.py::_merge_pdfs`).

## Project layout

```
config/theme.yaml        colors, fonts, spacing, layout limits
templates/*.j2           cover, body, dividers, dashboards, tables, CSS
src/                     models, loaders, formatters, aggregates,
                         charts, toc, render, cli
tests/                   unit tests (run: python -m pytest tests)
data/                    deterministic 60-project sample edition
static/img/              placeholder image assets
```

## Tests

```bat
python -m pytest tests -q
```

The suite covers Indian vs international number formatting, aggregation and
reconciliation, bucket edges, TOC range resolution, chart SVG generation, and
payload loading (the committed sample must load, reconcile, and report 58
ongoing projects).

## Notes

- Mega projects are defined as `original_cost >= ₹1000 crore` (threshold in
  `src/models.py::Project.is_mega`).
- KPI cards use Indian digit grouping (`₹ 33,70,138`); tables use
  international grouping with two decimals (`3,370,138.22`).
- The report is generated in two WeasyPrint passes; total runtime for a 60-row
  sample is ~26 seconds.