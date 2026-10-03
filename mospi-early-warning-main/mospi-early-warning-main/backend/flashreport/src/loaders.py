"""Input loading + validation.

Accepts a single JSON document (fastest, full fidelity) or a CSV of projects
plus an optional adjacent ``meta.json`` (CSV cannot carry the meta block, so it
is inferred with sensible defaults).  Any missing file, unknown project column
or invalid status fails loudly with an actionable message.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import Assets, InputReport, Meta, Project

PROJECT_FIELDS = set(Project.model_fields)
META_FIELDS = set(Meta.model_fields)

_ASSET_ROLES = ("emblem", "org_logo", "cover_art", "skyline_art", "qr_image")


class InputLoadError(Exception):
    """Raised when the input data or assets cannot be resolved."""


def _resolve_asset_path(project_root: Path, current_dir: Path, raw: str) -> str:
    """Return a filesystem-stable path for an asset; '' when not provided."""
    if not raw:
        return ""
    p = Path(raw)
    if not p.is_absolute():
        # resolve against current input location first, then project root
        for base in (current_dir, project_root):
            cand = base / raw
            if cand.exists():
                return str(cand)
        return str(project_root / raw)  # still reported missing later, loudly
    return str(p)


def _validate_assets(meta: Meta, current_dir: Path, project_root: Path) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for role in _ASSET_ROLES:
        raw = getattr(meta.assets, role)
        path = _resolve_asset_path(project_root, current_dir, raw)
        if path:
            p = Path(path)
            if not p.exists():
                raise InputLoadError(
                    f"Asset '{role}' declared in meta as {raw!r} but not found at "
                    f"{path!r}. Fix the path in the data file or supply the file."
                )
            # WeasyPrint needs a real absolute URI for Windows paths.
            resolved[role] = p.resolve().as_uri()
        else:
            resolved[role] = ""
    return resolved


def load_input(path: str | Path, project_root: Path | None = None) -> tuple[InputReport, dict[str, str]]:
    """Load + validate the input document. Returns (report, resolved_asset_paths)."""
    path = Path(path).expanduser()
    if not path.exists():
        raise InputLoadError(f"Input file not found: {path}")

    project_root = Path(project_root or path.parent.parent).resolve()

    if path.suffix.lower() == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or "projects" not in raw:
            raise InputLoadError(
                f"{path} must be an object with a 'projects' list (and optional 'meta')."
            )
        meta_raw = raw.get("meta", {})
        meta_raw.setdefault("month", "")  # fill below if missing
        if not meta_raw.get("month"):
            for p in raw["projects"]:
                if p.get("start_date"):
                    meta_raw["month"] = p["start_date"][:7]
                    break
        meta_raw.setdefault("report_title", f"{meta_raw.get('month', '')} Flash Report")

        meta = Meta.model_validate(meta_raw)
        projects = [Project.model_validate(p) for p in raw["projects"]]

        previous: InputReport | None = None
        prev_ref = raw.get("previous") or raw.get("previous_edition")
        if isinstance(prev_ref, str) and prev_ref:
            prev_path = _resolve_asset_path(project_root, path.parent, prev_ref)
            if not Path(prev_path).exists():
                raise InputLoadError(
                    f"previous_edition declared as {prev_ref!r} but not found at {prev_path!r}."
                )
            previous, _ = load_input(prev_path, project_root)
        elif isinstance(prev_ref, dict):
            # embedded previous payload - guard against recursive blow-ups
            prev_input = {"meta": prev_ref.get("meta", meta_raw), "projects": prev_ref.get("projects", [])}
            previous = InputReport.model_validate(prev_input)

        report = InputReport(meta=meta, projects=projects, previous=previous)
        assets = _validate_assets(meta, path.parent, project_root)
        return report, assets

    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
        if not rows:
            raise InputLoadError(f"CSV {path} contains no rows.")
        cols = set(rows[0].keys())
        missing = PROJECT_FIELDS - cols
        if missing:
            raise InputLoadError(
                f"CSV {path} is missing required columns: {sorted(missing)}"
            )
        projects = [Project.model_validate(r) for r in rows]

        meta_file = Path(str(path) + ".meta.json")
        if meta_file.exists():
            meta_raw = json.loads(meta_file.read_text(encoding="utf-8"))
        else:
            meta_file = path.parent / "meta.json"
            meta_raw = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}
        meta_raw = dict(meta_raw)
        meta_raw.setdefault("edition_no", 1)
        month = meta_raw.get("month", "")
        if not month:
            month = projects[0].start_date[:7] if projects[0].start_date else "2026-01"
            meta_raw["month"] = month
        meta_raw.setdefault("month_label", month.upper().replace("-", " "))
        meta_raw.setdefault("report_title", f"{month} Flash Report")
        meta = Meta.model_validate(meta_raw)
        report = InputReport(meta=meta, projects=projects)
        assets = _validate_assets(meta, path.parent, project_root)
        return report, assets

    raise InputLoadError(f"Unsupported input format: {path.suffix} (use .json or .csv)")


def load_theme(path: str | Path) -> dict:
    """Load theme.yaml into a plain dict (dict-of-dicts for template access)."""
    import yaml

    theme = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(theme, dict):
        raise InputLoadError(f"Theme file {path} must contain a YAML mapping.")
    return theme