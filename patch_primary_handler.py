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
score_h = root / "engines" / "director" / "score.h"
score_cpp = root / "engines" / "director" / "score.cpp"

for p in (lingo_events_cpp, lingo_code_cpp, builtins_cpp, lingo_funcs_cpp, score_h, score_cpp):
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

\t// ORACLE_RUNES_PRIMARY_HANDLER_NAME_FIX
\tCommon::String executableCode = code;
\tif (event == kEventMouseDown && code.equalsIgnoreCase("spuzz"))
\t\texecutableCode = "SPUZZ()";

\tmainArchive->replaceCode(executableCode, kEventScript, event);
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

\tif (debugChannelSet(3, kDebugLingoExec))'''
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

\t// Builtin function for go as used by the Director bytecode engine.'''
    if go_anchor not in builtins:
        raise RuntimeError("Could not locate LB::b_go implementation")
    builtins = builtins.replace(go_anchor, go_replacement, 1)
    builtins_cpp.write_text(builtins, encoding="utf-8")

# 4) Add a legal public Score helper. updateCurrentFrame() itself is private,
# so the helper lives inside Score and may call it safely.
hdr = score_h.read_text(encoding="utf-8")
helper_decl_marker = "ORACLE_RUNES_IMMEDIATE_FRAME_HELPER_DECL"
if helper_decl_marker not in hdr:
    anchor = '''\tDatum createScriptInstance(BehaviorElement *behavior);

private:'''
    repl = '''\tDatum createScriptInstance(BehaviorElement *behavior);

\t// ORACLE_RUNES_IMMEDIATE_FRAME_HELPER_DECL
\tvoid oracleApplyPuzzleFrame(uint16 frameId);

private:'''
    if anchor not in hdr:
        raise RuntimeError("Could not locate Score public/private boundary")
    hdr = hdr.replace(anchor, repl, 1)
    score_h.write_text(hdr, encoding="utf-8")

score_src = score_cpp.read_text(encoding="utf-8")
helper_impl_marker = "ORACLE_RUNES_IMMEDIATE_FRAME_HELPER_IMPL"
if helper_impl_marker not in score_src:
    anchor = '''void Score::setCurrentFrame(uint16 frameId) {
\t_nextFrame = frameId;
}'''
    repl = '''void Score::setCurrentFrame(uint16 frameId) {
\t_nextFrame = frameId;
}

// ORACLE_RUNES_IMMEDIATE_FRAME_HELPER_IMPL
void Score::oracleApplyPuzzleFrame(uint16 frameId) {
\tsetCurrentFrame(frameId);
\tupdateCurrentFrame();
\tupdateSprites(kRenderForceUpdate, true);
\tif (_window)
\t\t_window->render();
}'''
    if anchor not in score_src:
        raise RuntimeError("Could not locate Score::setCurrentFrame")
    score_src = score_src.replace(anchor, repl, 1)
    score_cpp.write_text(score_src, encoding="utf-8")

# 5) Oracle puzzle navigation fix: A..Z maps to score frames 29..54.
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
\t\tif (oraclePuzzleGoto) {
\t\t\t// ORACLE_RUNES_IMMEDIATE_PUZZLE_FRAME_APPLY
\t\t\tscore->oracleApplyPuzzleFrame(frame.asInt());
\t\t\tg_system->displayMessageOnOSD(Common::U32String::format(
\t\t\t\t"ORACLE APPLIED PUZZLE FRAME %d", frame.asInt()));
\t\t} else {
\t\t\tscore->setCurrentFrame(frame.asInt());
\t\t}
\t}'''
    if old_set not in funcs:
        raise RuntimeError("Could not locate numeric func_goto setCurrentFrame block")
    funcs = funcs.replace(old_set, new_set, 1)
    lingo_funcs_cpp.write_text(funcs, encoding="utf-8")

# 6) Strong verification.
events_check = lingo_events_cpp.read_text(encoding="utf-8")
code_check = lingo_code_cpp.read_text(encoding="utf-8")
builtins_check = builtins_cpp.read_text(encoding="utf-8")
funcs_check = lingo_funcs_cpp.read_text(encoding="utf-8")
hdr_check = score_h.read_text(encoding="utf-8")
score_check = score_cpp.read_text(encoding="utf-8")
checks = {
    "primary handler": marker in events_check and 'executableCode = "SPUZZ()"' in events_check,
    "SPUZZ entry": call_marker in code_check and "SPUZZ ENTER" in code_check,
    "go target": go_marker in builtins_check and "ORACLE GO -> frame" in builtins_check,
    "puzzle goto": nav_marker in funcs_check and "oraclePuzzleGoto" in funcs_check,
    "public helper declaration": helper_decl_marker in hdr_check and "oracleApplyPuzzleFrame" in hdr_check,
    "helper implementation": helper_impl_marker in score_check and "updateCurrentFrame()" in score_check,
    "immediate apply": "ORACLE_RUNES_IMMEDIATE_PUZZLE_FRAME_APPLY" in funcs_check and "oracleApplyPuzzleFrame" in funcs_check,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise RuntimeError("Oracle navigation verification failed: " + ", ".join(failed))

print("ORACLE IMMEDIATE PUZZLE FRAME BUILD FIX VERIFIED")
