import sys
import re
from pathlib import Path

if len(sys.argv) != 2:
    print("Usage: python3 patch_diagnostics.py <scummvm-source-dir>")
    sys.exit(1)

root = Path(sys.argv[1]).resolve()
events_cpp = root / "engines" / "director" / "events.cpp"
builtins_cpp = root / "engines" / "director" / "lingo" / "lingo-builtins.cpp"

for p in (events_cpp, builtins_cpp):
    if not p.exists():
        raise FileNotFoundError(str(p))

# ------------------------------------------------------------
# 1) Show the coordinates and Director sprite receiving the click
# ------------------------------------------------------------
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

# ------------------------------------------------------------
# 2) Show the exact Xtra/xtnd argument requested by the movie
#    The compatibility functions are added earlier by patch_scummvm.py.
# ------------------------------------------------------------
builtins = builtins_cpp.read_text(encoding="utf-8")

xtra_pattern = re.compile(
    r'// ORACLE_RUNES_SAFE_XTRA\nvoid LB::b_orunesXtra\(int nargs\) \{.*?\n\}',
    re.DOTALL,
)
xtnd_pattern = re.compile(
    r'// ORACLE_RUNES_SAFE_XTND\nvoid LB::b_orunesXtnd\(int nargs\) \{.*?\n\}',
    re.DOTALL,
)

xtra_replacement = r'''// ORACLE_RUNES_SAFE_XTRA
void LB::b_orunesXtra(int nargs) {
	Common::String requested = "<no-arg>";
	if (nargs > 0) {
		Datum d = g_lingo->pop();
		requested = d.asString();
		if (nargs > 1)
			g_lingo->dropStack(nargs - 1);
	}
	g_system->displayMessageOnOSD(Common::U32String::format("XTRA: %s", requested.c_str()));
	warning("Oracle of Runes: xtra(%s) compatibility fallback used", requested.c_str());
	g_lingo->push(Datum(0));
}'''

xtnd_replacement = r'''// ORACLE_RUNES_SAFE_XTND
void LB::b_orunesXtnd(int nargs) {
	Common::String requested = "<no-arg>";
	if (nargs > 0) {
		Datum d = g_lingo->pop();
		requested = d.asString();
		if (nargs > 1)
			g_lingo->dropStack(nargs - 1);
	}
	g_system->displayMessageOnOSD(Common::U32String::format("XTND: %s", requested.c_str()));
	warning("Oracle of Runes: xtnd(%s) compatibility fallback used", requested.c_str());
	g_lingo->push(Datum(0));
}'''

builtins, xtra_count = xtra_pattern.subn(xtra_replacement, builtins, count=1)
builtins, xtnd_count = xtnd_pattern.subn(xtnd_replacement, builtins, count=1)

if xtra_count != 1:
    raise RuntimeError("Could not instrument Oracle xtra fallback")
if xtnd_count != 1:
    raise RuntimeError("Could not instrument Oracle xtnd fallback")

builtins_cpp.write_text(builtins, encoding="utf-8")
print("Applied Oracle Xtra diagnostics.")

# ------------------------------------------------------------
# Verification
# ------------------------------------------------------------
click_check = events_cpp.read_text(encoding="utf-8")
xtra_check = builtins_cpp.read_text(encoding="utf-8")

checks = {
    "click diagnostic": marker in click_check and "CLICK %d,%d / sprite %u" in click_check,
    "xtra diagnostic": '"XTRA: %s"' in xtra_check,
    "xtnd diagnostic": '"XTND: %s"' in xtra_check,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise RuntimeError("Diagnostic verification failed: " + ", ".join(failed))

print("ORACLE DIAGNOSTICS VERIFIED")
