"""Satellite vegetation measurement from the NASA GIBS keyless WMTS service.

What this measures, and what it does not
----------------------------------------
GIBS publishes MODIS Terra EVI as 16-day composites, already rendered through
a published colour map. This module decodes those tiles and inverts the colour
map to recover EVI values, then reduces them to per-state statistics. The
inversion is exact rather than approximate: every colour in the ramp maps to a
single half-open value interval, so a reverse lookup table is lossless apart
from the interval's own width.

It is worth being blunt about the resolution. A z9 GIBS tile is about 300 m
per pixel, and EVI is a 250 m product resampled to fit, so a state statistic
here is a genuine measurement but a coarse one. More importantly it is
measured per state. A project is located at an administrative centroid, and a
300 m pixel around that point cannot describe a highway corridor, a mine
footprint, or a solar park. Nothing in this module is joined to a project.

Why the tiles are fetched as z9 only
-----------------------------------
GIBS serves these layers at a single tile-matrix level, `GoogleMapsCompatible_
Level9`. Requests at any other level return HTTP 400. That is a property of the
service, not a configuration mistake, and it caps how far a reader can zoom
before the imagery is simply being stretched.

Caching and courtesy
--------------------
Tiles are cached on disk and fetched with a descriptive User-Agent. A national
run touches a few hundred tiles per date; that is a modest amount of traffic
for a public research service, so the cache is what keeps repeat runs polite
rather than the tile count itself.
"""

import io
import math
import os
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import OrderedDict

import numpy as np
from PIL import Image

GIBS_TILE = (
    "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/{layer}"
    "/default/{date}/GoogleMapsCompatible_Level{z}/{z}/{y}/{x}.png"
)
GIBS_CAPABILITIES = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/1.0.0/WMTSCapabilities.xml"
GIBS_COLORMAP = "https://gibs.earthdata.nasa.gov/colormaps/v1.0/{name}.xml"
USER_AGENT = "MoSPI-Dhrishti-EarlyWarning/1.0 (public infrastructure monitoring; contact: MoSPI)"
EVI_LAYER = "MODIS_Terra_L3_EVI_16Day"
# A second index on exactly the same instrument, grid and date list. It costs
# one extra tile fetch per tile and is used as an independent cross-check on
# the EVI figure, because the two degrade differently under thin cloud.
NDVI_LAYER = "MODIS_Terra_L3_NDVI_16Day"
# Nominal MODIS EVI resolution. GIBS renders it coarser than this; the number
# is reported so a reader can see the true scale of the measurement.
EVI_RESOLUTION_M = 250
GIBS_ZOOM = 9
CACHE_DIR = os.getenv(
    "GIBS_CACHE_DIR",
    os.path.join(os.path.expanduser("~"), ".cache", "mospi-gibs"),
)
REQUEST_TIMEOUT = 45
TILE_RETRIES = 3

_LUT_CACHE = {}
_DATE_LIST_CACHE = {}
_CAPS_CACHE = {}


# --- capabilities -----------------------------------------------------------

def _capabilities():
    """The GIBS capabilities document, fetched once and held in memory.

    It is several megabytes and the same document answers three separate
    questions here - which dates a layer carries, which colour map renders it,
    and which tile levels exist - so parsing it more than once would be pure
    waste.
    """
    if "xml" not in _CAPS_CACHE:
        with urllib.request.urlopen(
            urllib.request.Request(GIBS_CAPABILITIES,
                                   headers={"User-Agent": USER_AGENT}),
            timeout=180,
        ) as r:
            _CAPS_CACHE["xml"] = r.read().decode("utf-8", "replace")
    return _CAPS_CACHE["xml"]


def _layer_segment(layer):
    content = _capabilities()
    i = content.find(f"{layer}</ows:Identifier>")
    if i < 0:
        raise LookupError(f"layer {layer} not present in GIBS capabilities")
    j = content.find("</Layer>", i)
    if j < 0:
        raise LookupError(f"layer {layer} has no closing tag in capabilities")
    return content[i:j]


def _colormap_name(layer):
    """Find the published colour map for a layer.

    The colour map is not named after the layer: `MODIS_Terra_L3_EVI_16Day`
    renders through `MODIS_L3_EVI`, and the VIIRS EVI layers share that same
    map. Guessing from the layer name returns 404, so the id is read from the
    layer's LegendURL in the capabilities document. The legend is an SVG whose
    name carries a `_H` suffix that the colour-map directory does not use, so
    both forms are tried.
    """
    seg = _layer_segment(layer)
    m = re.search(r"LegendURL[^>]*href=[\"']([^\"']+)[\"']", seg)
    candidates = []
    if m:
        base = m.group(1).rsplit("/", 1)[-1]
        if base.endswith(".svg"):
            base = base[:-4]
        candidates.append(base)
        if base.endswith("_H"):
            candidates.append(base[:-2])
    candidates.append(layer)

    for name in candidates:
        url = GIBS_COLORMAP.format(name=name)
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": USER_AGENT}),
                timeout=REQUEST_TIMEOUT,
            ) as r:
                if r.status == 200 and len(r.read()) > 0:
                    return name
        except Exception:  # noqa: BLE001 - try the next candidate
            continue
    raise LookupError(f"no colour map found for layer {layer} (tried {candidates})")


# --- projection -------------------------------------------------------------

def tile_for(lat, lon, z=GIBS_ZOOM):
    """Slippy-map tile containing a point, matching GIBS' Google layout."""
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    lr = math.radians(lat)
    y = int((1.0 - math.log(math.tan(lr) + 1 / math.cos(lr)) / math.pi) / 2.0 * n)
    return x, y


# --- colour map inversion ---------------------------------------------------

def load_lut(layer=EVI_LAYER):
    """Reverse lookup: packed RGB -> (EVI value, usable?).

    The colour map is a step function over RGB, so a direct table is exact.
    Bins flagged transparent in the published map are no-data (ocean, cloud,
    fill) and are marked unusable rather than read as a near-zero index, which
    would bias every coastal state downward.
    """
    if layer in _LUT_CACHE:
        return _LUT_CACHE[layer]
    name = _colormap_name(layer)
    with urllib.request.urlopen(
        urllib.request.Request(GIBS_COLORMAP.format(name=name),
                               headers={"User-Agent": USER_AGENT}),
        timeout=REQUEST_TIMEOUT,
    ) as r:
        root = ET.fromstring(r.read())

    lut = np.zeros((256, 256, 256), dtype=np.float32)
    usable = np.zeros((256, 256, 256), dtype=bool)
    for entry in root.findall("ColorMapEntry"):
        rgb_raw = entry.get("rgb")
        value_raw = entry.get("value")
        # Not every published colour map carries a value interval. A static
        # mask, for instance, is keyed on a flag with no numeric range, and a
        # missing `value` means the entry is structural rather than something
        # to invert.
        if not rgb_raw or value_raw is None:
            continue
        try:
            rgb = tuple(int(v) for v in rgb_raw.split(","))
        except ValueError:
            continue
        if len(rgb) != 3:
            continue
        # Intervals are written "[-0.3,-0.2)": a leading bracket and a closing
        # bracket or paren, so the upper bound arrives with a delimiter stuck
        # to it and has to be pulled out numerically.
        nums = re.findall(r"-?\d+\.?\d*", value_raw)
        if len(nums) < 2:
            continue
        lo, hi = float(nums[0]), float(nums[1])
        rep = min(max(0.5 * (lo + hi), lo), hi)
        lut[rgb] = rep
        usable[rgb] = (entry.get("transparent") != "true") and (hi - lo) > 1e-6

    _LUT_CACHE[layer] = (lut, usable)
    return lut, usable


# --- availability -----------------------------------------------------------

def available_dates(layer=EVI_LAYER):
    """Every date the service publishes for a layer, newest last.

    Read from the capabilities document rather than guessed on a 16-day
    cadence: the series starts and ends on specific days, and assuming a
    cadence produces 400s at the boundaries.
    """
    if layer in _DATE_LIST_CACHE:
        return _DATE_LIST_CACHE[layer]
    seg = _layer_segment(layer)

    dates = []
    for val in re.findall(r"<Value>([^<]+)</Value>", seg):
        try:
            m = re.match(r"^(\d{4}-\d{2}-\d{2})/(\d{4}-\d{2}-\d{2})/P(\d+)D$", val)
            if m:
                start, end, step = m.group(1), m.group(2), int(m.group(3))
                cur, stop = _parse_date(start), _parse_date(end)
                while cur <= stop:
                    dates.append(cur)
                    cur = _add_days(cur, step)
            else:
                dates.append(_parse_date(val))
        except (ValueError, IndexError):
            # Not every dimension is a clean daily list. A few layers publish
            # monthly or irregular ranges, and one unparseable value must not
            # take down a date lookup for the layer.
            continue
    dates = sorted(set(d for d in dates if d is not None))
    _DATE_LIST_CACHE[layer] = dates
    return dates


def _parse_date(s):
    """Parse `YYYY-MM-DD`, returning None rather than raising.

    Returning None lets the caller skip a malformed dimension value instead of
    failing the whole lookup.
    """
    from datetime import date
    parts = str(s).strip().split("-")
    if len(parts) != 3:
        return None
    try:
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None


def _add_days(d, n):
    from datetime import timedelta
    return d + timedelta(days=n)


# --- tile access ------------------------------------------------------------

class TileFetchError(RuntimeError):
    """A tile could not be retrieved for reasons other than 'no data'.

    Kept distinct from an empty result on purpose. If a network blip is
    allowed to look like an absent measurement, a run that fails halfway
    writes confident-looking "no data" rows into the database, and those rows
    are indistinguishable from real gaps forever after.
    """


def fetch_tile(layer, date, x, y, z=GIBS_ZOOM, use_cache=True):
    """PNG bytes for one tile, cached on disk.

    Returns None when the service has no tile there, which is a legitimate
    answer. Raises `TileFetchError` when retrieval itself failed, so the
    caller can refuse to record the gap as a measurement.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{layer}_{date}_{z}_{y}_{x}.png")
    if use_cache and os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, "rb") as fh:
            return fh.read()

    url = GIBS_TILE.format(layer=layer, date=date, z=z, y=y, x=x)
    last = None
    for attempt in range(TILE_RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
                data = r.read()
            with open(path, "wb") as fh:
                fh.write(data)
            return data
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 404):
                # Outside coverage for this layer, or a date the series does
                # not carry. A real answer, and not worth retrying.
                return None
            last = exc
            time.sleep(1.5 * (attempt + 1))
        except Exception as exc:  # noqa: BLE001 - network flakiness
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise TileFetchError(f"{layer} {date} ({x},{y}): {last}")


def decode_tile(blob, lut=None, usable=None):
    """EVI array plus a validity mask for one rendered tile."""
    lut, usable = (lut, usable) if lut is not None else load_lut()
    img = Image.open(io.BytesIO(blob)).convert("RGBA")
    arr = np.asarray(img)
    rgb = arr[..., :3].astype(np.int32)
    packed = rgb[..., 0] * 65536 + rgb[..., 1] * 256 + rgb[..., 2]
    evi = lut.reshape(-1)[packed]
    mask = usable.reshape(-1)[packed] & (arr[..., 3] > 0)
    return evi, mask


# --- state-level statistics -------------------------------------------------

def state_vegetation(state, date, sample_points, layer=EVI_LAYER,
                     ndvi_layer=NDVI_LAYER):
    """Reduce a set of sample points to one vegetation observation.

    `sample_points` are lat/lon pairs spread across the state. The per-tile
    median is taken across those tiles and the tile medians are then
    aggregated by median, which keeps a single cloud-obscured or coastal tile
    from moving the state's figure. The valid-pixel fraction is reported
    alongside: a state observed through a gap in the mosaic is a weaker
    measurement, and that has to be visible in the output.
    """
    lut, usable = load_lut(layer)
    ndvi_lut, ndvi_usable = load_lut(ndvi_layer) if ndvi_layer else (None, None)

    seen = OrderedDict()
    for lat, lon in sample_points:
        key = tile_for(lat, lon)
        seen.setdefault(key, [])

    tile_medians = []
    ndvi_tile_medians = []
    total_valid = 0
    total_pixels = 0
    collected = []
    fetch_failures = 0

    for (x, y) in seen:
        try:
            blob = fetch_tile(layer, date, x, y)
        except TileFetchError:
            fetch_failures += 1
            continue
        if blob is None:
            continue
        evi, mask = decode_tile(blob, lut, usable)
        if not mask.any():
            continue
        vals = evi[mask]
        tile_medians.append(float(np.median(vals)))
        collected.append(vals)
        total_valid += int(mask.sum())
        total_pixels += int(mask.size)

        # Same tile, same instrument, same date: the second index is free to
        # obtain and gives the cloud check something to disagree with.
        if ndvi_layer:
            try:
                nblob = fetch_tile(ndvi_layer, date, x, y)
            except TileFetchError:
                nblob = None
            if nblob is not None:
                ndvi, nmask = decode_tile(nblob, ndvi_lut, ndvi_usable)
                if nmask.any():
                    ndvi_tile_medians.append(float(np.median(ndvi[nmask])))

    if not collected:
        if fetch_failures and fetch_failures >= len(seen):
            # Nothing was retrievable. This is a service problem, not a
            # statement about the ground, and it must not be stored as one.
            return {
                "status": "error",
                "note": (f"all {len(seen)} tiles failed to download for {date}; "
                         f"not a measurement"),
                "tiles_sampled": 0,
                "fetch_failures": fetch_failures,
                "valid_pixel_fraction": 0.0,
            }
        return {
            "status": "no_data",
            "note": (f"no valid EVI pixels in {len(seen)} tiles for {date} "
                     f"(water or outside coverage)"),
            "tiles_sampled": 0,
            "fetch_failures": fetch_failures,
            "valid_pixel_fraction": 0.0,
        }

    pool = np.concatenate(collected)
    result = {
        "status": "ok",
        "evi_mean": float(pool.mean()),
        "evi_median": float(np.median(pool)),
        "evi_p10": float(np.percentile(pool, 10)),
        "evi_p90": float(np.percentile(pool, 90)),
        # Median of per-tile medians: robust to one poor tile.
        "evi_state_median": float(np.median(tile_medians)),
        "valid_pixel_fraction": (total_valid / total_pixels) if total_pixels else 0.0,
        "tiles_sampled": len(collected),
        "fetch_failures": fetch_failures,
    }
    if ndvi_tile_medians:
        result["ndvi_state_median"] = float(np.median(ndvi_tile_medians))
    return result


def flag_low_outliers(observations, min_states=8, z_threshold=3.0):
    """Mark states whose value sits far below every other state on the date.

    A state is not flagged for being dry; it is flagged for being *unlike
    every other state measured on the same acquisition*. That distinction is
    the whole point. A genuine dry spell affects a region and moves the
    national figure with it, whereas a cloud sheet sits over part of the
    country and leaves the national median where it was. So the check is a
    robust z-score against the cross-state median and MAD for that date, and
    only the low tail is flagged.

    The flag is deliberately not labelled "cloud". Ladakh and Ladakh-adjacent
    Jammu and Kashmir measure near 0.07 in late August, sit far outside the
    national distribution, and are doing so because they are high-altitude
    cold desert rather than because a cloud is overhead. Reporting that as
    suspected cloud would be its own kind of invented explanation, and it
    would erase the genuine finding. The note therefore says only what is
    actually established: this value is an extreme low outlier for the date,
    and the cause is not determined from these data alone.

    `observations` is a list of dicts carrying at least `state` and
    `evi_state_median`. Matching dicts are annotated in place with
    `low_outlier` and `outlier_z`. Returns the set of flagged state names.
    """
    usable = [o for o in observations
              if o.get("status") == "ok" and o.get("evi_state_median") is not None]
    if len(usable) < min_states:
        # Too few states to establish what "normal for this date" means.
        for o in observations:
            o["low_outlier"] = False
            o["outlier_z"] = None
            o["outlier_note"] = "too few states measured on this date to assess"
        return set()

    values = np.array([o["evi_state_median"] for o in usable], dtype=float)
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    # 1.4826 rescales the MAD to a standard deviation for normal data. When
    # most states agree, MAD collapses toward zero and the ratio explodes, so
    # a floor keeps a degenerate day from flagging everything.
    sigma = max(1.4826 * mad, 0.02)

    flagged = set()
    for o in observations:
        if o.get("evi_state_median") is None:
            o["low_outlier"] = False
            o["outlier_z"] = None
            o["outlier_note"] = None
            continue
        z = (o["evi_state_median"] - median) / sigma
        o["outlier_z"] = round(float(z), 2)
        if z < -z_threshold:
            o["low_outlier"] = True
            o["outlier_note"] = (
                f"{o['evi_state_median']:.3f} sits {abs(z):.1f} MAD below the "
                f"national median {median:.3f} for this date. Cause not "
                f"determined: could be cloud, or genuinely sparse vegetation."
            )
            flagged.add(o.get("state"))
        else:
            o["low_outlier"] = False
            o["outlier_note"] = None
    return flagged
