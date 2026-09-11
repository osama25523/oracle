import sys
from pathlib import Path

if len(sys.argv) != 2:
    print("Usage: python3 patch_diagnostics.py <scummvm-source-dir>")
    sys.exit(1)

root = Path(sys.argv[1]).resolve()
events_cpp = root / "engines" / "director" / "events.cpp"

if not events_cpp.exists():
    raise FileNotFoundError(str(events_cpp))

src = events_cpp.read_text(encoding="utf-8")
marker = "ORACLE_RUNES_CLICK_DIAGNOSTIC"

if marker not in src:
    anchor = '''\tcase Common::EVENT_LBUTTONDOWN:\n\tcase Common::EVENT_RBUTTONDOWN:\n\t\tpos = event.mouse;\n\t\tif (sc->_waitForClick) {'''

    if anchor not in src:
        raise RuntimeError("Could not locate Director mouse-button handling block")

    replacement = '''\tcase Common::EVENT_LBUTTONDOWN:\n\tcase Common::EVENT_RBUTTONDOWN:\n\t\tpos = event.mouse;\n\n\t\t// ORACLE_RUNES_CLICK_DIAGNOSTIC\n\t\tif (event.type == Common::EVENT_LBUTTONDOWN) {\n\t\t\tg_system->displayMessageOnOSD(Common::U32String::format(\n\t\t\t\t"CLICK %d,%d / sprite %u", pos.x, pos.y, (uint)spriteId));\n\t\t}\n\n\t\tif (sc->_waitForClick) {'''

    src = src.replace(anchor, replacement, 1)
    events_cpp.write_text(src, encoding="utf-8")
    print("Applied Oracle click diagnostic patch.")
else:
    print("Oracle click diagnostic patch already present.")

check = events_cpp.read_text(encoding="utf-8")
if marker not in check or "CLICK %d,%d / sprite %u" not in check:
    raise RuntimeError("Click diagnostic verification failed")

print("ORACLE CLICK DIAGNOSTIC VERIFIED")
