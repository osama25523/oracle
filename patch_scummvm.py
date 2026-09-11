import sys
from pathlib import Path

if len(sys.argv) != 2:
    print("Usage: python3 patch_scummvm.py <scummvm-source-dir>")
    sys.exit(1)

root = Path(sys.argv[1]).resolve()

detection_tables = root / "engines" / "director" / "detection_tables.h"
detection_cpp = root / "engines" / "director" / "detection.cpp"

if not detection_tables.exists():
    raise FileNotFoundError(detection_tables)

if not detection_cpp.exists():
    raise FileNotFoundError(detection_cpp)

print("Patching Oracle of Runes detection...")

# ------------------------------------------------------------
# 1) Add normal table-based detection entry
# ------------------------------------------------------------

tables_text = detection_tables.read_text(
    encoding="utf-8",
    errors="ignore"
)

marker = "ORACLE_OF_RUNES_CUSTOM_ENTRY"

if marker not in tables_text:
    insert_pos = tables_text.rfind("};")

    if insert_pos == -1:
        raise RuntimeError(
            "Could not find insertion point in detection_tables.h"
        )

    oracle_entry = r'''
	// ORACLE_OF_RUNES_CUSTOM_ENTRY
	{
		{
			"orunes",
			"Oracle of Runes",
			AD_ENTRY1s(
				"runes7.dxr",
				nullptr,
				0
			),
			Common::EN_ANY,
			Common::kPlatformWindows,
			ADGF_NO_FLAGS,
			GUIO0()
		},
		7,
		702
	},

'''

    tables_text = (
        tables_text[:insert_pos]
        + oracle_entry
        + tables_text[insert_pos:]
    )

    detection_tables.write_text(
        tables_text,
        encoding="utf-8"
    )

    print("Added Oracle of Runes detection table entry.")
else:
    print("Detection table entry already exists.")

# ------------------------------------------------------------
# 2) Add filename fallback detection
# ------------------------------------------------------------

cpp_text = detection_cpp.read_text(
    encoding="utf-8",
    errors="ignore"
)

fallback_marker = "ORACLE_OF_RUNES_FILENAME_FALLBACK"

if fallback_marker not in cpp_text:

    # Find the fallbackDetect method
    search_candidates = [
        "DirectorMetaEngineDetection::fallbackDetect",
        "DirectorMetaEngineDetection::fallbackDetectExtern",
        "DirectorMetaEngineDetection::fallbackDetectFileBased"
    ]

    method_pos = -1

    for candidate in search_candidates:
        method_pos = cpp_text.find(candidate)
        if method_pos != -1:
            break

    if method_pos == -1:
        raise RuntimeError(
            "Could not find Director fallback detection function "
            "in detection.cpp"
        )

    brace_pos = cpp_text.find("{", method_pos)

    if brace_pos == -1:
        raise RuntimeError(
            "Could not find fallback function opening brace"
        )

    fallback_code = '''
	// ORACLE_OF_RUNES_FILENAME_FALLBACK
	{
		Common::FSNode runesFile = fslist.begin()->getParent().getChild("runes7.dxr");

		if (runesFile.exists()) {
			Director::DirectorGameDescription desc = {
				{
					"orunes",
					"Oracle of Runes",
					AD_ENTRY1s(
						"runes7.dxr",
						nullptr,
						0
					),
					Common::EN_ANY,
					Common::kPlatformWindows,
					ADGF_NO_FLAGS,
					GUIO0()
				},
				7,
				702
			};

			return desc;
		}
	}

'''

    cpp_text = (
        cpp_text[:brace_pos + 1]
        + fallback_code
        + cpp_text[brace_pos + 1:]
    )

    detection_cpp.write_text(
        cpp_text,
        encoding="utf-8"
    )

    print("Added filename fallback detection.")
else:
    print("Filename fallback already exists.")

print("Oracle of Runes patch completed successfully.")
