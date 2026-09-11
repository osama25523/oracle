from pathlib import Path
import hashlib
import re
import sys

root = Path(sys.argv[1]).resolve()
game = Path(__file__).parent / "game_data" / "runes7.dxr"

if not root.exists():
    raise SystemExit(f"ScummVM source not found: {root}")
if not game.exists():
    raise SystemExit(f"Game file not found: {game}")

b = game.read_bytes()
size = len(b)
md5_first5000 = hashlib.md5(b[:5000]).hexdigest()
md5_full = hashlib.md5(b).hexdigest()
print(f"Oracle of Runes: size={size}")
print(f"MD5 first 5000 bytes={md5_first5000}")
print(f"MD5 full file={md5_full}")

# ---------------------------------------------------------------------------
# 1) Add a normal Advanced Detector entry using the exact runes7.dxr fingerprint.
# ---------------------------------------------------------------------------
tables = root / "engines/director/detection_tables.h"
s = tables.read_text(encoding="utf-8")

if '{ "orunes",' not in s:
    m = re.search(
        r'(static\s+const\s+PlainGameDescriptor\s+directorGames\[\]\s*=\s*\{)(.*?)(\n\s*\{\s*0\s*,\s*0\s*\}\s*\n\s*\};)',
        s,
        re.S,
    )
    if not m:
        raise SystemExit("Could not find directorGames[] table")
    body = m.group(2) + '\n\t{ "orunes",\t\t\t"Oracle of Runes" },'
    s = s[:m.start()] + m.group(1) + body + m.group(3) + s[m.end():]

# Use WINGAME1 instead of WINDEMO1. The variant is labelled Shareware, but this
# does not need the generic ADGF_DEMO flag to launch correctly.
entry = f'\tWINGAME1("orunes", "Shareware", "runes7.dxr", "{md5_first5000}", {size}, 702),\n'

# Remove an older Oracle entry if this builder has already been applied.
s = re.sub(
    r'^\s*WIN(?:DEMO|GAME)1\("orunes",\s*"Shareware",\s*"runes7\.dxr",[^\n]*\n',
    '',
    s,
    flags=re.M,
)

# Put the entry immediately after gameDescriptions[] opens. The physical order is
# irrelevant to Advanced Detector, and this avoids depending on headings that may
# change in future ScummVM versions.
gm = re.search(r'(static\s+const\s+DirectorGameDescription\s+gameDescriptions\[\]\s*=\s*\{\s*\n)', s)
if not gm:
    raise SystemExit("Could not find Director gameDescriptions[] table")
s = s[:gm.end()] + '\t// Oracle of Runes v2.0 Shareware (custom Android builder)\n' + entry + s[gm.end():]

tables.write_text(s, encoding="utf-8")
print("Patched detection table:", tables)

# ---------------------------------------------------------------------------
# 2) Add a filename fallback specifically for runes7.dxr.
#
# This is intentionally independent of MD5. If Android storage, a copied file,
# or a future detector change prevents the normal table match, selecting a folder
# containing runes7.dxr will still report Oracle of Runes as a Director 7.02 game.
# It also sets filesDescriptions[0].fileName, so the Director engine knows which
# movie to start when the user presses Start.
# ---------------------------------------------------------------------------
detection = root / "engines/director/detection.cpp"
d = detection.read_text(encoding="utf-8")

marker = "// ORACLE_OF_RUNES_FILENAME_FALLBACK"
if marker not in d:
    needle = '''\t\tif (!fileName.hasSuffix(".exe"))\n\t\t\tcontinue;'''
    if needle not in d:
        raise SystemExit("Could not locate Director fallback .exe check")

    block = r'''\t\t// ORACLE_OF_RUNES_FILENAME_FALLBACK
\t\t// Oracle of Runes is distributed here as the original Director 7 DXR movie,
\t\t// not as the Windows projector EXE. Detect it by its canonical filename as a
\t\t// robust fallback in addition to the exact MD5 table entry.
\t\tif (fileName.equalsIgnoreCase("runes7.dxr")) {
\t\t\tdesc->version = 702;
\t\t\tdesc->desc.gameId = "orunes";
\t\t\tdesc->desc.extra = "Shareware";
\t\t\tdesc->desc.language = Common::EN_ANY;
\t\t\tdesc->desc.platform = Common::kPlatformWindows;
\t\t\tdesc->desc.flags = ADGF_NO_FLAGS;
\t\t\tCommon::strlcpy(s_fallbackFileNameBuffer, file->getName().c_str(), sizeof(s_fallbackFileNameBuffer));
\t\t\tdesc->desc.filesDescriptions[0].fileName = s_fallbackFileNameBuffer;

\t\t\tif (extraInfo != nullptr) {
\t\t\t\t*extraInfo = new ADDetectedGameExtraInfo;
\t\t\t\t(*extraInfo)->targetID = "orunes";
\t\t\t\t(*extraInfo)->gameName = "Oracle of Runes";
\t\t\t}

\t\t\tADDetectedGame game(&desc->desc);
\t\t\treturn game;
\t\t}

'''
    d = d.replace(needle, block + needle, 1)
    detection.write_text(d, encoding="utf-8")
    print("Patched filename fallback:", detection)
else:
    print("Filename fallback already present")

# Verification output used by GitHub Actions logs.
check_tables = tables.read_text(encoding="utf-8")
check_detection = detection.read_text(encoding="utf-8")
assert '"orunes"' in check_tables
assert 'WINGAME1("orunes"' in check_tables
assert marker in check_detection
assert 'equalsIgnoreCase("runes7.dxr")' in check_detection
print("Oracle of Runes patch verification: OK")
print("Target ID: orunes")
