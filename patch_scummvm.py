import sys
from pathlib import Path

if len(sys.argv) != 2:
    print("Usage: python3 patch_scummvm.py <scummvm-source-dir>")
    sys.exit(1)

root = Path(sys.argv[1]).resolve()

tables = root / "engines" / "director" / "detection_tables.h"

if not tables.exists():
    raise FileNotFoundError(tables)

text = tables.read_text(encoding="utf-8")

# -------------------------------------------------------
# Add Oracle of Runes game name
# -------------------------------------------------------

if '"Oracle of Runes"' not in text:
    marker = '\t{ 0, 0 }\n};'

    pos = text.find(marker)

    if pos == -1:
        raise RuntimeError("Could not find end of directorGames table")

    entry = '\t{ "orunes", "Oracle of Runes" },\n'

    text = text[:pos] + entry + text[pos:]

    print("Added Oracle of Runes name")

tables.write_text(text, encoding="utf-8")

print("Patch completed.")
