import re

cpp = builtins_cpp.read_text(encoding="utf-8")

new_b_xtra = r'''void LB::b_xtra(int nargs) {
	Datum d = g_lingo->pop();

	if (d.type == INT) {
		int i = d.asInt() - 1;

		if (i >= 0 && (uint)i < g_lingo->_openXtraObjects.size()) {
			Datum var = g_lingo->_openXtraObjects[i];
			g_lingo->push(var);
			return;
		}
	} else {
		Common::String name = d.asString();

		for (uint i = 0; i < g_lingo->_openXtras.size(); i++) {
			if (name.equalsIgnoreCase(g_lingo->_openXtras[i])) {
				Datum var = g_lingo->_openXtraObjects[i];
				g_lingo->push(var);
				return;
			}
		}
	}

	// ORACLE_RUNES_XTRA_FALLBACK
	warning("Oracle of Runes: unsupported Xtra '%s', returning 0",
		d.asString().c_str());

	g_lingo->push(Datum(0));
}
'''

pattern = r'void LB::b_xtra\(int nargs\) \{.*?\n\}'

cpp, count = re.subn(
    pattern,
    new_b_xtra,
    cpp,
    count=1,
    flags=re.DOTALL
)

if count != 1:
    raise RuntimeError("Could not replace LB::b_xtra()")

builtins_cpp.write_text(cpp, encoding="utf-8")

print("b_xtra() fully replaced with Oracle fallback.")
