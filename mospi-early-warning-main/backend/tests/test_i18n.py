"""Guards the frontend translation catalogue.

The catalogue lives in a .js file, so it is parsed by regex rather than imported.
The format is column-aligned (`"key":   "value"`), which the patterns below
tolerate. If the file is ever restructured, these tests should fail loudly
rather than silently pass on an empty parse -- `test_catalogue_parses` covers
that case explicitly.

Motivation: the catalogue previously advertised 22 languages while 11 had no
translations at all and the 12 that did were each missing 36 keys, so most of
the picker silently fell back to English. These tests make that state
impossible to reintroduce unnoticed.
"""

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
I18N = ROOT / "frontend" / "src" / "i18n.js"
SRC = I18N.parent

EXPECTED_LANGUAGES = ["en", "hi"]

# A language block: two-space indent, bare code, opening brace.
BLOCK_RE = re.compile(r"^  ([a-z]{2,3}):\s*\{\s*$")
# A catalogue entry. Keys are quoted and column-aligned, so allow padding
# between the closing quote and the colon.
ENTRY_RE = re.compile(r'^\s*"([^"]+)"\s*:\s*("(?:[^"\\]|\\.)*")\s*,?\s*$')
CLOSE_RE = re.compile(r"^  \},")

# t("some.key") -- the local alias each page builds from translate().
T_CALL_RE = re.compile(r"""\bt\(\s*["']([a-zA-Z][\w.]*)["']""")
# t(`prefix${expr}`) -- a key assembled at runtime, e.g. `password.strength${n}`.
# Only the static prefix is checkable, so at least one key must extend it.
T_TEMPLATE_RE = re.compile(r"""\bt\(\s*`([a-zA-Z][\w.]*)\$\{""")
# The dead-fallback anti-pattern: t never returns falsy, so `t(k) || "x"` can
# never use "x". It hides missing keys rather than handling them.
DEAD_FALLBACK_RE = re.compile(r"""\bt\(\s*["'][^"']+["']\s*\)\s*\|\|\s*["']""")

DEVA = re.compile(r"[\u0900-\u097F]")

# Values that are deliberately identical in both languages. These are not prose:
# they are axis glyphs, symbols and file-format acronyms, where a Devanagari
# "translation" would be wrong. Kept as an explicit allow-list so genuine
# untranslated prose still fails, and so each exemption has to be justified in
# review.
SHARED_SYMBOL_KEYS = {
    # Down/right arrows labelling the confusion-matrix axes.
    "matrix.arrowDown",
    # "Comma Separated Values" is a format name, not a word to translate.
    "reports.formatCsv",
    # Metric name, same in both languages.
    "ml.rocAuc",
    # "Esc" is the name of a physical keyboard key.
    "cmd.esc",
    # EVI is the index acronym, and the value is the measurement itself.
    "map.legendMax",
    # A bare "a -> b" range glyph with numeric placeholders; the arrow is the
    # only content, so there is nothing to translate.
    "map.legendRange",
    # "#3" -- a rank marker, not a word.
    "opt.rankValue",
    # "OpenTopoMap" is the name of the basemap provider, like "Esri" above.
    "map.basemap.opentopo",
    # "OpenStreetMap" is likewise a provider name, kept verbatim in both.
    "map.basemap.osm",
}


def _read():
    assert I18N.exists(), f"missing {I18N}"
    return I18N.read_text(encoding="utf-8")


def _parse():
    """-> (declared_picker_codes, {code: {key: value}})"""
    picker = re.findall(
        r'\{\s*code:\s*"([^"]+)"\s*,\s*name:\s*"[^"]+"\s*,\s*native:\s*"[^"]*"\s*\}',
        _read(),
    )
    blocks, cur = {}, None
    for line in _read().splitlines():
        m = BLOCK_RE.match(line)
        if m:
            cur = m.group(1)
            blocks[cur] = {}
            continue
        if cur is not None:
            e = ENTRY_RE.match(line)
            if e:
                blocks[cur][e.group(1)] = e.group(2)[1:-1]
            elif CLOSE_RE.match(line):
                cur = None
    return picker, blocks


def _used_keys():
    used = {}
    for path in sorted(SRC.rglob("*.jsx")):
        text = path.read_text(encoding="utf-8")
        for k in T_CALL_RE.findall(text):
            used.setdefault(k, []).append(path.name)
    return used


def _used_key_prefixes():
    prefixes = {}
    for path in sorted(SRC.rglob("*.jsx")):
        text = path.read_text(encoding="utf-8")
        for p in T_TEMPLATE_RE.findall(text):
            prefixes.setdefault(p, []).append(path.name)
    return prefixes


def test_catalogue_parses():
    """Guard the guard: a regex that matches nothing would make every
    assertion below vacuously true."""
    picker, blocks = _parse()
    assert picker, "LANGUAGES array not found -- i18n.js format changed?"
    assert set(blocks) == {"en", "hi"}, f"expected en+hi blocks, got {sorted(blocks)}"
    assert len(blocks["en"]) > 100, f"en parsed only {len(blocks['en'])} keys"


def test_only_english_and_hindi_are_offered():
    picker, blocks = _parse()
    assert picker == EXPECTED_LANGUAGES, (
        f"language picker must offer exactly {EXPECTED_LANGUAGES}, got {picker}"
    )
    # A language in the picker with no dictionary would silently fall back to
    # English while looking translated.
    assert set(picker) == set(blocks), (
        f"picker offers {picker} but dictionaries exist for {sorted(blocks)}"
    )


def test_hindi_covers_every_english_key():
    _, blocks = _parse()
    en, hi = blocks["en"], blocks["hi"]
    missing = sorted(set(en) - set(hi))
    assert not missing, f"English keys with no Hindi translation: {missing}"
    extra = sorted(set(hi) - set(en))
    assert not extra, f"Hindi keys absent from English: {extra}"


def test_hindi_values_are_actually_translated():
    """Catches a Hindi slot filled with the English string, or with a
    placeholder like 'TODO'."""
    _, blocks = _parse()
    en, hi = blocks["en"], blocks["hi"]
    untranslated = []
    for k, v in hi.items():
        if k in SHARED_SYMBOL_KEYS:
            continue
        if k in en and v == en[k]:
            untranslated.append(k)
        elif not DEVA.search(v):
            untranslated.append(k)
    assert not untranslated, f"Hindi values not in Devanagari: {untranslated}"


def test_every_used_key_exists_in_both_languages():
    used = _used_keys()
    assert used, "no t() calls found -- has the call convention changed?"
    _, blocks = _parse()
    missing_en = {k: v for k, v in used.items() if k not in blocks["en"]}
    missing_hi = {k: v for k, v in used.items() if k not in blocks["hi"]}
    assert not missing_en, (
        "t() keys with no English definition (would render as a humanised "
        f"key): {missing_en}"
    )
    assert not missing_hi, f"t() keys with no Hindi translation: {missing_hi}"


def test_runtime_composed_keys_resolve():
    """For t(`prefix${...}`), require at least one catalogue key per language
    to extend the prefix, so a renamed family cannot slip through."""
    prefixes = _used_key_prefixes()
    _, blocks = _parse()
    for prefix, files in prefixes.items():
        for code, keys in blocks.items():
            assert any(k.startswith(prefix) for k in keys), (
                f"t(`{prefix}${{...}}`) used in {sorted(set(files))} but no {code} "
                f"key starts with {prefix!r}"
            )


def test_catalogue_is_utf8_not_mojibake():
    """The Hindi block must hold real Devanagari, not re-encoded garbage.

    Regression guard. A generator step once wrote this file via a PowerShell
    pipeline (`git show ... | Out-File`), which decodes the bytes through the
    Windows console codepage and turns every Devanagari codepoint into Greek
    or Latin-extended characters. The file stayed valid UTF-8 and still parsed,
    so only this check caught it -- the parity and coverage tests all passed
    happily over mojibake.
    """
    text = _read()
    suspicious = []
    for line in text.splitlines():
        if not re.match(r'^\s*"', line):
            continue
        # Greek and Latin-extended letters should not appear in a catalogue of
        # English and Hindi. Devanagari, typographic punctuation and arrows are
        # all expected; stray Greek/Latin-extended letters are not.
        if re.search(r"[\u0370-\u03FF\u0100-\u024F]", line):
            suspicious.append(line.strip()[:70])
    assert not suspicious, (
        "possible mojibake in i18n.js (Greek/Latin-extended chars where "
        f"Devanagari should be); {len(suspicious)} lines, first few: {suspicious[:5]}"
    )


def test_hindi_block_actually_contains_devanagari():
    """Guards against a wholesale block that is English or empty."""
    _, blocks = _parse()
    hi = blocks["hi"]
    assert hi, "no Hindi entries parsed"
    with_devanagari = sum(1 for v in hi.values() if DEVA.search(v))
    # Everything except the explicit symbol allow-list must be Devanagari.
    expected = len(hi) - len(SHARED_SYMBOL_KEYS)
    assert with_devanagari == expected, (
        f"{expected - with_devanagari} Hindi values contain no Devanagari: "
        f"{sorted(k for k, v in hi.items() if k not in SHARED_SYMBOL_KEYS and not DEVA.search(v))[:10]}"
    )


def test_no_dead_fallback_pattern():
    """`t("k") || "English"` can never use the literal, because translate()
    returns the English string or a humanised key -- never falsy. The pattern
    only conceals a missing catalogue entry."""
    offenders = {}
    for path in sorted(SRC.rglob("*.jsx")):
        hits = DEAD_FALLBACK_RE.findall(path.read_text(encoding="utf-8"))
        if hits:
            offenders[path.name] = len(hits)
    assert not offenders, (
        "remove the `t(...) || \"...\"` fallbacks; they are unreachable and hide "
        f"missing keys: {offenders}"
    )
