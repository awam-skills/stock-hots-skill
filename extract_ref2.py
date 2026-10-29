# -*- coding: utf-8 -*-
import re

txt = open("reference_report.html", encoding="utf-8").read()

def extract_var(name):
    # match "var NAME=" or "const NAME=" or "var NAME ="
    m = re.search(r"(?:var|const|let)\s+" + re.escape(name) + r"\s*=\s*", txt)
    if not m:
        return None
    # find first { or [ after '='
    eq = txt.index("=", m.start())
    # locate first brace/paren
    i = eq + 1
    while i < len(txt) and txt[i] in " =\r\n\t":
        i += 1
    opener = txt[i]
    if opener not in "{[":
        return txt[i:i+300]
    close = "}" if opener == "{" else "]"
    depth = 0
    end = None
    for j in range(i, len(txt)):
        if txt[j] == opener:
            depth += 1
        elif txt[j] == close:
            depth -= 1
            if depth == 0:
                end = j + 1
                break
    return txt[i:end]

for name in ["reps", "terms", "I18N", "k", "t"]:
    chunk = extract_var(name)
    if chunk is None:
        print(f"=== {name}: NOT FOUND ===")
        continue
    print(f"=== {name} (len {len(chunk)}) ===")
    print(chunk[:1800])
    print("...\n")
