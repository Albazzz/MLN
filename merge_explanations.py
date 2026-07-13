# -*- coding: utf-8 -*-
import json
import glob
import sys

sys.stdout.reconfigure(encoding="utf-8")

qs = json.load(open("questions.json", encoding="utf-8"))
by_id = {q["id"]: q for q in qs}

paths = sorted(glob.glob("batches/out_*.json"))
print("merge files:", paths)

merged = 0
missing = []
bad = []

for path in paths:
    data = json.load(open(path, encoding="utf-8"))
    if not isinstance(data, list):
        print("skip non-list", path)
        continue
    for item in data:
        qid = item.get("id")
        exp = item.get("explanation")
        if qid not in by_id:
            missing.append(qid)
            continue
        if not exp or not exp.get("whyCorrect") or not isinstance(exp.get("whyWrong"), dict):
            bad.append(qid)
            continue
        # strip fluff markers
        exp["whyCorrect"] = str(exp["whyCorrect"]).strip()
        exp["whyWrong"] = {str(k): str(v).strip() for k, v in exp["whyWrong"].items()}
        by_id[qid]["explanation"] = exp
        # keep alternative explanations if we had them; optional re-generate lightly later
        merged += 1

# check coverage
no_exp = [q["id"] for q in qs if not q.get("explanation") or not q["explanation"].get("whyCorrect")]
print(f"merged={merged} no_exp={len(no_exp)} bad={len(bad)} missing_ids={missing[:10]}")

# sample
for i in [1, 2, 3, 4, 526]:
    q = by_id[i]
    e = q["explanation"]
    print("---", i)
    print(e["whyCorrect"][:200])
    wk = list(e.get("whyWrong", {}).items())
    if wk:
        print(wk[0][0], ":", wk[0][1][:160])

with open("questions.json", "w", encoding="utf-8") as f:
    json.dump(qs, f, ensure_ascii=False, indent=2)

with open("questions.js", "w", encoding="utf-8") as f:
    f.write("// 526 questions + high-quality explanations\n")
    f.write("window.QUIZ_QUESTIONS = ")
    json.dump(qs, f, ensure_ascii=False)
    f.write(";\n")

print("wrote questions.json/js")
