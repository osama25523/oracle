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

# ---------------------------------------------------------
# 1) Add human-readable game name
# ---------------------------------------------------------

if '"orunes"' not in text:
    start_marker = "static const PlainGameDescriptor directorGames[] = {"
    start = text.find(start_marker)

    if start == -1:
        raise RuntimeError("directorGames table not found")

    end = text.find("};", start)

    if end == -1:
        raise RuntimeError("directorGames table end not found")

    entry = '\t{ "orunes", "Oracle of Runes" },\n'

    text = text[:end] + entry + text[end:]

    print("Added Oracle of Runes to directorGames")
else:
    print("Oracle of Runes game ID already exists")


# ---------------------------------------------------------
# 2) Add actual Director 7 game detection entry
# ---------------------------------------------------------

oracle_detection_marker = "ORACLE_OF_RUNES_DETECTION"

if oracle_detection_marker not in text:

    table_marker = "static const DirectorGameDescription gameDescriptions[] = {"
    table_start = text.find(table_marker)

    if table_start == -1:
        raise RuntimeError("gameDescriptions table not found")

    end_marker = "{ AD_TABLE_END_MARKER, GID_GENERIC, 0 }"
    insert_pos = text.find(end_marker, table_start)

    if insert_pos == -1:
        raise RuntimeError("AD_TABLE_END_MARKER not found")

    entry = '''
\t// ORACLE_OF_RUNES_DETECTION
\tWINGAME1(
\t\t"orunes",
\t\t"",
\t\t"runes7.dxr",
\t\t"33f63d3d8f8e26f604e42cb332bc311b",
\t\t3319232,
\t\t702
\t),

'''

    text = text[:insert_pos] + entry + text[insert_pos:]

    print("Added Oracle of Runes Director 7.02 detection")
else:
    print("Oracle of Runes detection already exists")


tables.write_text(text, encoding="utf-8")

print("Oracle of Runes patch completed successfully.")
