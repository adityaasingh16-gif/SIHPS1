"""Two-pass page resolution for the Contents page.

Pass 1 renders the body, then every section/table anchor id is located on its
physical page by walking WeasyPrint's box tree.  Pass 2 re-renders with the
true page ranges filled in.  Nothing on the Contents page is hard-coded.
"""
from __future__ import annotations

import logging

log = logging.getLogger("report_gen.toc")


def _iter_boxes(box):
    yield box
    for child in getattr(box, "children", []):
        yield from _iter_boxes(child)


def extract_page_map(document, anchor_ids: set[str]) -> dict[str, int]:
    """Map each anchor id -> the physical page it appears on (1-based).

    Only the first occurrence is recorded; every anchor must exist or an error
    is raised so a changed template can't silently break the Contents.
    """
    found: dict[str, int] = {}
    for page_no, page in enumerate(document.pages, start=1):
        root = getattr(page, "_page_box", None)
        if root is None:
            continue
        for box in _iter_boxes(root):
            el = getattr(box, "element", None)
            if el is None:
                continue
            eid = el.get("id")
            if eid and eid in anchor_ids and eid not in found:
                found[eid] = page_no
                if len(found) == len(anchor_ids):
                    return found
    missing = anchor_ids - set(found)
    if missing:
        raise RuntimeError(
            f"TOC anchors not found in rendered document: {sorted(missing)}. "
            "Check that every section template carries its start/end anchors."
        )
    return found


def resolve(tree: list[dict], page_map: dict[str, int]) -> None:
    """Populate ``range``/``pages`` on every tree entry (recursively), in place.

    ``tree`` entries are ``{anchor, end, ...}``; the range is ``start_page[-end_page]``
    (single page has no dash suffix).
    """

    def fill(entry: dict) -> None:
        start = page_map[entry["anchor"]]
        end_anchor = entry.get("end")
        end = page_map.get(end_anchor) if end_anchor else None
        if end is None or end == start:
            entry["range"] = str(start)
        else:
            entry["range"] = f"{start}-{end}"
        entry["pages"] = entry["range"]
        for child in entry.get("children", []):
            fill(child)

    for entry in tree:
        fill(entry)


def build_bookmarks(tree: list[dict]) -> list[dict]:
    """Flatten the contents tree into the PDF outline for WeasyPrint metadata.

    CSS ``bookmark-level`` already drives the visible outline when rendering,
    so this mirrors it into ``.pdf_metadata`` for readers that ignore embedded
    outline links.  Returns the ordered (label, level) list.
    """
    out: list[tuple[str, int]] = []

    def walk(entries, level):
        for e in entries:
            out.append((e["title"], level))
            walk(e.get("children", []), level + 1)

    walk(tree, 1)
    return out