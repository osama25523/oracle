import sys
from pathlib import Path

if len(sys.argv) != 2:
    print("Usage: python3 patch_primary_handler.py <scummvm-source-dir>")
    sys.exit(1)

root = Path(sys.argv[1]).resolve()
lingo_events_cpp = root / "engines" / "director" / "lingo" / "lingo-events.cpp"
lingo_code_cpp = root / "engines" / "director" / "lingo" / "lingo-code.cpp"
builtins_cpp = root / "engines" / "director" / "lingo" / "lingo-builtins.cpp"
lingo_funcs_cpp = root / "engines" / "director" / "lingo" / "lingo-funcs.cpp"

for p in (lingo_events_cpp, lingo_code_cpp, builtins_cpp, lingo_funcs_cpp):
    if not p.exists():
        raise FileNotFoundError(str(p))

# 1) Make Director's bare mouseDownScript handler name executable.
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
\n\t// ORACLE_RUNES_PRIMARY_HANDLER_NAME_FIX
\tCommon::String executableCode = code;
\tif (event == kEventMouseDown && code.equalsIgnoreCase("spuzz"))
\t\texecutableCode = "SPUZZ()";
\n\tmainArchive->replaceCode(executableCode, kEventScript, event);
}'''
    if old not in src:
        raise RuntimeError("Could not locate Movie::setPrimaryEventHandler")
    src = src.replace(old, new, 1)
    lingo_events_cpp.write_text(src, encoding="utf-8")

# 2) Compact SPUZZ entry diagnostic.
code = lingo_code_cpp.read_text(encoding="utf-8")
call_marker = "ORACLE_RUNES_SPUZZ_ENTRY_DIAGNOSTIC"
if call_marker not in code:
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
\t\tWindow *oracleWindow = g_director->getCurrentWindow();
\t\tMovie *oracleMovie = oracleWindow ? oracleWindow->getCurrentMovie() : nullptr;
\t\tif (oracleMovie) {
\t\t\tint oracleX = oracleMovie->_lastMousePos.x;
\t\t\tint oracleY = oracleMovie->_lastMousePos.y + 1;
\t\t\tg_system->displayMessageOnOSD(Common::U32String::format(
\t\t\t\t"SPUZZ ENTER / mouseH %d / mouseV %d", oracleX, oracleY));
\t\t}
\t}
\n\tif (debugChannelSet(3, kDebugLingoExec))'''
    if call_anchor not in code:
        raise RuntimeError("Could not locate LC::call(name) implementation")
    code = code.replace(call_anchor, call_replacement, 1)
    lingo_code_cpp.write_text(code, encoding="utf-8")

# 3) Compact go-target diagnostic.
builtins = builtins_cpp.read_text(encoding="utf-8")
go_marker = "ORACLE_RUNES_GO_TARGET_DIAGNOSTIC"
if go_marker not in builtins:
    go_anchor = '''void LB::b_go(int nargs) {
\t// Builtin function for go as used by the Director bytecode engine.'''
    go_replacement = '''void LB::b_go(int nargs) {
\t// ORACLE_RUNES_GO_TARGET_DIAGNOSTIC
\tif (nargs == 1) {
\t\tDatum oracleTarget = g_lingo->peek(0);
\t\tif (oracleTarget.type == INT)
\t\t\tg_system->displayMessageOnOSD(Common::U32String::format(
\t\t\t\t"ORACLE GO -> frame %d", oracleTarget.asInt()));
\t}
\n\t// Builtin function for go as used by the Director bytecode engine.'''
    if go_anchor not in builtins:
        raise RuntimeError("Could not locate LB::b_go implementation")
    builtins = builtins.replace(go_anchor, go_replacement, 1)
    builtins_cpp.write_text(builtins, encoding="utf-8")

# 4) Oracle puzzle navigation fix.
# A..Z selector maps to frames 29..54. Runtime #35 proved setCurrentFrame()
# receives frame 29, but the normal Score cycle never visibly applies it.
# For this dedicated build, apply and render puzzle frames immediately.
funcs = lingo_funcs_cpp.read_text(encoding="utf-8")
nav_marker = "ORACLE_RUNES_PUZZLE_GOTO_FIX"
if nav_marker not in funcs:
    old_guard = '''\tif (score->_disableGoPlayUpdateStage) {
\t\twarning("Lingo::func_goto(): ignoring goto due to disableGoPlayUpdateStage flag");
\t\treturn;
\t}'''
    new_guard = '''\t// ORACLE_RUNES_PUZZLE_GOTO_FIX
\tbool oraclePuzzleGoto = (movie.type == VOID && frame.type == INT && frame.asInt() >= 29 && frame.asInt() <= 54);
\tif (score->_disableGoPlayUpdateStage && !oraclePuzzleGoto) {
\t\twarning("Lingo::func_goto(): ignoring goto due to disableGoPlayUpdateStage flag");
\t\treturn;
\t}'''
    if old_guard not in funcs:
        raise RuntimeError("Could not locate func_goto disableGoPlayUpdateStage guard")
    funcs = funcs.replace(old_guard, new_guard, 1)

    old_set = '''\t} else {
\t\tdebugC(3, kDebugLingoExec, "Lingo::func_goto(): going to frame %d", frame.asInt());
\t\tscore->setCurrentFrame(frame.asInt());
\t}'''
    new_set = '''\t} else {
\t\tdebugC(3, kDebugLingoExec, "Lingo::func_goto(): going to frame %d", frame.asInt());
\t\tscore->setCurrentFrame(frame.asInt());
\t\tif (oraclePuzzleGoto) {
\t\t\t// ORACLE_RUNES_IMMEDIATE_PUZZLE_FRAME_APPLY
\t\t\t// The normal D7 update-stage cycle can overwrite/defer this jump.
\t\t\t// Apply the queued frame now and force a redraw before returning to Lingo.
\t\t\tscore->updateCurrentFrame();
\t\t\tscore->updateSprites(kRenderForceUpdate, true);
\t\t\twindow->render();
\t\t\tg_system->displayMessageOnOSD(Common::U32String::format(
\t\t\t\t"ORACLE APPLIED PUZZLE FRAME %d", frame.asInt()));
\t\t}
\t}'''
    if old_set not in funcs:
        raise RuntimeError("Could not locate numeric func_goto setCurrentFrame block")
    funcs = funcs.replace(old_set, new_set, 1)
    lingo_funcs_cpp.write_text(funcs, encoding="utf-8")

# 5) Strong verification.
events_check = lingo_events_cpp.read_text(encoding="utf-8")
code_check = lingo_code_cpp.read_text(encoding="utf-8")
builtins_check = builtins_cpp.read_text(encoding="utf-8")
funcs_check = lingo_funcs_cpp.read_text(encoding="utf-8")
checks = {
    "primary handler": marker in events_check and 'executableCode = "SPUZZ()"' in events_check,
    "SPUZZ entry": call_marker in code_check and "SPUZZ ENTER" in code_check,
    "go target": go_marker in builtins_check and "ORACLE GO -> frame" in builtins_check,
    "puzzle goto": nav_marker in funcs_check and "oraclePuzzleGoto" in funcs_check,
    "immediate apply": "ORACLE_RUNES_IMMEDIATE_PUZZLE_FRAME_APPLY" in funcs_check and "updateCurrentFrame()" in funcs_check and "window->render()" in funcs_check,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise RuntimeError("Oracle navigation verification failed: " + ", ".join(failed))

print("ORACLE IMMEDIATE PUZZLE FRAME APPLY VERIFIED")
