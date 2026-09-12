import sys
from pathlib import Path

if len(sys.argv) != 2:
    print("Usage: python3 patch_primary_handler.py <scummvm-source-dir>")
    sys.exit(1)

root = Path(sys.argv[1]).resolve()
lingo_events_cpp = root / "engines" / "director" / "lingo" / "lingo-events.cpp"
lingo_code_cpp = root / "engines" / "director" / "lingo" / "lingo-code.cpp"
builtins_cpp = root / "engines" / "director" / "lingo" / "lingo-builtins.cpp"

for p in (lingo_events_cpp, lingo_code_cpp, builtins_cpp):
    if not p.exists():
        raise FileNotFoundError(str(p))

# -----------------------------------------------------------------------------
# 1) Make Director's bare mouseDownScript handler name executable.
# -----------------------------------------------------------------------------
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
\tif (event == kEventMouseDown && code.equalsIgnoreCase("spuzz"))
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

# -----------------------------------------------------------------------------
# 2) One-shot diagnostic checkpoint: prove whether SPUZZ() is actually entered.
#    The OSD also shows the mouseH/mouseV values Oracle should see and an inferred
#    puzzle letter/number from the visible two-column puzzle grid.
# -----------------------------------------------------------------------------
code = lingo_code_cpp.read_text(encoding="utf-8")
call_marker = "ORACLE_RUNES_SPUZZ_ENTRY_DIAGNOSTIC"

if call_marker not in code:
    # g_system/displayMessageOnOSD is used only by this diagnostic.
    if '#include "common/system.h"' not in code:
        include_anchor = '#include "graphics/macgui/macwindowmanager.h"'
        if include_anchor not in code:
            raise RuntimeError("Could not locate lingo-code.cpp include anchor")
        code = code.replace(include_anchor, '#include "common/system.h"\n' + include_anchor, 1)

    call_anchor = '''void LC::call(const Common::String &name, int nargs, bool allowRetVal) {
\tif (debugChannelSet(3, kDebugLingoExec))'''
    call_replacement = '''void LC::call(const Common::String &name, int nargs, bool allowRetVal) {
\t// ORACLE_RUNES_SPUZZ_ENTRY_DIAGNOSTIC
\tif (name.equalsIgnoreCase("spuzz")) {
\t\tint oracleX = -1;
\t\tint oracleY = -1;
\t\tWindow *oracleWindow = g_director->getCurrentWindow();
\t\tMovie *oracleMovie = oracleWindow ? oracleWindow->getCurrentMovie() : nullptr;
\t\tif (oracleMovie) {
\t\t\toracleX = oracleMovie->_lastMousePos.x;
\t\t\t// This matches patch_mouse_position.py: SPUZZ sees mouseV as lastY + 1.
\t\t\toracleY = oracleMovie->_lastMousePos.y + 1;
\t\t}

\t\tint oraclePuzzle = 0;
\t\tchar oracleLetter = '?';
\t\tif (oracleX >= 0 && oracleY >= 82) {
\t\t\t// Oracle's 13 rows are about 26 Director pixels apart; first row is A/N.
\t\t\tint oracleRow = (oracleY - 82) / 26;
\t\t\tif (oracleRow < 0)
\t\t\t\toracleRow = 0;
\t\t\tif (oracleRow > 12)
\t\t\t\toracleRow = 12;
\t\t\toraclePuzzle = (oracleX < 320) ? (oracleRow + 1) : (oracleRow + 14);
\t\t\tif (oraclePuzzle >= 1 && oraclePuzzle <= 26)
\t\t\t\toracleLetter = (char)('A' + oraclePuzzle - 1);
\t\t}

\t\tg_system->displayMessageOnOSD(Common::U32String::format(
\t\t\t"SPUZZ ENTER / mouseH %d / mouseV %d / calc %c #%d",
\t\t\toracleX, oracleY, oracleLetter, oraclePuzzle));
\t}

\tif (debugChannelSet(3, kDebugLingoExec))'''

    if call_anchor not in code:
        raise RuntimeError("Could not locate LC::call(name) implementation")
    code = code.replace(call_anchor, call_replacement, 1)
    lingo_code_cpp.write_text(code, encoding="utf-8")
    print("Applied Oracle SPUZZ entry diagnostic.")
else:
    print("Oracle SPUZZ entry diagnostic already present.")

# -----------------------------------------------------------------------------
# 3) One-shot diagnostic checkpoint: if SPUZZ reaches `go`, show the exact values
#    on the Lingo stack before ScummVM consumes them. This reveals the requested
#    frame/movie target without changing normal execution.
# -----------------------------------------------------------------------------
builtins = builtins_cpp.read_text(encoding="utf-8")
go_marker = "ORACLE_RUNES_GO_TARGET_DIAGNOSTIC"

if go_marker not in builtins:
    go_anchor = '''void LB::b_go(int nargs) {
\t// Builtin function for go as used by the Director bytecode engine.'''
    go_replacement = '''void LB::b_go(int nargs) {
\t// ORACLE_RUNES_GO_TARGET_DIAGNOSTIC
\tCommon::String oracleArg0 = "<none>";
\tCommon::String oracleArg1 = "<none>";
\tif (nargs > 0)
\t\toracleArg0 = g_lingo->peek(0).asString(true);
\tif (nargs > 1)
\t\toracleArg1 = g_lingo->peek(1).asString(true);

\tint oracleX = -1;
\tint oracleY = -1;
\tWindow *oracleWindow = g_director->getCurrentWindow();
\tMovie *oracleMovie = oracleWindow ? oracleWindow->getCurrentMovie() : nullptr;
\tif (oracleMovie) {
\t\toracleX = oracleMovie->_lastMousePos.x;
\t\toracleY = oracleMovie->_lastMousePos.y + 1;
\t}

\tint oraclePuzzle = 0;
\tchar oracleLetter = '?';
\tif (oracleX >= 0 && oracleY >= 82) {
\t\tint oracleRow = (oracleY - 82) / 26;
\t\tif (oracleRow < 0)
\t\t\toracleRow = 0;
\t\tif (oracleRow > 12)
\t\t\toracleRow = 12;
\t\toraclePuzzle = (oracleX < 320) ? (oracleRow + 1) : (oracleRow + 14);
\t\tif (oraclePuzzle >= 1 && oraclePuzzle <= 26)
\t\t\toracleLetter = (char)('A' + oraclePuzzle - 1);
\t}

\tg_system->displayMessageOnOSD(Common::U32String::format(
\t\t"SPUZZ -> GO / %c #%d / go[%s] [%s]",
\t\toracleLetter, oraclePuzzle, oracleArg0.c_str(), oracleArg1.c_str()));

\t// Builtin function for go as used by the Director bytecode engine.'''

    if go_anchor not in builtins:
        raise RuntimeError("Could not locate LB::b_go implementation")
    builtins = builtins.replace(go_anchor, go_replacement, 1)
    builtins_cpp.write_text(builtins, encoding="utf-8")
    print("Applied Oracle go-target diagnostic.")
else:
    print("Oracle go-target diagnostic already present.")

# -----------------------------------------------------------------------------
# 4) Strong verification. If this script exits successfully, the next APK has
#    all three useful states in one build:
#      CLICK only      -> primary/SPUZZ path never ran
#      SPUZZ ENTER     -> handler ran, but no `go` was reached
#      SPUZZ -> GO     -> handler ran and we see its exact navigation target
# -----------------------------------------------------------------------------
events_check = lingo_events_cpp.read_text(encoding="utf-8")
code_check = lingo_code_cpp.read_text(encoding="utf-8")
builtins_check = builtins_cpp.read_text(encoding="utf-8")
checks = {
    "primary handler": marker in events_check and 'executableCode = "SPUZZ()"' in events_check,
    "SPUZZ entry": call_marker in code_check and "SPUZZ ENTER" in code_check,
    "go target": go_marker in builtins_check and "SPUZZ -> GO" in builtins_check,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise RuntimeError("Oracle primary/diagnostic verification failed: " + ", ".join(failed))

print("ORACLE PRIMARY + SPUZZ + GO ONE-SHOT DIAGNOSTIC VERIFIED")
