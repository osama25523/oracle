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
\t// Oracle's SPUZZ handler must finish normally.  If we take ScummVM's
\t// stock goto path here it freezes the event script before the next Score
\t// cycle and the selector remains on screen.  Queue A..Z unconditionally;
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
    path.write_text(src, encoding="utf-8")

check = path.read_text(encoding="utf-8")
if marker not in check or "ORACLE QUEUE PUZZLE FRAME" not in check:
    raise RuntimeError("Oracle always-queue patch verification failed")

print("ORACLE ALWAYS-QUEUE PUZZLE GOTO VERIFIED")
