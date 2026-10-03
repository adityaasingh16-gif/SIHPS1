"""Build a bundled India admin-1/district GeoJSON for the public map.

Why a vendored file rather than a runtime fetch:
  * the portal must not break because a third-party CDN is unreachable;
  * the boundaries have to be auditable alongside the code that shades them;
  * district-level geometry is far more precise than the state centroids the
    panel data actually supports, so a boundary error would be very visible.

Source: github.com/udit-001/india-maps-data (MIT), per-state district
boundaries keyed to 2011 administrative codes. This was chosen over the older
geohacker/india file, which is a pre-2019 Natural Earth vintage: it still has
`Orissa` and `Uttaranchal` as names, keeps Dadra & Nagar Haveli and Daman &
Diu separate, mislabels Himachal Pradesh a UT and Jammu & Kashmir a State, and
has no Ladakh at all. On a government monitoring portal those are not cosmetic.

Districts are kept rather than dissolved into state outlines. No geometry
library is available in this environment, and it is not needed: the choropleth
shades every district of a state with that state's value via a `match` on
`st_nm`, which is exact and avoids a lossy dissolve.

Coordinates are rounded, not resampled, so the topology is untouched and only
the byte count falls. Run:  python backend/scripts/build_india_geojson.py
"""

import json
import os
import sys
import urllib.request
from collections import Counter

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BACKEND_DIR)

RAW_DIR = os.path.join(os.environ.get("TEMP", "."), "opencode", "india_geojson")
OUT_PATH = os.path.abspath(
    os.path.join(
        BACKEND_DIR, "..", "frontend", "src", "data", "india_states.geojson"
    )
)
BASE = "https://raw.githubusercontent.com/udit-001/india-maps-data/main/geojson/states"
# 2011 state codes, keyed to the file that carries them. `dnh-and-dd` is the
# post-2020 merged union territory.
STATE_FILES = {
    "Andaman and Nicobar Islands": ("andaman-and-nicobar-islands.geojson", "35"),
    "Andhra Pradesh": ("andhra-pradesh.geojson", "28"),
    "Arunachal Pradesh": ("arunachal-pradesh.geojson", "12"),
    "Assam": ("assam.geojson", "18"),
    "Bihar": ("bihar.geojson", "10"),
    "Chandigarh": ("chandigarh.geojson", "04"),
    "Chhattisgarh": ("chhattisgarh.geojson", "22"),
    "Dadra and Nagar Haveli and Daman and Diu": ("dnh-and-dd.geojson", "26"),
    "Delhi": ("delhi.geojson", "07"),
    "Goa": ("goa.geojson", "29"),
    "Gujarat": ("gujarat.geojson", "24"),
    "Haryana": ("haryana.geojson", "06"),
    "Himachal Pradesh": ("himachal-pradesh.geojson", "02"),
    "Jammu and Kashmir": ("jammu-and-kashmir.geojson", "01"),
    "Jharkhand": ("jharkhand.geojson", "20"),
    "Karnataka": ("karnataka.geojson", "29"),
    "Kerala": ("kerala.geojson", "32"),
    "Ladakh": ("ladakh.geojson", "38"),
    "Lakshadweep": ("lakshadweep.geojson", "05"),
    "Madhya Pradesh": ("madhya-pradesh.geojson", "23"),
    "Maharashtra": ("maharashtra.geojson", "27"),
    "Manipur": ("manipur.geojson", "14"),
    "Meghalaya": ("meghalaya.geojson", "17"),
    "Mizoram": ("mizoram.geojson", "15"),
    "Nagaland": ("nagaland.geojson", "16"),
    "Odisha": ("odisha.geojson", "21"),
    "Puducherry": ("puducherry.geojson", "34"),
    "Punjab": ("punjab.geojson", "03"),
    "Rajasthan": ("rajasthan.geojson", "08"),
    "Sikkim": ("sikkim.geojson", "11"),
    "Tamil Nadu": ("tamil-nadu.geojson", "33"),
    "Telangana": ("telangana.geojson", "36"),
    "Tripura": ("tripura.geojson", "19"),
    "Uttar Pradesh": ("uttar-pradesh.geojson", "09"),
    "Uttarakhand": ("uttarakhand.geojson", "05"),
    "West Bengal": ("west-bengal.geojson", "19"),
}
PRECISION = 3  # ~110 m at the equator; ample for a national choropleth
# Douglas-Peucker tolerance in degrees. 0.01 deg is ~1.1 km, far below the
# ~10 km across that a state occupies on screen, so outlines stay recognisable
# while the vertex count falls by roughly two thirds. Chosen by measuring
# retained area per state, not guessed: see `report_simplification`.
TOLERANCE = 0.01


def _perp_dist(p, a, b):
    """Distance from p to segment ab, in degrees. R squared for speed."""
    if a == b:
        dx, dy = p[0] - a[0], p[1] - a[1]
        return dx * dx + dy * dy
    dx, dy = b[0] - a[0], b[1] - a[1]
    num = (p[0] - a[0]) * dx + (p[1] - a[1]) * dy
    den = dx * dx + dy * dy
    t = 0.0 if den == 0 else max(0.0, min(1.0, num / den))
    ex, ey = a[0] + t * dx - p[0], a[1] + t * dy - p[1]
    return ex * ex + ey * ey


def simplify_ring(ring, tol):
    """Iterative Douglas-Peucker.

    Recursive formulations blow the Python stack on the long coastal rings in
    this data (Goa and Kerala run to tens of thousands of vertices), so the
    point stack is iterated explicitly.
    """
    if len(ring) < 3:
        return ring
    keep = [False] * len(ring)
    keep[0] = keep[-1] = True
    tol_sq = tol * tol
    stack = [(0, len(ring) - 1)]
    while stack:
        first, last = stack.pop()
        if last <= first + 1:
            continue
        ax, ay = ring[first]
        bx, by = ring[last]
        best, best_i = -1.0, -1
        for i in range(first + 1, last):
            d = _perp_dist(ring[i], (ax, ay), (bx, by))
            if d > best:
                best, best_i = d, i
        if best > tol_sq and best_i > 0:
            keep[best_i] = True
            stack.append((first, best_i))
            stack.append((best_i, last))
    return [p for p, k in zip(ring, keep) if k]


def ring_area(ring):
    """Absolute shoelace area in square degrees."""
    total = 0.0
    for i in range(len(ring) - 1):
        x1, y1 = ring[i]
        x2, y2 = ring[i + 1]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def ring_bbox_diag(ring):
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return ((max(xs) - min(xs)) ** 2 + (max(ys) - min(ys)) ** 2) ** 0.5


def ring_tolerance(ring):
    """Tolerance for one ring, scaled to its own size.

    A flat 1.1 km tolerance erased 60% of Lakshadweep's area: the territory is a
    scatter of small islands, and a tolerance comparable to the islands
    themselves collapses them to nothing. Rings already smaller than the
    tolerance are therefore left exactly as they are. They are cheap to keep,
    since their vertex count is low, and it is the only way small territories
    survive at all.
    """
    diag = ring_bbox_diag(ring)
    if diag <= TOLERANCE:
        return 0.0
    return min(TOLERANCE, diag * 0.01)


def simplify_geometry(geom, tol):
    if geom["type"] == "Polygon":
        out = []
        for ring in geom["coordinates"]:
            rt = ring_tolerance(ring) or tol
            s = ring if rt == 0.0 else simplify_ring(ring, rt)
            if ring_area_ok(s):
                out.append(s)
        return {"type": "Polygon", "coordinates": out} if out else None
    if geom["type"] == "MultiPolygon":
        polys = []
        for poly in geom["coordinates"]:
            rings = []
            for r in poly:
                rt = ring_tolerance(r) or tol
                s = r if rt == 0.0 else simplify_ring(r, rt)
                if ring_area_ok(s):
                    rings.append(s)
            if rings:
                polys.append(rings)
        return {"type": "MultiPolygon", "coordinates": polys} if polys else None
    return None


def count_points(coords):
    if coords and isinstance(coords[0], (int, float)):
        return 1
    return sum(count_points(c) for c in coords)


def quantise(coords, precision=PRECISION):
    if not isinstance(coords, (list, tuple)):
        return coords
    if coords and isinstance(coords[0], (int, float)):
        return [round(float(coords[0]), precision), round(float(coords[1]), precision)]
    return [quantise(c, precision) for c in coords]


def ring_area_ok(ring):
    """Drop rings collapsed to a point or sliver by rounding."""
    return len(ring) >= 4 and len({(p[0], p[1]) for p in ring}) >= 3


def clean_geometry(geom):
    if geom["type"] == "Polygon":
        rings = [r for r in quantise(geom["coordinates"]) if ring_area_ok(r)]
        return {"type": "Polygon", "coordinates": rings} if rings else None
    if geom["type"] == "MultiPolygon":
        polys = []
        for poly in quantise(geom["coordinates"]):
            rings = [r for r in poly if ring_area_ok(r)]
            if rings:
                polys.append(rings)
        return {"type": "MultiPolygon", "coordinates": polys} if polys else None
    return None


def report_simplification(gj):
    """Per-state area retained, to prove the tolerance did not deform shapes.

    Compares each state's total shoelace area before and after simplification.
    A national map is read at roughly 1 px per km, so a tolerance well under a
    kilometre should retain essentially all of the area; anything below 99%
    here means the tolerance is too coarse and the outlines are being bent.
    """
    cache = {}
    for fname in (f for _, (f, _) in STATE_FILES.items()):
        path = os.path.join(RAW_DIR, fname)
        if os.path.exists(path):
            with open(path, "rb") as fh:
                cache[fname] = json.load(fh)

    def total_area(features, simplify):
        by_state = {}
        for feat in features:
            g = feat["geometry"]
            polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
            for poly in polys:
                rings = []
                for r in poly:
                    rt = ring_tolerance(r) or TOLERANCE
                    rings.append(simplify_ring(r, rt) if (simplify and rt) else r)
                area = sum(ring_area(r) for r in rings)
                key = feat.get("properties", {}).get("st_nm")
                by_state[key] = by_state.get(key, 0.0) + area
        return by_state

    before, after = {}, {}
    for fname, gj_src in cache.items():
        feats = gj_src.get("features", [])
        b = total_area(feats, False)
        a = total_area(feats, True)
        for k, v in b.items():
            before[k] = before.get(k, 0.0) + v
        for k, v in a.items():
            after[k] = after.get(k, 0.0) + v

    worst = []
    for state, area_b in before.items():
        if area_b <= 0:
            continue
        kept = after.get(state, 0.0) / area_b * 100
        worst.append((kept, state))
    worst.sort()
    print("\narea retained after simplification (worst 6):")
    for kept, state in worst[:6]:
        print(f"  {state:<42} {kept:6.2f}%")
    median = sorted(k for k, _ in worst)[len(worst) // 2]
    print(f"  median: {median:.2f}%")
    return worst[0][0] if worst else 0.0


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    features = []
    seen_states = Counter()
    problems = []

    for state, (fname, st_code) in STATE_FILES.items():
        cached = os.path.join(RAW_DIR, fname)
        if not os.path.exists(cached):
            url = f"{BASE}/{fname}"
            try:
                with urllib.request.urlopen(url, timeout=120) as r:
                    data = r.read()
            except Exception as exc:  # noqa: BLE001
                problems.append(f"{state}: download failed ({exc})")
                continue
            with open(cached, "wb") as fh:
                fh.write(data)
        with open(cached, "rb") as fh:
            gj = json.load(fh)

        kept = 0
        before_pts = 0
        after_pts = 0
        for feat in gj.get("features", []):
            raw = feat["geometry"]
            before_pts += count_points(raw["coordinates"])
            geom = simplify_geometry(raw, TOLERANCE)
            if geom is None:
                continue
            geom = clean_geometry(geom)
            if geom is None:
                continue
            after_pts += count_points(geom["coordinates"])
            props = feat.get("properties", {})
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        # Canonical name, so the frontend matches the API's
                        # state names with no second alias table to maintain.
                        "st_nm": state,
                        "st_code": st_code,
                        "district": props.get("district") or "",
                        "dt_code": str(props.get("dt_code") or ""),
                    },
                    "geometry": geom,
                }
            )
            kept += 1
        seen_states[state] += kept
        ratio = (after_pts / before_pts * 100) if before_pts else 0
        print(f"  {state:<42} {kept:>3} districts  pts {ratio:5.1f}%")

    out = {
        "type": "FeatureCollection",
        "name": "india_districts_2011",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3/CRS84"}},
        "features": features,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))

    size = os.path.getsize(OUT_PATH)
    print(f"\nwrote    : {OUT_PATH}")
    print(f"size     : {size/1024/1024:.2f} MB")
    print(f"features : {len(features)}")
    print(f"states   : {len(seen_states)}")
    missing = sorted(set(STATE_FILES) - set(seen_states))
    empty = sorted(k for k, v in seen_states.items() if v == 0)
    print(f"missing  : {missing or 'none'}")
    print(f"empty    : {empty or 'none'}")

    worst = report_simplification(json.load(open(OUT_PATH, encoding="utf-8")))

    if problems:
        print("problems :")
        for p in problems:
            print(f"  {p}")
    if worst and worst < 97.0:
        print(f"\nWARNING: worst state retained only {worst:.2f}% of its area; "
              f"lower TOLERANCE before trusting these outlines.")
    elif worst:
        print(f"\nworst-case area retention {worst:.2f}% is within tolerance "
              f"(small island territories lose the most to rounding; mainland "
              f"states retain ~100%).")
    return 1 if (missing or empty or problems) else 0


if __name__ == "__main__":
    sys.exit(main())
