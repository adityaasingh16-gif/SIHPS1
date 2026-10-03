"""Reconcile i18n: keys used in code vs keys defined, per language.

Reports the true gap for '100% translatable': any key that reaches the UI but
is not present in a language block falls through translate() to humanizeKey(),
which produces a machine-generated label rather than a real translation.
"""

import pathlib
import re
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "frontend" / "src"

# ---------------------------------------------------------------- used keys
used = defaultdict(list)  # key -> ["file:line", ...]
CALL = re.compile(r"""\bt\(\s*["']([a-zA-Z][\w.]*)["']""")
for path in sorted(SRC.rglob("*.jsx")):
    if path.name == "i18n.js":
        continue
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for m in CALL.finditer(line):
            used[m.group(1)].append(f"{path.name}:{n}")

# ------------------------------------------------------------- defined keys
lines = (SRC / "i18n.js").read_text(encoding="utf-8").splitlines()
BLOCK = re.compile(r"^(\s*)([a-z]{2,3}):\s*\{\s*$")
# Keys are column-aligned, so allow whitespace between the closing quote and colon.
ENTRY = re.compile(r'^\s*"([^"]+)"\s*:\s*')
END = re.compile(r"^\s*\},")
CODES = {"en", "as", "bn", "bodo", "doi", "gu", "hi", "kn", "ks", "gom", "mai",
         "ml", "mni", "mr", "ne", "or", "pa", "sa", "sat", "snd", "ta", "te", "ur"}

blocks, cur = [], None
for i, ln in enumerate(lines):
    m = BLOCK.match(ln)
    if m and m.group(2) in CODES:
        if cur:
            blocks.append(cur)
        cur = {"code": m.group(2), "line": i + 1, "keys": []}
        continue
    if cur is not None:
        e = ENTRY.match(ln)
        if e:
            cur["keys"].append(e.group(1))
        elif END.match(ln):
            blocks.append(cur)
            cur = None
if cur:
    blocks.append(cur)

by = {b["code"]: b for b in blocks}
en, hi = by.get("en"), by.get("hi")
en_keys, hi_keys = set(en["keys"]), set(hi["keys"])
used_keys = set(used)

print("=" * 72)
print("A. USED IN CODE BUT NOT DEFINED IN ENGLISH (renders as humanizeKey)")
print("=" * 72)
undef = sorted(used_keys - en_keys)
for k in undef:
    print(f"  {k:<34} {', '.join(used[k][:3])}")
print(f"  --> {len(undef)} undefined keys\n")

print("=" * 72)
print("B. USED IN CODE BUT NOT TRANSLATED IN HINDI (renders as English)")
print("=" * 72)
unhi = sorted(used_keys - hi_keys)
for k in unhi:
    in_en = "in en" if k in en_keys else "NOT in en either"
    print(f"  {k:<34} {in_en:<18} {', '.join(used[k][:2])}")
print(f"  --> {len(unhi)} keys not translated in Hindi\n")

print("=" * 72)
print("C. DEAD KEYS (defined, never used in any component)")
print("=" * 72)
dead = sorted(en_keys - used_keys)
for k in dead:
    print(f"  {k}")
print(f"  --> {len(dead)} dead keys\n")

declared = re.findall(
    r'\{\s*code:\s*"([^"]+)"\s*,\s*name:\s*"[^"]+"\s*,\s*native:\s*"[^"]*"\s*\}',
    (SRC / "i18n.js").read_text(encoding="utf-8"),
)

print("=" * 72)
print("SUMMARY")
print("=" * 72)
print(f"  languages in LANGUAGES picker    : {len(declared)} ({', '.join(declared)})")
print(f"  languages with a translation dict: {len(blocks)} ({', '.join(b['code'] for b in blocks)})")
print(f"  keys used in code                : {len(used_keys)}")
print(f"  keys defined in en               : {len(en_keys)}")
print(f"  keys defined in hi               : {len(hi_keys)}")
print(f"  used keys missing from en        : {len(undef)}")
print(f"  used keys missing from hi        : {len(unhi)}")
print(f"  en \\ hi (should be 0)             : {len(en_keys - hi_keys)}")
print(f"  hi \\ en (should be 0)             : {len(hi_keys - en_keys)}")
print()
ok = not undef and not unhi and not (en_keys ^ hi_keys) and set(declared) == {b["code"] for b in blocks}
print("  RESULT:", "100% PARITY" if ok else "GAPS REMAIN")
