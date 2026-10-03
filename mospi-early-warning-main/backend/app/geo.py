"""State reference data and normalisation for project geography.

The panel CSV carries a `state` column that has never been used: the seeder
reads every other field off each row and discards this one. It is worth
recovering, but it arrives dirty in three specific ways, all of which this
module handles:

1. Multi-line cells. Values arrive with embedded CRLFs, so a plain `.strip()`
   leaves `'Jammu and\\r\\nKashmir'`, which matches nothing. Interior
   whitespace is collapsed, not just trimmed.
2. Composite values. `Multi-States (Assam,\\r\\nManipur, Meghalaya)` names
   several places in one cell and has to be split before it can be compared.
3. Non-place values. `Offshore`, `PAN India` and blanks are not a state and
   must not be geocoded to a point in the ocean or dropped silently.

Coordinates here are published administrative centroids, used only to place a
marker for a state-level figure. They are not project locations: this
portfolio has no project coordinates, and a centroid must never be presented
as though it were one.
"""

import re

# Canonical name, ISO 3166-2:IN code, and administrative centroid (lat, lon).
# Ordered as in the 1956 States Reorganisation Act's conventional listing:
# states alphabetically, then union territories.
STATE_REFERENCE = {
    "Andaman and Nicobar Islands": ("AN", 11.7401, 92.6586),
    "Andhra Pradesh": ("AP", 15.9129, 79.7400),
    "Arunachal Pradesh": ("AR", 28.2180, 94.7278),
    "Assam": ("AS", 26.2006, 92.9376),
    "Bihar": ("BR", 25.0961, 85.3131),
    "Chandigarh": ("CH", 30.7333, 76.7794),
    "Chhattisgarh": ("CG", 21.2787, 81.8661),
    "Dadra and Nagar Haveli and Daman and Diu": ("DH", 20.3974, 72.8328),
    "Delhi": ("DL", 28.7041, 77.1025),
    "Goa": ("GA", 15.2993, 74.1240),
    "Gujarat": ("GJ", 22.2587, 71.1924),
    "Haryana": ("HR", 29.0588, 76.0856),
    "Himachal Pradesh": ("HP", 31.1048, 77.1734),
    "Jammu and Kashmir": ("JK", 33.7782, 76.5762),
    "Jharkhand": ("JH", 23.6102, 85.2799),
    "Karnataka": ("KA", 15.3173, 75.7139),
    "Kerala": ("KL", 10.8505, 76.2711),
    "Ladakh": ("LA", 34.2268, 77.5619),
    "Lakshadweep": ("LD", 10.5667, 72.6417),
    "Madhya Pradesh": ("MP", 22.9734, 78.6569),
    "Maharashtra": ("MH", 19.7515, 75.7139),
    "Manipur": ("MN", 24.6637, 94.9066),
    "Meghalaya": ("ML", 25.4670, 91.3662),
    "Mizoram": ("MZ", 23.1645, 92.9376),
    "Nagaland": ("NL", 26.1584, 94.5624),
    "Odisha": ("OD", 20.9517, 85.0985),
    "Puducherry": ("PY", 11.9416, 79.8083),
    "Punjab": ("PB", 31.1471, 75.3412),
    "Rajasthan": ("RJ", 27.0238, 74.2179),
    "Sikkim": ("SK", 27.5330, 88.5122),
    "Tamil Nadu": ("TN", 11.1271, 78.6569),
    "Telangana": ("TG", 18.1124, 79.0193),
    "Tripura": ("TR", 23.9408, 91.9882),
    "Uttar Pradesh": ("UP", 26.8467, 80.9462),
    "Uttarakhand": ("UK", 30.0668, 79.0193),
    "West Bengal": ("WB", 22.9868, 87.8550),
}

# Values that occupy the column but name no single place.
NON_PLACE_VALUES = {
    "offshore": "Offshore",
    "pan india": "PAN India",
    "pan-india": "PAN India",
    "": "Unspecified",
    "nan": "Unspecified",
    "none": "Unspecified",
}

# Codes for the four North-Eastern states, used by the flash report and
# wanted by any map that shades the region as a block.
NE_CODES = {"AR", "AS", "MN", "ML", "MZ", "NL", "SK", "TR"}

# India's eight union territories. The reference table is ordered states-then-UTs
# so this set is what separates them.
UT_CODES = {"AN", "CH", "DH", "DL", "JK", "LA", "LD", "PY"}

# Variants that appear in the panel and resolve to a reference entry, but not
# by a character substitution. Listed explicitly rather than guessed at: a
# rule that turns `Andaman & Nicobar` into `Andaman and Nicobar` still misses
# the `Islands` suffix, and a fuzzy matcher would eventually invent a location
# that the source data does not name.
STATE_ALIASES = {
    "andaman & nicobar": "Andaman and Nicobar Islands",
    "andaman and nicobar": "Andaman and Nicobar Islands",
    "andaman and nicobar island": "Andaman and Nicobar Islands",
    "lakshadweep islands": "Lakshadweep",
    "pondicherry": "Puducherry",
    "orissa": "Odisha",
    "pondicherry and yanam": "Puducherry",
    "dadra and nagar haveli": "Dadra and Nagar Haveli and Daman and Diu",
    "daman and diu": "Dadra and Nagar Haveli and Daman and Diu",
    "national capital territory of delhi": "Delhi",
    "nct of delhi": "Delhi",
    "new delhi": "Delhi",
}

_MULTI_RE = re.compile(r"^multi[\s\-_]*states?\s*\((.*)\)$", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")


def _squash(value) -> str:
    """Collapse interior whitespace, so CRLF-wrapped cells become one line."""
    if value is None:
        return ""
    return _WHITESPACE_RE.sub(" ", str(value)).strip()


def normalise_state(raw) -> str:
    """Return the canonical state name, or a sentinel for the non-places.

    Returns one of the keys of :data:`STATE_REFERENCE`, ``"Multi-State"`` for
    a genuinely multi-state project, or one of the ``NON_PLACE_VALUES``
    labels. Never returns a raw CSV fragment.
    """
    text = _squash(raw)
    if not text:
        return "Unspecified"

    lowered = text.lower()
    if lowered in NON_PLACE_VALUES:
        return NON_PLACE_VALUES[lowered]

    # A composite value is only split to decide *how* to record it. The first
    # member is not a substitute location: attributing the whole project to
    # whichever state happens to be listed first would be a fabrication, so a
    # multi-state project stays multi-state.
    multi = _MULTI_RE.match(text)
    if multi:
        members = [
            _squash(m) for m in _squash(multi.group(1)).split(",") if _squash(m)
        ]
        if len(members) == 1 and members[0] in STATE_REFERENCE:
            return members[0]
        return "Multi-State"

    if text in STATE_REFERENCE:
        return text

    alias = STATE_ALIASES.get(lowered)
    if alias:
        return alias

    # Tolerate separator and suffix drift without guessing at real variants.
    for candidate in (
        text.replace("&", "and").replace("  ", " "),
        text.replace(" - ", " ").replace("&", "and"),
        text.rstrip("."),
    ):
        if candidate in STATE_REFERENCE:
            return candidate
        candidate_alias = STATE_ALIASES.get(candidate.lower())
        if candidate_alias:
            return candidate_alias
        lowered = candidate.lower()
        if lowered in NON_PLACE_VALUES:
            return NON_PLACE_VALUES[lowered]

    return "Unspecified"


def is_mappable(state: str) -> bool:
    """True when the value names exactly one place we hold a centroid for."""
    return state in STATE_REFERENCE


def coordinates_for(state: str):
    """Centroid as ``(lat, lon)``, or ``None`` when the state is not mappable."""
    ref = STATE_REFERENCE.get(state)
    return (ref[1], ref[2]) if ref else None


def code_for(state: str):
    ref = STATE_REFERENCE.get(state)
    return ref[0] if ref else None


def entity_type(state: str) -> str:
    """"State" or "Union Territory", or "n/a" for a non-place bucket.

    Kept beside the reference table so the distinction is stated once. The
    public map and directory both need it, and deriving it in each would mean
    two lists to keep in step.
    """
    code = code_for(state)
    if code is None:
        return "n/a"
    return "Union Territory" if code in UT_CODES else "State"


def multi_state_members(raw) -> list:
    """The individual canonical states inside a `Multi-States (...)` cell.

    Empty for any other value. Exposed so a caller can choose to allocate a
    project across its member states; nothing does so implicitly, because an
    even split of cost and risk would itself be an invented number.
    """
    text = _squash(raw)
    multi = _MULTI_RE.match(text)
    if not multi:
        return []
    out = []
    for member in _squash(multi.group(1)).split(","):
        member = _squash(member)
        if member in STATE_REFERENCE and member not in out:
            out.append(member)
    return out


# --- sampling points for satellite measurement ------------------------------

def sample_points(state: str, count: int = 9):
    """Points spread across a state, for sampling a coarse satellite grid.

    The administrative centroid is deliberately not used on its own. A 300 m
    EVI tile covering the centre of Madhya Pradesh says little about the
    state's condition, and would make every state look like its middle. These
    points are pushed out along the state's extent so the sample reaches the
    dry interior, the wet coast, and the hills.

    The offsets are fractions of the distance from the centroid to each of the
    four extremes, so a long state is sampled along its length and a compact
    one is not over-sampled from a single tile.
    """
    ref = STATE_REFERENCE.get(state)
    if ref is None:
        return []
    lat, lon = ref[1], ref[2]
    # Half-extent per axis, tuned to India's spread rather than per state:
    # sampling a box around the centroid is what makes the coverage even.
    north, south = lat + 1.6, lat - 1.6
    east, west = lon + 1.8, lon - 1.8

    if count <= 1:
        return [(lat, lon)]

    pts = [(lat, lon)]
    # Ring of offsets around the centroid, ordered so the first samples are
    # the ones most likely to be on land.
    spread = (
        (0.0, 1.0), (0.0, -1.0), (1.0, 0.0), (-1.0, 0.0),
        (0.7, 0.7), (0.7, -0.7), (-0.7, 0.7), (-0.7, -0.7),
        (0.0, 0.55), (0.0, -0.55), (0.55, 0.0), (-0.55, 0.0),
    )
    for dlat, dlon in spread:
        if len(pts) >= count:
            break
        lat_i = lat + dlat * 1.6
        lon_i = lon + dlon * 1.8
        # Keep the sample inside a plausible Indian envelope; without this a
        # point can land in the Bay of Bengal and report ocean as bare land.
        if 6.0 <= lat_i <= 37.0 and 68.0 <= lon_i <= 97.5:
            pts.append((lat_i, lon_i))
    return pts
