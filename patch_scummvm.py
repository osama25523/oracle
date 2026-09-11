import sys
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
# A) Oracle fallback builtins: xtnd() and xtra()
# ============================================================

cpp = builtins_cpp.read_text(encoding="utf-8")

if "ORACLE_RUNES_SAFE_XTRA" not in cpp:
    old_reg = '{ "xtra", LB::b_xtra, 1, 1, 500, FBLTIN }'
    new_reg = '{ "xtra", LB::b_orunesXtra, 1, 1, 500, FBLTIN }'

    if old_reg not in cpp:
        raise RuntimeError("Could not find current ScummVM xtra builtin registration")

    cpp = cpp.replace(old_reg, new_reg, 1)

    reg_end = cpp.find("\n", cpp.find(new_reg))
    if reg_end == -1:
        raise RuntimeError("Could not locate xtra registration line end")

    cpp = (
        cpp[:reg_end + 1]
        + '\t{ "xtnd", LB::b_orunesXtnd, -1, 0, 200, FBLTIN }, // ORACLE_RUNES_SAFE_XTND\n'
        + cpp[reg_end + 1:]
    )

    impl_anchor = "void LB::b_xtra(int nargs) {"
    impl_pos = cpp.find(impl_anchor)
    if impl_pos == -1:
        raise RuntimeError("Could not locate LB::b_xtra implementation")

    helper = r'''
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
    cpp = cpp[:impl_pos] + helper + cpp[impl_pos:]
    builtins_cpp.write_text(cpp, encoding="utf-8")
    print("Applied Oracle xtra/xtnd compatibility patch.")
else:
    print("Oracle xtra/xtnd patch already present.")

hdr = builtins_h.read_text(encoding="utf-8")
if "void b_orunesXtra(int nargs);" not in hdr:
    anchor = "void b_xtra(int nargs);"
    if anchor not in hdr:
        raise RuntimeError("Could not find b_xtra declaration in lingo-builtins.h")

    replacement = (
        anchor
        + "\nvoid b_orunesXtra(int nargs);"
        + "\nvoid b_orunesXtnd(int nargs);"
    )
    hdr = hdr.replace(anchor, replacement, 1)
    builtins_h.write_text(hdr, encoding="utf-8")
    print("Added Oracle builtin declarations.")

# ============================================================
# B) Android direct boot
# ============================================================

java = activity.read_text(encoding="utf-8")
marker = "// ORACLE_RUNES_DIRECT_BOOT_PATCH"

if marker not in java:
    oncreate_anchor = "\t@Override\n\tpublic void onCreate(Bundle savedInstanceState) {"
    if oncreate_anchor not in java:
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
    java = java.replace(oncreate_anchor, helpers + oncreate_anchor, 1)

    old = '''		final Uri intentData = getIntent().getData();
		String[] args;
		if (intentData == null) {
			args = new String[]{
				"ScummVM"
			};
		} else {
			args = new String[]{
				"ScummVM",
				intentData.getSchemeSpecificPart()
			};
		}
		_scummvm.setArgs(args);'''

    new = '''		try {
			prepareOracleOfRunes();
		} catch (IOException e) {
			Log.e(ScummVM.LOG_TAG, "Failed to prepare Oracle of Runes", e);
		}

		String[] args = new String[]{
			"ScummVM",
			"orunes"
		};

		_scummvm.setArgs(args);'''

    if old not in java:
        raise RuntimeError(
            "Android launch block changed upstream. "
            "Do not build: send the GitHub error so the patch can be updated."
        )

    java = java.replace(old, new, 1)
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
    "xtra implementation present": "void LB::b_orunesXtra(int nargs)" in cpp_check,
    "xtnd implementation present": "void LB::b_orunesXtnd(int nargs)" in cpp_check,
    "header xtra declaration": "void b_orunesXtra(int nargs);" in hdr_check,
    "header xtnd declaration": "void b_orunesXtnd(int nargs);" in hdr_check,
    "Android direct boot": "ORACLE_RUNES_DIRECT_BOOT_PATCH" in java_check,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise RuntimeError("Patch verification failed: " + ", ".join(failed))

print("ALL ORACLE OF RUNES PATCH CHECKS PASSED")
