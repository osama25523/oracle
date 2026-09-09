from pathlib import Path
import hashlib, re, sys

root = Path(sys.argv[1]).resolve()
game = Path(__file__).parent / 'game_data' / 'runes7.dxr'
if not root.exists():
    raise SystemExit(f'ScummVM source not found: {root}')
if not game.exists():
    raise SystemExit(f'Game file not found: {game}')

b = game.read_bytes()
size = len(b)
md5_first5000 = hashlib.md5(b[:5000]).hexdigest()
print(f'Oracle of Runes DXR size={size} md5(first5000)={md5_first5000}')

p = root / 'engines/director/detection_tables.h'
s = p.read_text(encoding='utf-8')

if '"orunes"' not in s:
    # Add title to directorGames table before its {0,0} terminator.
    m = re.search(r'(static\s+const\s+PlainGameDescriptor\s+directorGames\[\]\s*=\s*\{)(.*?)(\n\s*\{\s*0\s*,\s*0\s*\}\s*\n\s*\};)', s, re.S)
    if not m:
        raise SystemExit('Could not find directorGames[] table in current ScummVM source.')
    body = m.group(2) + '\n\t{ "orunes", "Oracle of Runes" },'
    s = s[:m.start()] + m.group(1) + body + m.group(3) + s[m.end():]

entry = f'\tWINDEMO1("orunes", "Shareware", "runes7.dxr", "{md5_first5000}", {size}, 702),\n'
if entry.strip() not in s:
    # Prefer insertion immediately under the Director v7 heading.
    pat = re.compile(r'(//\s*Macromedia Director v7[^\n]*\n(?:\s*//[^\n]*\n){0,3})')
    m = pat.search(s)
    if not m:
        # fallback: before first known v7 entry using version 700/701/702
        m2 = re.search(r'(^\s*WIN(?:DEMO)?\d*\([^\n]+,\s*70[0-9]\)\s*,?\s*$)', s, re.M)
        if not m2:
            raise SystemExit('Could not locate Director v7 detection section.')
        s = s[:m2.start()] + entry + s[m2.start():]
    else:
        s = s[:m.end()] + entry + s[m.end():]

p.write_text(s, encoding='utf-8')
print('Patched:', p)
print('Target id: orunes')
