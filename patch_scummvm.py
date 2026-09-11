import sys
from pathlib import Path

if len(sys.argv) != 2:
    print("Usage: python3 patch_scummvm.py <scummvm-source-dir>")
    sys.exit(1)

root = Path(sys.argv[1]).resolve()

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

if not activity.exists():
    raise FileNotFoundError(activity)

text = activity.read_text(encoding="utf-8")

marker = "// ORACLE_RUNES_DIRECT_BOOT_PATCH"

if marker in text:
    print("Oracle of Runes Android direct boot patch already applied.")
    sys.exit(0)

# ---------------------------------------------------------
# Add helper methods before onCreate()
# ---------------------------------------------------------

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
			copyStreamToStream(in, out);
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

		if (!runesDxr.exists() || runesDxr.length() == 0) {
			copyOracleAsset("runes7.dxr", runesDxr);
		}

		if (!runesDat.exists()) {
			copyOracleAsset("Runes.dat", runesDat);
		}

		if (!runesSkr.exists()) {
			copyOracleAsset("Runes.skr", runesSkr);
		}

		File config = new File(getFilesDir(), "scummvm.ini");

		String gamePath = gameDir.getAbsolutePath().replace("\\", "/");

		String configText =
			"[scummvm]\n" +
			"gui_browser_show_hidden=true\n" +
			"\n" +
			"[orunes]\n" +
			"description=Oracle of Runes\n" +
			"engineid=director\n" +
			"gameid=director\n" +
			"platform=windows\n" +
			"path=" + gamePath + "\n" +
			"start_movie=runes7.dxr\n";

		try (FileOutputStream output = new FileOutputStream(config, false)) {
			output.write(configText.getBytes("UTF-8"));
		}

		Log.d(ScummVM.LOG_TAG, "Oracle of Runes prepared at: " + gamePath);
	}

'''

text = text.replace(anchor, helper_code + anchor, 1)

# ---------------------------------------------------------
# Replace normal launcher args with direct Oracle target
# ---------------------------------------------------------

old_args = '''		// Start ScummVM
		final Uri intentData = getIntent().getData();
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

new_args = '''		// Start Oracle of Runes directly
		try {
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

print("Oracle of Runes direct Android boot patch applied successfully.")
