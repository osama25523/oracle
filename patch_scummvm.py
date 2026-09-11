import sys
import re
from pathlib import Path

if len(sys.argv) != 2:
    print("Usage: python3 patch_scummvm.py <scummvm-source-dir>")
    sys.exit(1)

root = Path(sys.argv[1]).resolve()

builtins_cpp = root / "engines" / "director" / "lingo" / "lingo-builtins.cpp"
builtins_h = root / "engines" / "director" / "lingo" / "lingo-builtins.h"
activity = root / "backends" / "platform" / "android" / "org" / "scummvm" / "scummvm" / "ScummVMActivity.java"

for p in (builtins_cpp, builtins_h, activity):
    if not p.exists():
        raise FileNotFoundError(str(p))

# ============================================================
# A) Director/Lingo compatibility for Oracle of Runes
# ============================================================

cpp = builtins_cpp.read_text(encoding="utf-8")

if "ORACLE_RUNES_SAFE_XTRA" not in cpp:
    xtra_pattern = re.compile(
        r'(?m)^(?P<indent>\s*)\{\s*"xtra"\s*,\s*LB::b_xtra\s*,\s*1\s*,\s*1\s*,\s*500\s*,\s*FBLTIN\s*\}\s*,\s*(?://[^\n]*)?$'
    )
    match = xtra_pattern.search(cpp)
    if not match:
        raise RuntimeError("Could not find current ScummVM xtra builtin registration")

    indent = match.group("indent")
    replacement = (
        f'{indent}{{ "xtra", LB::b_orunesXtra, 1, 1, 500, FBLTIN }}, // ORACLE_RUNES_SAFE_XTRA\n'
        f'{indent}{{ "xtnd", LB::b_orunesXtnd, -1, 0, 200, FBLTIN }}, // ORACLE_RUNES_SAFE_XTND'
    )
    cpp = cpp[:match.start()] + "".join(replacement) + cpp[match.end():]

    impl_anchor = "void LB::b_xtra(int nargs) {"
    impl_pos = cpp.find(impl_anchor)
    if impl_pos == -1:
        raise RuntimeError("Could not locate LB::b_xtra implementation")

    helpers = r'''
// ORACLE_RUNES_SAFE_XTRA
void LB::b_orunesXtra(int nargs) {
	if (nargs > 0)
		g_lingo->dropStack(nargs);

	warning("Oracle of Runes: xtra() compatibility fallback used");
	g_lingo->push(Datum(0));
}

// ORACLE_RUNES_SAFE_XTND
void LB::b_orunesXtnd(int nargs) {
	if (nargs > 0)
		g_lingo->dropStack(nargs);

	warning("Oracle of Runes: xtnd() compatibility fallback used");
	g_lingo->push(Datum(0));
}

'''
    cpp = cpp[:impl_pos] + helpers + cpp[impl_pos:]
    builtins_cpp.write_text(cpp, encoding="utf-8")
    print("Applied Oracle xtra/xtnd compatibility patch.")
else:
    print("Oracle xtra/xtnd patch already present.")

hdr = builtins_h.read_text(encoding="utf-8")
if "void b_orunesXtra(int nargs);" not in hdr:
    anchor = "void b_xtra(int nargs);"
    if anchor not in hdr:
        raise RuntimeError("Could not find b_xtra declaration in lingo-builtins.h")

    hdr = hdr.replace(
        anchor,
        anchor + "\nvoid b_orunesXtra(int nargs);\nvoid b_orunesXtnd(int nargs);",
        1,
    )
    builtins_h.write_text(hdr, encoding="utf-8")
    print("Added Oracle xtra/xtnd declarations.")

# ------------------------------------------------------------
# getAt compatibility
# Upstream ARRBOUNDSCHECK/TYPECHECK paths can return without pushing
# a value. Since getAt is registered as a function, that opens the
# debugger with: Builtin 'getAt' did not return value.
# ------------------------------------------------------------

cpp = builtins_cpp.read_text(encoding="utf-8")

if "ORACLE_RUNES_SAFE_GETAT" not in cpp:
    getat_pattern = re.compile(
        r'(?m)^(?P<indent>\s*)\{\s*"getAt"\s*,\s*LB::b_getAt\s*,\s*2\s*,\s*2\s*,\s*400\s*,\s*FBLTIN_LIST\s*\}\s*,\s*(?://[^\n]*)?$'
    )
    match = getat_pattern.search(cpp)
    if not match:
        raise RuntimeError("Could not find current ScummVM getAt builtin registration")

    indent = match.group("indent")
    replacement = f'{indent}{{ "getAt", LB::b_orunesGetAt, 2, 2, 400, FBLTIN_LIST }}, // ORACLE_RUNES_SAFE_GETAT'
    cpp = cpp[:match.start()] + replacement + cpp[match.end():]

    impl_anchor = "void LB::b_getAt(int nargs) {"
    impl_pos = cpp.find(impl_anchor)
    if impl_pos == -1:
        raise RuntimeError("Could not locate LB::b_getAt implementation")

    helper = r'''
// ORACLE_RUNES_SAFE_GETAT
void LB::b_orunesGetAt(int nargs) {
	Datum indexD = g_lingo->pop();
	Datum list = g_lingo->pop();

	if (indexD.type != INT && indexD.type != FLOAT) {
		warning("Oracle of Runes: getAt() received invalid index type; returning void");
		g_lingo->pushVoid();
		return;
	}

	int index = indexD.asInt();

	switch (list.type) {
	case ARRAY:
	case POINT:
	case RECT:
		if (index < 1 || index > (int)list.u.farr->arr.size()) {
			warning("Oracle of Runes: getAt() index %d out of bounds; returning void", index);
			g_lingo->pushVoid();
			return;
		}
		g_lingo->push(list.u.farr->arr[index - 1]);
		return;

	case PARRAY:
		if (index < 1 || index > (int)list.u.parr->arr.size()) {
			warning("Oracle of Runes: getAt() property-list index %d out of bounds; returning void", index);
			g_lingo->pushVoid();
			return;
		}
		g_lingo->push(list.u.parr->arr[index - 1].v);
		return;

	default:
		warning("Oracle of Runes: getAt() received unsupported list type; returning void");
		g_lingo->pushVoid();
		return;
	}
}

'''
    cpp = cpp[:impl_pos] + helper + cpp[impl_pos:]
    builtins_cpp.write_text(cpp, encoding="utf-8")
    print("Applied Oracle safe getAt compatibility patch.")
else:
    print("Oracle getAt patch already present.")

hdr = builtins_h.read_text(encoding="utf-8")
if "void b_orunesGetAt(int nargs);" not in hdr:
    anchor = "void b_getAt(int nargs);"
    if anchor not in hdr:
        raise RuntimeError("Could not find b_getAt declaration in lingo-builtins.h")
    hdr = hdr.replace(anchor, anchor + "\nvoid b_orunesGetAt(int nargs);", 1)
    builtins_h.write_text(hdr, encoding="utf-8")
    print("Added Oracle getAt declaration.")

# ============================================================
# B) Android direct boot
# ============================================================

java = activity.read_text(encoding="utf-8")
marker = "// ORACLE_RUNES_DIRECT_BOOT_PATCH"

if marker not in java:
    oncreate_pattern = re.compile(
        r'(?m)^\t@Override\n\tpublic void onCreate\(Bundle savedInstanceState\) \{'
    )
    oncreate_match = oncreate_pattern.search(java)
    if not oncreate_match:
        raise RuntimeError("Could not find ScummVMActivity.onCreate()")

    helpers = r'''
	// ORACLE_RUNES_DIRECT_BOOT_PATCH
	private void copyOracleAsset(String assetName, File destination) throws IOException {
		try (
			InputStream in = getAssets().open("oracle-runes-game/" + assetName);
			OutputStream out = new FileOutputStream(destination)
		) {
			byte[] buffer = new byte[8192];
			int count;
			while ((count = in.read(buffer)) != -1)
				out.write(buffer, 0, count);
		}
	}

	private void prepareOracleOfRunes() throws IOException {
		File gameDir = new File(getFilesDir(), "oracle-runes-game");
		if (!gameDir.exists() && !gameDir.mkdirs())
			throw new IOException("Could not create Oracle of Runes directory");

		File dxr = new File(gameDir, "runes7.dxr");
		File dat = new File(gameDir, "Runes.dat");
		File skr = new File(gameDir, "Runes.skr");

		if (!dxr.exists() || dxr.length() == 0)
			copyOracleAsset("runes7.dxr", dxr);
		if (!dat.exists())
			copyOracleAsset("Runes.dat", dat);
		if (!skr.exists())
			copyOracleAsset("Runes.skr", skr);

		String gamePath = gameDir.getAbsolutePath().replace("\\", "/");
		File config = new File(getFilesDir(), "scummvm.ini");

		String configText =
			"[scummvm]\n\n" +
			"[orunes]\n" +
			"description=Oracle of Runes\n" +
			"engineid=director\n" +
			"gameid=director\n" +
			"platform=windows\n" +
			"version=702\n" +
			"path=" + gamePath + "\n" +
			"start_movie=runes7.dxr\n";

		try (FileOutputStream out = new FileOutputStream(config, false)) {
			out.write(configText.getBytes("UTF-8"));
		}
	}

'''
    java = java[:oncreate_match.start()] + helpers + java[oncreate_match.start():]

    args_pattern = re.compile(
        r'\t\tfinal Uri intentData = getIntent\(\)\.getData\(\);\n'
        r'\t\tString\[\] args;.*?'
        r'\t\t_scummvm\.setArgs\(args\);',
        re.DOTALL,
    )

    direct_args = '''\t\ttry {
\t\t\tprepareOracleOfRunes();
\t\t} catch (IOException e) {
\t\t\tLog.e(ScummVM.LOG_TAG, "Failed to prepare Oracle of Runes", e);
\t\t}

\t\tString[] args = new String[]{
\t\t\t"ScummVM",
\t\t\t"orunes"
\t\t};
\t\t_scummvm.setArgs(args);'''

    java, count = args_pattern.subn(direct_args, java, count=1)
    if count != 1:
        raise RuntimeError("Could not find current ScummVM Android argument block")

    activity.write_text(java, encoding="utf-8")
    print("Applied Oracle Android direct-boot patch.")
else:
    print("Android direct-boot patch already present.")

# ============================================================
# C) Strong verification
# ============================================================

cpp_check = builtins_cpp.read_text(encoding="utf-8")
hdr_check = builtins_h.read_text(encoding="utf-8")
java_check = activity.read_text(encoding="utf-8")

checks = {
    "xtra registration redirected": '"xtra", LB::b_orunesXtra' in cpp_check,
    "xtnd registration present": '"xtnd", LB::b_orunesXtnd' in cpp_check,
    "getAt registration redirected": '"getAt", LB::b_orunesGetAt' in cpp_check,
    "xtra implementation present": "void LB::b_orunesXtra(int nargs)" in cpp_check,
    "xtnd implementation present": "void LB::b_orunesXtnd(int nargs)" in cpp_check,
    "getAt implementation present": "void LB::b_orunesGetAt(int nargs)" in cpp_check,
    "header xtra declaration": "void b_orunesXtra(int nargs);" in hdr_check,
    "header xtnd declaration": "void b_orunesXtnd(int nargs);" in hdr_check,
    "header getAt declaration": "void b_orunesGetAt(int nargs);" in hdr_check,
    "Android direct boot": "ORACLE_RUNES_DIRECT_BOOT_PATCH" in java_check,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise RuntimeError("Patch verification failed: " + ", ".join(failed))

print("ALL ORACLE OF RUNES PATCH CHECKS PASSED")
