import sys
from pathlib import Path

if len(sys.argv) != 2:
    print("Usage: python3 patch_puzzle_queue_always.py <scummvm-source-dir>")
    sys.exit(1)

root = Path(sys.argv[1]).resolve()
path = root / "engines" / "director" / "lingo" / "lingo-funcs.cpp"
if not path.exists():
    raise FileNotFoundError(str(path))

src = path.read_text(encoding="utf-8")
marker = "ORACLE_RUNES_ALWAYS_QUEUE_PUZZLE_GOTO"
semantics_marker = "ORACLE_RUNES_PRESERVE_GOTO_SEMANTICS"
setup_marker = "ORACLE_RUNES_DEFER_SETUP_FRAME_4"
if marker not in src:
    old = '''\t// ORACLE_RUNES_SAFE_PUZZLE_GOTO_FIX
\tbool oraclePuzzleGoto = (movie.type == VOID && frame.type == INT && frame.asInt() >= 29 && frame.asInt() <= 54);
\tif (score->_disableGoPlayUpdateStage && oraclePuzzleGoto) {
\t\tscore->oracleQueuePuzzleFrame(frame.asInt());
\t\tg_system->displayMessageOnOSD(Common::U32String::format(
\t\t\t"ORACLE DEFER PUZZLE FRAME %d", frame.asInt()));
\t\treturn;
\t}
\tif (score->_disableGoPlayUpdateStage) {'''
    new = '''\t// ORACLE_RUNES_SAFE_PUZZLE_GOTO_FIX
\tbool oraclePuzzleGoto = (movie.type == VOID && frame.type == INT && frame.asInt() >= 29 && frame.asInt() <= 54);
\t// ORACLE_RUNES_ALWAYS_QUEUE_PUZZLE_GOTO
\t// ORACLE_RUNES_PRESERVE_GOTO_SEMANTICS
\t// Keep Director's normal `go` semantics while deferring only the actual
\t// frame assignment until Score::update(). Stock func_goto sets both of
\t// these before changing _nextFrame: it suppresses exitFrame on the old
\t// frame and freezes the current Lingo state until the destination frame
\t// has entered. Omitting them made Oracle re-enter the selector/exitFrame
\t// path and repeatedly queue frame 29, which produced the visible flicker.
\tif (oraclePuzzleGoto) {
\t\tstage->_skipFrameAdvance = true;
\t\tif (!_playDone)
\t\t\t_freezeState = true;
\t\tscore->oracleQueuePuzzleFrame(frame.asInt());
\t\tg_system->displayMessageOnOSD(Common::U32String::format(
\t\t\t"ORACLE QUEUE GOTO %d", frame.asInt()));
\t\treturn;
\t}
\tif (score->_disableGoPlayUpdateStage) {'''
    if old not in src:
        raise RuntimeError("Could not locate Oracle safe puzzle goto block")
    src = src.replace(old, new, 1)

# Frame 29..54 is Oracle's per-puzzle setup frame. During that setup the
# original Director movie can issue `go 4` to enter the common gameplay
# board. ScummVM normally ignores goto while prepareFrame has its update-stage
# guard enabled. Defer exactly frame 4, but preserve the same skip/freeze
# semantics as an ordinary Director goto so the setup script resumes only
# after frame 4 has entered.
if setup_marker not in src:
    old_guard = '''\tif (score->_disableGoPlayUpdateStage) {
\t\twarning("Lingo::func_goto(): ignoring goto due to disableGoPlayUpdateStage flag");
\t\treturn;
\t}'''
    new_guard = '''\t// ORACLE_RUNES_DEFER_SETUP_FRAME_4
\tif (score->_disableGoPlayUpdateStage && movie.type == VOID && frame.type == INT && frame.asInt() == 4) {
\t\tstage->_skipFrameAdvance = true;
\t\tif (!_playDone)
\t\t\t_freezeState = true;
\t\tscore->oracleQueuePuzzleFrame(4);
\t\tg_system->displayMessageOnOSD(Common::U32String("ORACLE DEFER GOTO 4"));
\t\treturn;
\t}
\tif (score->_disableGoPlayUpdateStage) {
\t\twarning("Lingo::func_goto(): ignoring goto due to disableGoPlayUpdateStage flag");
\t\treturn;
\t}'''
    if old_guard not in src:
        raise RuntimeError("Could not locate guarded goto block for Oracle setup frame 4")
    src = src.replace(old_guard, new_guard, 1)

path.write_text(src, encoding="utf-8")

check = path.read_text(encoding="utf-8")
if marker not in check or semantics_marker not in check or "ORACLE QUEUE GOTO" not in check:
    raise RuntimeError("Oracle goto-semantics queue patch verification failed")
if setup_marker not in check or "ORACLE DEFER GOTO 4" not in check:
    raise RuntimeError("Oracle setup frame 4 queue verification failed")
if "stage->_skipFrameAdvance = true" not in check or "_freezeState = true" not in check:
    raise RuntimeError("Oracle goto semantics were not preserved")

print("ORACLE QUEUED GOTO WITH DIRECTOR SKIP/FREEZE SEMANTICS VERIFIED")
