import sys
from pathlib import Path

if len(sys.argv) != 2:
    print("Usage: python3 patch_primary_handler.py <scummvm-source-dir>")
    sys.exit(1)

root = Path(sys.argv[1]).resolve()
lingo_events_cpp = root / "engines" / "director" / "lingo" / "lingo-events.cpp"

if not lingo_events_cpp.exists():
    raise FileNotFoundError(str(lingo_events_cpp))

src = lingo_events_cpp.read_text(encoding="utf-8")
marker = "ORACLE_RUNES_PRIMARY_HANDLER_NAME_FIX"

if marker not in src:
    old = '''void Movie::setPrimaryEventHandler(LEvent event, const Common::String &code) {
\tdebugC(3, kDebugLingoExec, "setting primary event handler (%s)", _lingo->_eventHandlerTypes[event]);
\tLingoArchive *mainArchive = getMainLingoArch();
\tmainArchive->primaryEventHandlers[event] = code;
\tmainArchive->replaceCode(code, kEventScript, event);
}'''

    new = '''void Movie::setPrimaryEventHandler(LEvent event, const Common::String &code) {
\tdebugC(3, kDebugLingoExec, "setting primary event handler (%s)", _lingo->_eventHandlerTypes[event]);
\tLingoArchive *mainArchive = getMainLingoArch();
\tmainArchive->primaryEventHandlers[event] = code;

\t// ORACLE_RUNES_PRIMARY_HANDLER_NAME_FIX
\t// Director accepts a bare custom-handler name in mouseDownScript/keyUpScript,
\t// e.g. `set the mouseDownScript to "spuzz"`, and invokes that handler when
\t// the event fires. The generic Lingo compiler can interpret a bare identifier
\t// as a value instead of a zero-argument handler call. Make the intended call
\t// explicit for Oracle of Runes while preserving the stored property string.
\tCommon::String executableCode = code;
\tif (event == kEventMouseDown && code == "spuzz")
\t\texecutableCode = "SPUZZ()";

\tmainArchive->replaceCode(executableCode, kEventScript, event);
}'''

    if old not in src:
        raise RuntimeError("Could not locate Movie::setPrimaryEventHandler")

    src = src.replace(old, new, 1)
    lingo_events_cpp.write_text(src, encoding="utf-8")
    print("Applied Oracle mouseDownScript custom-handler fix.")
else:
    print("Oracle mouseDownScript custom-handler fix already present.")

check = lingo_events_cpp.read_text(encoding="utf-8")
if marker not in check or 'executableCode = "SPUZZ()"' not in check:
    raise RuntimeError("Oracle primary-handler patch verification failed")

print("ORACLE PRIMARY HANDLER FIX VERIFIED")
