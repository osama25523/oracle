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
direct_marker = "ORACLE_RUNES_DIRECT_PUZZLE_JUMP"
setup_marker = "ORACLE_RUNES_DEFER_SETUP_FRAME_4"

# SPUZZ already resolves A..Z to frames 29..54 correctly. The bug is not the
# target number: freezing/deferring that handler leaves ScummVM's Director
# state stuck around the selector and the same goto is re-entered. For the
# selector jump, reproduce the useful parts of Director's goto immediately:
# mark a non-consecutive jump, set _nextFrame, kill old behavior instances,
# but deliberately DO NOT freeze the SPUZZ state. Score::step() will see the
# nonzero _nextFrame on the next cycle and perform the normal frame lifecycle.
if direct_marker not in src:
    old = '''\t// ORACLE_RUNES_SAFE_PUZZLE_GOTO_FIX
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
    new = '''\t// ORACLE_RUNES_SAFE_PUZZLE_GOTO_FIX
\tbool oraclePuzzleGoto = (movie.type == VOID && frame.type == INT && frame.asInt() >= 29 && frame.asInt() <= 54);
\t// ORACLE_RUNES_ALWAYS_QUEUE_PUZZLE_GOTO
\t// ORACLE_RUNES_DIRECT_PUZZLE_JUMP
\tif (oraclePuzzleGoto) {
\t\tstage->_skipFrameAdvance = true;
\t\tscore->setCurrentFrame(frame.asInt());
\t\tscore->killScriptInstances(score->getNextFrame());
\t\tg_system->displayMessageOnOSD(Common::U32String::format(
\t\t\t"ORACLE DIRECT PUZZLE -> %d", frame.asInt()));
\t\treturn;
\t}
\tif (score->_disableGoPlayUpdateStage) {'''
    if old not in src:
        raise RuntimeError("Could not locate Oracle queued puzzle goto block")
    src = src.replace(old, new, 1)

# Frame 29..54 is a per-puzzle setup frame. Its frame script can legitimately
# request `go 4` while ScummVM's prepareFrame guard is active. That is a
# different situation: keep only this guarded go-4 deferred to the next safe
# Score cycle, and do not freeze the setup script either.
if setup_marker not in src:
    old_guard = '''\tif (score->_disableGoPlayUpdateStage) {
\t\twarning("Lingo::func_goto(): ignoring goto due to disableGoPlayUpdateStage flag");
\t\treturn;
\t}'''
    new_guard = '''\t// ORACLE_RUNES_DEFER_SETUP_FRAME_4
\tif (score->_disableGoPlayUpdateStage && movie.type == VOID && frame.type == INT && frame.asInt() == 4) {
\t\tstage->_skipFrameAdvance = true;
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
else:
    # #44 already inserted the setup block with freeze semantics; remove only
    # that freeze because it can strand the frame script just like SPUZZ.
    frozen_setup = '''\t// ORACLE_RUNES_DEFER_SETUP_FRAME_4
\tif (score->_disableGoPlayUpdateStage && movie.type == VOID && frame.type == INT && frame.asInt() == 4) {
\t\tstage->_skipFrameAdvance = true;
\t\tif (!_playDone)
\t\t\t_freezeState = true;
\t\tscore->oracleQueuePuzzleFrame(4);
\t\tg_system->displayMessageOnOSD(Common::U32String("ORACLE DEFER GOTO 4"));
\t\treturn;
\t}'''
    nonfrozen_setup = '''\t// ORACLE_RUNES_DEFER_SETUP_FRAME_4
\tif (score->_disableGoPlayUpdateStage && movie.type == VOID && frame.type == INT && frame.asInt() == 4) {
\t\tstage->_skipFrameAdvance = true;
\t\tscore->oracleQueuePuzzleFrame(4);
\t\tg_system->displayMessageOnOSD(Common::U32String("ORACLE DEFER GOTO 4"));
\t\treturn;
\t}'''
    if frozen_setup in src:
        src = src.replace(frozen_setup, nonfrozen_setup, 1)

path.write_text(src, encoding="utf-8")

check = path.read_text(encoding="utf-8")
if direct_marker not in check or "ORACLE DIRECT PUZZLE" not in check:
    raise RuntimeError("Oracle direct puzzle jump verification failed")
if "score->setCurrentFrame(frame.asInt())" not in check:
    raise RuntimeError("Oracle puzzle target is not applied directly")
if setup_marker not in check or "ORACLE DEFER GOTO 4" not in check:
    raise RuntimeError("Oracle setup frame 4 queue verification failed")

print("ORACLE DIRECT PUZZLE JUMP + NONFROZEN SETUP GOTO VERIFIED")
