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
stock_marker = "ORACLE_RUNES_STOCK_GOTO_BYPASS_GUARD"
always_marker = "ORACLE_RUNES_ALWAYS_QUEUE_PUZZLE_GOTO"
setup_marker = "ORACLE_RUNES_DEFER_SETUP_FRAME_4"

# patch_primary_handler.py runs immediately before this script on a fresh
# ScummVM checkout. It adds a temporary queue workaround around func_goto.
# Replace that workaround with a much smaller compatibility rule: Oracle's
# puzzle setup jumps are allowed through ScummVM's update-stage guard, then
# the rest of the ORIGINAL func_goto executes unchanged. This preserves the
# normal Director semantics: _skipFrameAdvance, Lingo freeze, setCurrentFrame,
# and killScriptInstances all happen in their stock order.
if stock_marker not in src:
    pattern = re.compile(
        r'\t// ORACLE_RUNES_SAFE_PUZZLE_GOTO_FIX\n'
        r'\tbool oraclePuzzleGoto = \(movie\.type == VOID && frame\.type == INT && frame\.asInt\(\) >= 29 && frame\.asInt\(\) <= 54\);\n'
        r'.*?'
        r'\tif \(score->_disableGoPlayUpdateStage\) \{\n'
        r'\t\twarning\("Lingo::func_goto\(\): ignoring goto due to disableGoPlayUpdateStage flag"\);\n'
        r'\t\treturn;\n'
        r'\t\}\n',
        re.DOTALL,
    )

    replacement = '''\t// ORACLE_RUNES_SAFE_PUZZLE_GOTO_FIX
\tbool oraclePuzzleGoto = (movie.type == VOID && frame.type == INT && frame.asInt() >= 29 && frame.asInt() <= 54);
\t// ORACLE_RUNES_DEFER_SETUP_FRAME_4
\tbool oracleSetupGoto4 = (movie.type == VOID && frame.type == INT && frame.asInt() == 4 &&
\t\tscore->getCurrentFrameNum() >= 29 && score->getCurrentFrameNum() <= 54);
\tbool oracleAllowedGuardedGoto = oraclePuzzleGoto || oracleSetupGoto4;

\t// ORACLE_RUNES_ALWAYS_QUEUE_PUZZLE_GOTO
\t// ORACLE_RUNES_STOCK_GOTO_BYPASS_GUARD
\tif (score->_disableGoPlayUpdateStage && !oracleAllowedGuardedGoto) {
\t\twarning("Lingo::func_goto(): ignoring goto due to disableGoPlayUpdateStage flag");
\t\treturn;
\t}

\tif (oracleAllowedGuardedGoto) {
\t\tg_system->displayMessageOnOSD(Common::U32String::format(
\t\t\t"ORACLE STOCK GOTO -> %d", frame.asInt()));
\t}
'''

    src, count = pattern.subn(replacement, src, count=1)
    if count != 1:
        raise RuntimeError("Could not locate Oracle temporary goto workaround block")

path.write_text(src, encoding="utf-8")

check = path.read_text(encoding="utf-8")
required = {
    "base marker": base_marker,
    "stock goto marker": stock_marker,
    "workflow compatibility marker": always_marker,
    "setup frame marker": setup_marker,
    "puzzle range": "frame.asInt() >= 29 && frame.asInt() <= 54",
    "setup source range": "score->getCurrentFrameNum() >= 29",
    "stock diagnostic": "ORACLE STOCK GOTO",
    "stock freeze": "_freezeState = true",
    "stock frame assignment": "score->setCurrentFrame(frame.asInt())",
    "stock instance cleanup": "score->killScriptInstances(score->getNextFrame())",
}
missing = [name for name, text in required.items() if text not in check]
if missing:
    raise RuntimeError("Oracle stock goto compatibility verification failed: " + ", ".join(missing))

if "ORACLE DIRECT PUZZLE" in check or "ORACLE DEFER GOTO 4" in check:
    raise RuntimeError("Old direct/deferred Oracle goto workaround is still present")

print("ORACLE STOCK DIRECTOR GOTO SEMANTICS VERIFIED")
