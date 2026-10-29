# -*- coding: utf-8 -*-
import re, json

txt = open("reference_report.html", encoding="utf-8").read()

def extract_var(name):
    m = re.search(r"var\s+" + name + r"\s*=\s*", txt)
    if not m:
        return None
    i = txt.index("{", m.start())
    depth = 0
    end = None
    for j in range(i, len(txt)):
        if txt[j] == "{":
            depth += 1
        elif txt[j] == "}":
            depth -= 1
            if depth == 0:
                end = j + 1
                break
    return txt[i:end]

for name in ["PH", "TERMS"]:
    chunk = extract_var(name)
    if chunk is None:
        print(f"=== {name}: NOT FOUND ===")
        continue
    print(f"=== {name} (len {len(chunk)}) ===")
    # Try to parse as JS object -> JSON-ish; just print a slice
    print(chunk[:2000])
    print("...\n")
