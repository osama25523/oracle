import sys
import re
from pathlib import Path

if len(sys.argv) != 2:
    print("Usage: python3 patch_diagnostics.py <scummvm-source-dir>")
    sys.exit(1)

root = Path(sys.argv[1]).resolve()
events_cpp = root / "engines" / "director" / "events.cpp"
lingo_events_cpp = root / "engines" / "director" / "lingo" / "lingo-events.cpp"
builtins_cpp = root / "engines" / "director" / "lingo" / "lingo-builtins.cpp"

for p in (events_cpp, lingo_events_cpp, builtins_cpp):
    if not p.exists():
        raise FileNotFoundError(str(p))

# 1) Compact click diagnostics.
src = events_cpp.read_text(encoding="utf-8")
marker = "ORACLE_RUNES_CLICK_DIAGNOSTIC"
if marker not in src:
    anchor = '''\tcase Common::EVENT_LBUTTONDOWN:\n\tcase Common::EVENT_RBUTTONDOWN:\n\t\tpos = event.mouse;\n\t\tif (sc->_waitForClick) {'''
    if anchor not in src:
        raise RuntimeError("Could not locate Director mouse-button handling block")
    replacement = '''\tcase Common::EVENT_LBUTTONDOWN:\n\tcase Common::EVENT_RBUTTONDOWN:\n\t\tpos = event.mouse;\n\n\t\t// ORACLE_RUNES_CLICK_DIAGNOSTIC\n\t\tif (event.type == Common::EVENT_LBUTTONDOWN) {\n\t\t\tSprite *diagSprite = sc->getSpriteById(spriteId);\n\t\t\tuint diagBehaviors = diagSprite ? (uint)diagSprite->_behaviors.size() : 0;\n\t\t\tChannel *diagChannel = sc->getChannelById(spriteId);\n\t\t\tuint diagInstances = diagChannel ? (uint)diagChannel->_scriptInstanceList.size() : 0;\n\t\t\tg_system->displayMessageOnOSD(Common::U32String::format(\n\t\t\t\t"CLICK %d,%d / sprite %u / behaviors %u / instances %u",\n\t\t\t\tpos.x, pos.y, (uint)spriteId, diagBehaviors, diagInstances));\n\t\t}\n\n\t\tif (sc->_waitForClick) {'''
    src = src.replace(anchor, replacement, 1)
    events_cpp.write_text(src, encoding="utf-8")

# 2) Oracle D7 behavior compatibility.
lingo = lingo_events_cpp.read_text(encoding="utf-8")

# 2a) Resolve behavior ScriptContext across common Director script types.
resolve_marker = "ORACLE_RUNES_RESOLVE_BEHAVIOR_SCRIPT"
if resolve_marker not in lingo:
    old_resolve = '''\t// Instantiate the behavior\n\tScriptContext *scr = _movie->getScriptContext(kScoreScript, behavior->memberID);\n\n\t// Some movies have behaviors with missing scripts\n\tif (scr == nullptr) {\n\t\tdebugC(7, kDebugLingoExec, "Score::createScriptInstance(): Missing script for behavior %s", behavior->toString().c_str());\n\t\treturn Datum();\n\t}'''
    new_resolve = '''\t// Instantiate the behavior\n\t// ORACLE_RUNES_RESOLVE_BEHAVIOR_SCRIPT\n\tScriptContext *scr = _movie->getScriptContext(kScoreScript, behavior->memberID);\n\tif (scr == nullptr)\n\t\tscr = _movie->getScriptContext(kCastScript, behavior->memberID);\n\tif (scr == nullptr)\n\t\tscr = _movie->getScriptContext(kMovieScript, behavior->memberID);\n\n\tif (scr == nullptr && behavior->memberID.member) {\n\t\tCastMemberID oracleDefaultId(behavior->memberID.member, DEFAULT_CAST_LIB);\n\t\tscr = _movie->getScriptContext(kScoreScript, oracleDefaultId);\n\t\tif (scr == nullptr)\n\t\t\tscr = _movie->getScriptContext(kCastScript, oracleDefaultId);\n\t\tif (scr == nullptr)\n\t\t\tscr = _movie->getScriptContext(kMovieScript, oracleDefaultId);\n\t}\n\n\tif (scr == nullptr) {\n\t\twarning("Oracle of Runes: could not resolve script for behavior %s", behavior->toString().c_str());\n\t\treturn Datum();\n\t}'''
    if old_resolve not in lingo:
        raise RuntimeError("Could not locate behavior ScriptContext resolution block")
    lingo = lingo.replace(old_resolve, new_resolve, 1)

# 2b) If normal `new` does not yield an object, clone the ScriptContext.
clone_marker = "ORACLE_RUNES_CLONE_BEHAVIOR_INSTANCE"
if clone_marker not in lingo:
    old_clone = '''\tDatum instance = g_lingo->pop();\n\n\tif (instance.type != OBJECT) {\n\t\twarning("Score::createScriptInstance(): Could not instantiate behavior %s", behavior->toString().c_str());\n\t\treturn Datum();\n\t}'''
    new_clone = '''\tDatum instance = g_lingo->pop();\n\n\tif (instance.type != OBJECT) {\n\t\t// ORACLE_RUNES_CLONE_BEHAVIOR_INSTANCE\n\t\twarning("Oracle of Runes: normal behavior instantiation failed for %s; cloning ScriptContext", behavior->toString().c_str());\n\t\tScriptContext *oracleInstance = new ScriptContext(*scr);\n\t\tinstance = Datum((AbstractObject *)oracleInstance);\n\t}'''
    if old_clone not in lingo:
        raise RuntimeError("Could not locate behavior instantiation failure block")
    lingo = lingo.replace(old_clone, new_clone, 1)

# 2c) Critical fix: if a D6+/D7 sprite has behaviors but no instances when an
# input event arrives, instantiate them lazily using ScummVM's own
# Score::createScriptInstance() before queuing mouseDown/mouseUp.
lazy_marker = "ORACLE_RUNES_LAZY_BEHAVIOR_INSTANTIATION"
old_queue = '''\t\t\t\t\t// Generate event for each behavior, and pass through for all but the last one.\n\t\t\t\t\t// This is to allow multiple behaviors on a single sprite to each have a\n\t\t\t\t\t// chance to handle the event.\n\t\t\t\t\tfor (uint i = 0; i < channel->_scriptInstanceList.size(); i++) {\n\t\t\t\t\t\tbool passThrough = (i != channel->_scriptInstanceList.size() - 1);\n\t\t\t\t\t\tqueue.push(LingoEvent(event, eventId, kSpriteHandler, passThrough, pos, pointedSpriteId, i));\n\t\t\t\t\t}'''
new_queue = '''\t\t\t\t\t// Generate event for each behavior, and pass through for all but the last one.\n\t\t\t\t\t// ORACLE_RUNES_LAZY_BEHAVIOR_INSTANTIATION\n\t\t\t\t\tif (channel->_scriptInstanceList.empty() && channel->_sprite && !channel->_sprite->_behaviors.empty()) {\n\t\t\t\t\t\tfor (uint oracleI = 0; oracleI < channel->_sprite->_behaviors.size(); ++oracleI) {\n\t\t\t\t\t\t\tDatum oracleInstance = _score->createScriptInstance(&channel->_sprite->_behaviors[oracleI]);\n\t\t\t\t\t\t\tif (oracleInstance.type == OBJECT)\n\t\t\t\t\t\t\t\tchannel->_scriptInstanceList.push_back(oracleInstance);\n\t\t\t\t\t\t}\n\t\t\t\t\t\tif ((event == kEventMouseDown || event == kEventMouseUp) && !channel->_scriptInstanceList.empty())\n\t\t\t\t\t\t\tg_system->displayMessageOnOSD(Common::U32String::format(\n\t\t\t\t\t\t\t\t"ORACLE: created %u behavior instance(s)", (uint)channel->_scriptInstanceList.size()));\n\t\t\t\t\t}\n\n\t\t\t\t\tfor (uint i = 0; i < channel->_scriptInstanceList.size(); i++) {\n\t\t\t\t\t\tbool passThrough = (i != channel->_scriptInstanceList.size() - 1);\n\t\t\t\t\t\tqueue.push(LingoEvent(event, eventId, kSpriteHandler, passThrough, pos, pointedSpriteId, i));\n\t\t\t\t\t}'''

if lazy_marker not in lingo:
    # Accept either pristine upstream or the previous Oracle queue fallback and replace it.
    previous_fallback = re.compile(
        r'\t\t\t\t\t// Generate event for each behavior, and pass through for all but the last one\.\n'
        r'(?:\t\t\t\t\t//.*\n)*'
        r'\t\t\t\t\t// ORACLE_RUNES_BEHAVIOR_FALLBACK\n'
        r'\t\t\t\t\tuint oracleInstanceCount = .*?\n'
        r'\t\t\t\t\t\}',
        re.DOTALL,
    )
    if old_queue in lingo:
        lingo = lingo.replace(old_queue, new_queue, 1)
    else:
        m = previous_fallback.search(lingo)
        if not m:
            raise RuntimeError("Could not locate D6+ behavior event queue")
        lingo = lingo[:m.start()] + new_queue + lingo[m.end():]

# 2d) Resolve queued event to the actual object instance.
# Replace prior Oracle resolution if present; otherwise patch upstream block.
old2 = '''\t\t\tif (_vm->getVersion() >= 600) {\n\t\t\t\tevent.scriptType = kScoreScript;\n\t\t\t\tevent.scriptId = scriptId;\n\t\t\t\tif (event.behaviorIndex >= 0 && event.behaviorIndex < (int)_score->_channels[event.channelId]->_scriptInstanceList.size())\n\t\t\t\t\tevent.scriptInstance = _score->_channels[event.channelId]->_scriptInstanceList[event.behaviorIndex].u.obj;\n\t\t\t\telse\n\t\t\t\t\twarning("resolveScriptEvent: behaviorIndex %d out of range", event.behaviorIndex);\n\t\t\t\treturn;\n\t\t\t}'''
new2 = '''\t\t\tif (_vm->getVersion() >= 600) {\n\t\t\t\tevent.scriptType = kScoreScript;\n\t\t\t\tevent.scriptId = scriptId;\n\t\t\t\tif (event.behaviorIndex >= 0 && event.behaviorIndex < (int)_score->_channels[event.channelId]->_scriptInstanceList.size()) {\n\t\t\t\t\tDatum &oracleInstance = _score->_channels[event.channelId]->_scriptInstanceList[event.behaviorIndex];\n\t\t\t\t\tif (oracleInstance.type == OBJECT)\n\t\t\t\t\t\tevent.scriptInstance = oracleInstance.u.obj;\n\t\t\t\t}\n\t\t\t\treturn;\n\t\t\t}'''
if old2 in lingo:
    lingo = lingo.replace(old2, new2, 1)

lingo_events_cpp.write_text(lingo, encoding="utf-8")

# 3) Keep Xtra/xtnd safe fallbacks.
builtins = builtins_cpp.read_text(encoding="utf-8")
xtra_pattern = re.compile(r'// ORACLE_RUNES_SAFE_XTRA\nvoid LB::b_orunesXtra\(int nargs\) \{.*?\n\}', re.DOTALL)
xtnd_pattern = re.compile(r'// ORACLE_RUNES_SAFE_XTND\nvoid LB::b_orunesXtnd\(int nargs\) \{.*?\n\}', re.DOTALL)

xtra_replacement = '''// ORACLE_RUNES_SAFE_XTRA
void LB::b_orunesXtra(int nargs) {
\tCommon::String requested = "<no-arg>";
\tif (nargs > 0) {
\t\tDatum d = g_lingo->pop();
\t\trequested = d.asString();
\t\tif (nargs > 1)
\t\t\tg_lingo->dropStack(nargs - 1);
\t}
\twarning("Oracle of Runes: xtra(%s) compatibility fallback used", requested.c_str());
\tg_lingo->push(Datum(0));
}'''

xtnd_replacement = '''// ORACLE_RUNES_SAFE_XTND
void LB::b_orunesXtnd(int nargs) {
\tCommon::String requested = "<no-arg>";
\tif (nargs > 0) {
\t\tDatum d = g_lingo->pop();
\t\trequested = d.asString();
\t\tif (nargs > 1)
\t\t\tg_lingo->dropStack(nargs - 1);
\t}
\twarning("Oracle of Runes: xtnd(%s) compatibility fallback used", requested.c_str());
\tg_lingo->push(Datum(0));
}'''

builtins, xtra_count = xtra_pattern.subn(lambda m: xtra_replacement, builtins, count=1)
builtins, xtnd_count = xtnd_pattern.subn(lambda m: xtnd_replacement, builtins, count=1)
if xtra_count != 1 or xtnd_count != 1:
    raise RuntimeError("Could not preserve Oracle Xtra fallbacks")
builtins_cpp.write_text(builtins, encoding="utf-8")

click_check = events_cpp.read_text(encoding="utf-8")
lingo_check = lingo_events_cpp.read_text(encoding="utf-8")
checks = {
    "click diagnostic": marker in click_check and "instances %u" in click_check,
    "script resolver": resolve_marker in lingo_check,
    "instance fallback": clone_marker in lingo_check,
    "lazy instantiation": lazy_marker in lingo_check and "createScriptInstance(&channel->_sprite->_behaviors" in lingo_check,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise RuntimeError("Oracle verification failed: " + ", ".join(failed))

print("ORACLE D7 LAZY BEHAVIOR INSTANTIATION FIX VERIFIED")
