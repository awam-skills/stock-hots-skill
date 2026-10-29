# -*- coding: utf-8 -*-
import re

txt = open("reference_report.html", encoding="utf-8").read()
# Remove script/style
body = re.sub(r"<script[\s\S]*?</script>", " ", txt)
body = re.sub(r"<style[\s\S]*?</style>", " ", body)
# Keep newlines for block-level tags
body = re.sub(r"<(div|tr|li|p|br|/div|/tr|/li|/p)[^>]*>", "\n", body, flags=re.I)
text = re.sub(r"<[^>]+>", " ", body)
text = re.sub(r"&nbsp;", " ", text)
text = re.sub(r"[ \t]+", " ", text)
text = re.sub(r"\n\s*\n+", "\n", text)
open("reference_text.txt", "w", encoding="utf-8").write(text)
print("total text chars:", len(text))
# Print lines containing 行业/领涨/板块 or board-like percentages
lines = [l.strip() for l in text.split("\n") if l.strip()]
print("non-empty lines:", len(lines))
# find industry section
idx = next((i for i,l in enumerate(lines) if "行业轮动" in l or "行业板块" in l), None)
print("industry idx:", idx)
for l in lines[max(0,idx-3): idx+60]:
    print(l)
