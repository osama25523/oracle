import sys
from pathlib import Path

if len(sys.argv) != 2:
    print("Usage: python3 patch_scummvm.py <scummvm-source-dir>")
    sys.exit(1)

root = Path(sys.argv[1]).resolve()

builtins_cpp = (
    root / "engines" / "director" / "lingo" / "lingo-builtins.cpp"
)

builtins_h = (
    root / "engines" / "director" / "lingo" / "lingo-builtins.h"
)

activity = (
    root
    / "backends"
    / "platform"
    / "android"
    / "org"
    / "scummvm"
    / "scummvm"
    / "ScummVMActivity.java"
)

for f in (builtins_cpp, builtins_h, activity):
    if not f.exists():
        raise FileNotFoundError(f)

# ============================================================
# 1) Patch Lingo builtin "xtnd"
# ============================================================

cpp = builtins_cpp.read_text(encoding="utf-8")

if "ORACLE_RUNES_XTND_PATCH" not in cpp:

    # Add builtin registration near xtra
    registration = (
        '\t{ "xtra",'
    )

    pos = cpp.find(registration)

    if pos == -1:
        raise RuntimeError("Could not find xtra builtin registration")

    line_end = cpp.find("\n", pos)

    new_registration = (
        '\n'
        '\t// ORACLE_RUNES_XTND_PATCH\n'
        '\t{ "xtnd",           LB::b_xtnd,          -1, 0, 200, FBLTIN },\n'
    )

    cpp = cpp[:line_end + 1] + new_registration + cpp[line_end + 1:]

    # Add implementation before b_xtra()
    impl_anchor = "void LB::b_xtra(int nargs) {"

    impl_pos = cpp.find(impl_anchor)

    if impl_pos == -1:
        raise RuntimeError("Could not find LB::b_xtra")

    implementation = r'''
// ORACLE_RUNES_XTND_PATCH
void LB::b_xtnd(int nargs) {
	warning("Oracle of Runes: xtnd() stub called with %d args", nargs);

	if (nargs > 0)
		g_lingo->dropStack(nargs);

	// Oracle of Runes expects xtnd() to return a value.
	// Return a neutral integer rather than entering the debugger.
	g_lingo->push(Datum(0));
}

'''

    cpp = cpp[:impl_pos] + implementation + cpp[impl_pos:]

    builtins_cpp.write_text(cpp, encoding="utf-8")

    print("Added xtnd fallback builtin.")
else:
    print("xtnd patch already present.")

# ============================================================
# 2) Add declaration to lingo-builtins.h
# ============================================================

hdr = builtins_h.read_text(encoding="utf-8")

if "void b_xtnd(int nargs);" not in hdr:
    anchor = "void b_xtra(int nargs);"

    if anchor not in hdr:
        raise RuntimeError("Could not find b_xtra declaration")

    hdr = hdr.replace(
        anchor,
        anchor + "\nvoid b_xtnd(int nargs);",
        1
    )

    builtins_h.write_text(hdr, encoding="utf-8")

    print("Added b_xtnd declaration.")
else:
    print("b_xtnd declaration already present.")

# ============================================================
# 3) Keep Oracle of Runes Android direct boot
# ============================================================

text = activity.read_text(encoding="utf-8")

marker = "// ORACLE_RUNES_DIRECT_BOOT_PATCH"

if marker not in text:

    anchor = "\t@Override\n\tpublic void onCreate(Bundle savedInstanceState) {"

    if anchor not in text:
        raise RuntimeError("Could not find ScummVMActivity.onCreate()")

    helper_code = r'''
	// ORACLE_RUNES_DIRECT_BOOT_PATCH
	private void copyOracleAsset(String assetName, File destination) throws IOException {
		try (
			InputStream in = getAssets().open("oracle-runes-game/" + assetName);
			OutputStream out = new FileOutputStream(destination)
		) {
			byte[] buffer = new byte[8192];
			int count;

			while ((count = in.read(buffer)) != -1) {
				out.write(buffer, 0, count);
			}
		}
	}

	private void prepareOracleOfRunes() throws IOException {
		File gameDir = new File(getFilesDir(), "oracle-runes-game");

		if (!gameDir.exists() && !gameDir.mkdirs()) {
			throw new IOException("Could not create Oracle of Runes directory");
		}

		File runesDxr = new File(gameDir, "runes7.dxr");
		File runesDat = new File(gameDir, "Runes.dat");
		File runesSkr = new File(gameDir, "Runes.skr");

		if (!runesDxr.exists() || runesDxr.length() == 0)
			copyOracleAsset("runes7.dxr", runesDxr);

		if (!runesDat.exists())
			copyOracleAsset("Runes.dat", runesDat);

		if (!runesSkr.exists())
			copyOracleAsset("Runes.skr", runesSkr);

		File config = new File(getFilesDir(), "scummvm.ini");

		String gamePath = gameDir.getAbsolutePath().replace("\\", "/");

		String configText =
			"[scummvm]\n" +
			"\n" +
			"[orunes]\n" +
			"description=Oracle of Runes\n" +
			"engineid=director\n" +
			"gameid=director\n" +
			"platform=windows\n" +
			"version=702\n" +
			"path=" + gamePath + "\n" +
			"start_movie=runes7.dxr\n";

		try (FileOutputStream output = new FileOutputStream(config, false)) {
			output.write(configText.getBytes("UTF-8"));
		}
	}

'''

    text = text.replace(anchor, helper_code + anchor, 1)

    old_args = '''		final Uri intentData = getIntent().getData();
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

    new_args = '''		try {
			prepareOracleOfRunes();
		} catch (IOException e) {
			Log.e(ScummVM.LOG_TAG, "Failed to prepare Oracle of Runes", e);
		}

		String[] args = new String[]{
			"ScummVM",
			"orunes"
		};

		_scummvm.setArgs(args);'''

    if old_args not in text:
        raise RuntimeError("Could not find ScummVM argument block")

    text = text.replace(old_args, new_args, 1)

    activity.write_text(text, encoding="utf-8")

    print("Applied Android direct boot patch.")
else:
    print("Android direct boot patch already present.")

print("Oracle of Runes patch completed successfully.")
