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
# 1) Add Oracle of Runes to the readable game-name table
# -------------------------------------------------------

game_name_entry = '\t{ "orunes",\t\t\t"Oracle of Runes" },\n'

if '"Oracle of Runes"' not in text:
    marker = '\t{ 0, 0 }\n};'

    pos = text.find(marker)

    if pos == -1:
        raise RuntimeError("Could not find end of directorGames table")

    text = text[:pos] + game_name_entry + text[pos:]

    print("Added Oracle of Runes game name.")
else:
    print("Oracle of Runes game name already present.")

# -------------------------------------------------------
# 2) Add Director detection entry
# -------------------------------------------------------

detection_marker = "// ORACLE_OF_RUNES_DETECTION"

if detection_marker not in text:
    end_marker = "\t{ AD_TABLE_END_MARKER, GID_GENERIC, 0 }"

    pos = text.find(end_marker)

    if pos == -1:
        raise RuntimeError("Could not find gameDescriptions end marker")

    entry = '''\
\t// ORACLE_OF_RUNES_DETECTION
\tWINGAME1("orunes", "", "runes7.dxr",
\t\t"33f63d3d8f8e26f604e42cb332bc311b",
\t\t3319232, 702),

'''

    text = text[:pos] + entry + text[pos:]

    print("Added Oracle of Runes Director detection.")
else:
    print("Oracle of Runes detection already present.")

tables.write_text(text, encoding="utf-8")

print("Patch completed successfully.")
