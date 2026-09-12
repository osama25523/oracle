import sys
from pathlib import Path

if len(sys.argv) != 2:
    print("Usage: python3 patch_mouse_position.py <scummvm-source-dir>")
    sys.exit(1)

root = Path(sys.argv[1]).resolve()
lingo_the_cpp = root / "engines" / "director" / "lingo" / "lingo-the.cpp"

if not lingo_the_cpp.exists():
    raise FileNotFoundError(str(lingo_the_cpp))

src = lingo_the_cpp.read_text(encoding="utf-8")
marker = "ORACLE_RUNES_TOUCH_MOUSE_POSITION_FIX"

if marker not in src:
    old_h = '''\tcase kTheMouseH:\n\t\td = g_director->getCurrentWindow()->getMousePos().x;\n\t\tbreak;'''
    new_h = '''\tcase kTheMouseH:\n\t\t// ORACLE_RUNES_TOUCH_MOUSE_POSITION_FIX\n\t\t// Android touch injection reaches Movie::processSysEvent with the correct\n\t\t// Director-stage coordinates, but Window::getMousePos() can lag behind.\n\t\t// Oracle's SPUZZ handler uses `the mouseH`, so use the movie's last\n\t\t// processed mouse coordinate, which is updated from the actual event.\n\t\tif (g_director->getCurrentWindow()->getCurrentMovie())\n\t\t\td = g_director->getCurrentWindow()->getCurrentMovie()->_lastMousePos.x;\n\t\telse\n\t\t\td = g_director->getCurrentWindow()->getMousePos().x;\n\t\tbreak;'''

    old_v = '''\tcase kTheMouseV:\n\t\td = g_director->getCurrentWindow()->getMousePos().y;\n\t\tbreak;'''
    new_v = '''\tcase kTheMouseV:\n\t\t// ORACLE_RUNES_TOUCH_MOUSE_POSITION_FIX\n\t\t// SPUZZ uses strict `mouseV > SCOREY` bounds. On Android the visible\n\t\t// touch can land exactly on the first row boundary (e.g. y=94 for A),\n\t\t// which Director's original desktop cursor normally lands just inside.\n\t\t// Nudge the event coordinate one pixel into the row so boundary taps count.\n\t\tif (g_director->getCurrentWindow()->getCurrentMovie())\n\t\t\td = g_director->getCurrentWindow()->getCurrentMovie()->_lastMousePos.y + 1;\n\t\telse\n\t\t\td = g_director->getCurrentWindow()->getMousePos().y;\n\t\tbreak;'''

    if old_h not in src:
        raise RuntimeError("Could not locate kTheMouseH implementation")
    if old_v not in src:
        raise RuntimeError("Could not locate kTheMouseV implementation")

    src = src.replace(old_h, new_h, 1)
    src = src.replace(old_v, new_v, 1)
    lingo_the_cpp.write_text(src, encoding="utf-8")
    print("Applied Oracle Android mouseH/mouseV event-position fix with row-boundary tolerance.")
else:
    print("Oracle Android mouseH/mouseV fix already present.")

check = lingo_the_cpp.read_text(encoding="utf-8")
if marker not in check or "_lastMousePos.x" not in check or "_lastMousePos.y + 1" not in check:
    raise RuntimeError("Oracle mouse-position patch verification failed")

print("ORACLE TOUCH MOUSE POSITION + BOUNDARY FIX VERIFIED")
