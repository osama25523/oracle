import re
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
base_marker = "ORACLE_RUNES_SAFE_PUZZLE_GOTO_FIX"
always_marker = "ORACLE_RUNES_ALWAYS_QUEUE_PUZZLE_GOTO"
direct_marker = "ORACLE_RUNES_DIRECT_PUZZLE_JUMP"
setup_marker = "ORACLE_RUNES_DEFER_SETUP_FRAME_4"

# patch_primary_handler.py runs immediately before this script on a fresh
# ScummVM checkout. It inserts ORACLE_RUNES_SAFE_PUZZLE_GOTO_FIX. Replace that
# entire temporary guarded block in one pass instead of depending on the exact
# text produced by an older build (#44).
if direct_marker not in src:
    pattern = re.compile(
        r'\t// ORACLE_RUNES_SAFE_PUZZLE_GOTO_FIX\n'
        r'\tbool oraclePuzzleGoto = \(movie\.type == VOID && frame\.type == INT && frame\.asInt\(\) >= 29 && frame\.asInt\(\) <= 54\);\n'
        r'.*?'
        r'\tif \(score->_disableGoPlayUpdateStage\) \{',
        re.DOTALL,
    )

    replacement = '''\t// ORACLE_RUNES_SAFE_PUZZLE_GOTO_FIX
\tbool oraclePuzzleGoto = (movie.type == VOID && frame.type == INT && frame.asInt() >= 29 && frame.asInt() <= 54);

\t// ORACLE_RUNES_ALWAYS_QUEUE_PUZZLE_GOTO
\t// ORACLE_RUNES_DIRECT_PUZZLE_JUMP
\t// SPUZZ already resolves A..Z to frames 29..54 correctly. Apply that
\t// jump using stock Director goto mechanics except for freezing SPUZZ.
\t// Freezing the selector handler caused it to re-enter after the frame
\t// change, repeatedly issuing go 29 and producing the visible flicker.
\tif (oraclePuzzleGoto) {
\t\tstage->_skipFrameAdvance = true;
\t\tscore->setCurrentFrame(frame.asInt());
\t\tscore->killScriptInstances(score->getNextFrame());
\t\tg_system->displayMessageOnOSD(Common::U32String::format(
\t\t\t"ORACLE DIRECT PUZZLE -> %d", frame.asInt()));
\t\treturn;
\t}

\t// ORACLE_RUNES_DEFER_SETUP_FRAME_4
\t// Puzzle setup frames can issue go 4 while prepareFrame has the normal
\t// ScummVM update-stage guard enabled. Preserve that request for the next
\t// safe Score update, but do not freeze the setup script.
\tif (score->_disableGoPlayUpdateStage && movie.type == VOID && frame.type == INT && frame.asInt() == 4) {
\t\tstage->_skipFrameAdvance = true;
\t\tscore->oracleQueuePuzzleFrame(4);
\t\tg_system->displayMessageOnOSD(Common::U32String("ORACLE DEFER GOTO 4"));
\t\treturn;
\t}

\tif (score->_disableGoPlayUpdateStage) {'''

    src, count = pattern.subn(replacement, src, count=1)
    if count != 1:
        raise RuntimeError("Could not locate fresh Oracle safe puzzle goto block")

path.write_text(src, encoding="utf-8")

check = path.read_text(encoding="utf-8")
required = {
    "base marker": base_marker,
    "always marker": always_marker,
    "direct jump marker": direct_marker,
    "setup frame marker": setup_marker,
    "direct target": "score->setCurrentFrame(frame.asInt())",
    "kill old instances": "score->killScriptInstances(score->getNextFrame())",
    "setup queue": "score->oracleQueuePuzzleFrame(4)",
    "direct diagnostic": "ORACLE DIRECT PUZZLE",
    "setup diagnostic": "ORACLE DEFER GOTO 4",
}
missing = [name for name, text in required.items() if text not in check]
if missing:
    raise RuntimeError("Oracle direct puzzle patch verification failed: " + ", ".join(missing))

print("ORACLE DIRECT PUZZLE JUMP + NONFROZEN SETUP GOTO VERIFIED")
