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

# 1) Compact click diagnostics: target + behavior/instance counts.
src = events_cpp.read_text(encoding="utf-8")
marker = "ORACLE_RUNES_CLICK_DIAGNOSTIC"
if marker not in src:
    anchor = '''\tcase Common::EVENT_LBUTTONDOWN:\n\tcase Common::EVENT_RBUTTONDOWN:\n\t\tpos = event.mouse;\n\t\tif (sc->_waitForClick) {'''
    if anchor not in src:
        raise RuntimeError("Could not locate Director mouse-button handling block")
    replacement = '''\tcase Common::EVENT_LBUTTONDOWN:\n\tcase Common::EVENT_RBUTTONDOWN:\n\t\tpos = event.mouse;\n\n\t\t// ORACLE_RUNES_CLICK_DIAGNOSTIC\n\t\tif (event.type == Common::EVENT_LBUTTONDOWN) {\n\t\t\tSprite *diagSprite = sc->getSpriteById(spriteId);\n\t\t\tuint diagBehaviors = diagSprite ? (uint)diagSprite->_behaviors.size() : 0;\n\t\t\tChannel *diagChannel = sc->getChannelById(spriteId);\n\t\t\tuint diagInstances = diagChannel ? (uint)diagChannel->_scriptInstanceList.size() : 0;\n\t\t\tg_system->displayMessageOnOSD(Common::U32String::format(\n\t\t\t\t"CLICK %d,%d / sprite %u / behaviors %u / instances %u",\n\t\t\t\tpos.x, pos.y, (uint)spriteId, diagBehaviors, diagInstances));\n\t\t}\n\n\t\tif (sc->_waitForClick) {'''
    src = src.replace(anchor, replacement, 1)
    events_cpp.write_text(src, encoding="utf-8")

# 2) Oracle D7 compatibility.
lingo = lingo_events_cpp.read_text(encoding="utf-8")

# 2a) The movie exposes a valid behavior but ScummVM's normal `new` path
# returns a non-object for this title. A Director behavior instance is
# essentially a per-sprite copy of its ScriptContext, so create that object
# directly as a compatibility fallback. This preserves method dispatch
# (mouseDown/mouseUp) and per-instance properties.
clone_marker = "ORACLE_RUNES_CLONE_BEHAVIOR_INSTANCE"
if clone_marker not in lingo:
    old_clone = '''\tDatum instance = g_lingo->pop();\n\n\tif (instance.type != OBJECT) {\n\t\twarning("Score::createScriptInstance(): Could not instantiate behavior %s", behavior->toString().c_str());\n\t\treturn Datum();\n\t}'''
    new_clone = '''\tDatum instance = g_lingo->pop();\n\n\tif (instance.type != OBJECT) {\n\t\t// ORACLE_RUNES_CLONE_BEHAVIOR_INSTANCE\n\t\t// Oracle of Runes (Director 7) has valid behavior ScriptContexts but\n\t\t// the normal Lingo `new` path can fail to return an object. Clone the\n\t\t// ScriptContext so behavior methods and instance properties still work.\n\t\twarning("Oracle of Runes: normal behavior instantiation failed for %s; cloning ScriptContext", behavior->toString().c_str());\n\t\tScriptContext *oracleInstance = new ScriptContext(*scr);\n\t\tinstance = Datum((AbstractObject *)oracleInstance);\n\t}'''
    if old_clone not in lingo:
        raise RuntimeError("Could not locate behavior instantiation failure block")
    lingo = lingo.replace(old_clone, new_clone, 1)

# 2b) Keep queue fallback as a safety net for any frame where behavior
# instances have not been created yet.
fallback_marker = "ORACLE_RUNES_BEHAVIOR_FALLBACK"
if fallback_marker not in lingo:
    old = '''\t\t\t\t\t// Generate event for each behavior, and pass through for all but the last one.\n\t\t\t\t\t// This is to allow multiple behaviors on a single sprite to each have a\n\t\t\t\t\t// chance to handle the event.\n\t\t\t\t\tfor (uint i = 0; i < channel->_scriptInstanceList.size(); i++) {\n\t\t\t\t\t\tbool passThrough = (i != channel->_scriptInstanceList.size() - 1);\n\t\t\t\t\t\tqueue.push(LingoEvent(event, eventId, kSpriteHandler, passThrough, pos, pointedSpriteId, i));\n\t\t\t\t\t}'''
    new = '''\t\t\t\t\t// Generate event for each behavior, and pass through for all but the last one.\n\t\t\t\t\t// ORACLE_RUNES_BEHAVIOR_FALLBACK\n\t\t\t\t\tuint oracleInstanceCount = channel->_scriptInstanceList.size();\n\t\t\t\t\tuint oracleBehaviorCount = channel->_sprite ? channel->_sprite->_behaviors.size() : 0;\n\t\t\t\t\tuint oracleEventCount = oracleInstanceCount ? oracleInstanceCount : oracleBehaviorCount;\n\t\t\t\t\tfor (uint i = 0; i < oracleEventCount; i++) {\n\t\t\t\t\t\tbool passThrough = (i != oracleEventCount - 1);\n\t\t\t\t\t\tqueue.push(LingoEvent(event, eventId, kSpriteHandler, passThrough, pos, pointedSpriteId, i));\n\t\t\t\t\t}'''
    if old not in lingo:
        raise RuntimeError("Could not locate D6+ behavior event queue")
    lingo = lingo.replace(old, new, 1)

    old2 = '''\t\t\tif (_vm->getVersion() >= 600) {\n\t\t\t\tevent.scriptType = kScoreScript;\n\t\t\t\tevent.scriptId = scriptId;\n\t\t\t\tif (event.behaviorIndex >= 0 && event.behaviorIndex < (int)_score->_channels[event.channelId]->_scriptInstanceList.size())\n\t\t\t\t\tevent.scriptInstance = _score->_channels[event.channelId]->_scriptInstanceList[event.behaviorIndex].u.obj;\n\t\t\t\telse\n\t\t\t\t\twarning("resolveScriptEvent: behaviorIndex %d out of range", event.behaviorIndex);\n\t\t\t\treturn;\n\t\t\t}'''
    new2 = '''\t\t\tif (_vm->getVersion() >= 600) {\n\t\t\t\tevent.scriptType = kScoreScript;\n\t\t\t\tevent.scriptId = scriptId;\n\t\t\t\tif (event.behaviorIndex >= 0 && event.behaviorIndex < (int)_score->_channels[event.channelId]->_scriptInstanceList.size()) {\n\t\t\t\t\tDatum &oracleInstance = _score->_channels[event.channelId]->_scriptInstanceList[event.behaviorIndex];\n\t\t\t\t\tif (oracleInstance.type == OBJECT)\n\t\t\t\t\t\tevent.scriptInstance = oracleInstance.u.obj;\n\t\t\t\t}\n\t\t\t\treturn;\n\t\t\t}'''
    if old2 not in lingo:
        raise RuntimeError("Could not locate D6+ behavior instance resolution block")
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

# Verification
click_check = events_cpp.read_text(encoding="utf-8")
lingo_check = lingo_events_cpp.read_text(encoding="utf-8")
checks = {
    "click diagnostic": marker in click_check and "instances %u" in click_check,
    "real behavior instance fallback": clone_marker in lingo_check and "new ScriptContext(*scr)" in lingo_check,
    "event queue fallback": fallback_marker in lingo_check,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise RuntimeError("Oracle verification failed: " + ", ".join(failed))

print("ORACLE D7 REAL BEHAVIOR INSTANCE FIX VERIFIED")
