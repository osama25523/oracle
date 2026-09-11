# ============================================================
# 4) Fix xtra() when requested Xtra does not exist
# ============================================================

builtins_cpp = (
    root / "engines" / "director" / "lingo" / "lingo-builtins.cpp"
)

cpp = builtins_cpp.read_text(encoding="utf-8")

old_xtra = '''\tg_lingo->lingoError("Xtra not found: %s", d.asString().c_str());
}'''

new_xtra = '''\t// ORACLE_RUNES_XTRA_FALLBACK
\twarning("Oracle of Runes: Xtra not found: %s - returning 0", d.asString().c_str());
\tg_lingo->push(Datum(0));
}'''

if "ORACLE_RUNES_XTRA_FALLBACK" not in cpp:
    if old_xtra not in cpp:
        raise RuntimeError("Could not find b_xtra fallback code")

    cpp = cpp.replace(old_xtra, new_xtra, 1)
    builtins_cpp.write_text(cpp, encoding="utf-8")

    print("Patched xtra() fallback.")
else:
    print("xtra() fallback already patched.")
