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
\t// Oracle's SPUZZ handler must finish normally. If we take ScummVM's
\t// stock goto path here it freezes the event script before the next Score
\t// cycle and the selector remains on screen. Queue A..Z unconditionally;
\t// Score::update() applies the pending frame at the start of the ordinary
\t// Director lifecycle (kill scripts -> load frame -> prepare/render/enter).
\tif (oraclePuzzleGoto) {
\t\tscore->oracleQueuePuzzleFrame(frame.asInt());
\t\tg_system->displayMessageOnOSD(Common::U32String::format(
\t\t\t"ORACLE QUEUE PUZZLE FRAME %d", frame.asInt()));
\t\treturn;
\t}
\tif (score->_disableGoPlayUpdateStage) {'''
    if old not in src:
        raise RuntimeError("Could not locate Oracle safe puzzle goto block")
    src = src.replace(old, new, 1)

# Frame 29..54 is Oracle's per-puzzle setup frame. During that setup the
# original Director movie legitimately issues `go 4` to enter the common
# gameplay board. ScummVM normally ignores goto while prepareFrame has its
# update-stage guard enabled, which leaves the setup frame half-rendered.
# Defer exactly that observed setup jump through the same safe Score queue.
if setup_marker not in src:
    old_guard = '''\tif (score->_disableGoPlayUpdateStage) {
\t\twarning("Lingo::func_goto(): ignoring goto due to disableGoPlayUpdateStage flag");
\t\treturn;
\t}'''
    new_guard = '''\t// ORACLE_RUNES_DEFER_SETUP_FRAME_4
\tif (score->_disableGoPlayUpdateStage && movie.type == VOID && frame.type == INT && frame.asInt() == 4) {
\t\tscore->oracleQueuePuzzleFrame(4);
\t\tg_system->displayMessageOnOSD(Common::U32String("ORACLE DEFER SETUP FRAME 4"));
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
if marker not in check or "ORACLE QUEUE PUZZLE FRAME" not in check:
    raise RuntimeError("Oracle always-queue patch verification failed")
if setup_marker not in check or "ORACLE DEFER SETUP FRAME 4" not in check:
    raise RuntimeError("Oracle setup frame 4 queue verification failed")

print("ORACLE ALWAYS-QUEUE PUZZLE GOTO + SETUP FRAME 4 VERIFIED")
