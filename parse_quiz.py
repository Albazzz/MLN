# -*- coding: utf-8 -*-
"""
Parse data.docx → questions.json / questions.js
Supports A–E options, multi-answers (ABC, BDE), answers with notes: "A (…)"
Attaches "Kiểu hỏi khác" alternatives; promotes full alt MCQs into bank.
"""
import re
import json
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

for path in ("data_extracted.txt", "data.docx"):
    try:
        raw = open(path, "rb").read().decode("utf-8")
        src = path
        break
    except Exception:
        raw = None
else:
    raise SystemExit("No data file")

raw = raw.replace("\r\n", "\n").replace("\r", "\n")
raw = re.sub(r"[ \t]*\(NHUNG HOÀNG\)", "", raw)
raw = re.sub(r"\(\d{3}-\d{3}-\d{4}\)", "", raw)

lines = [ln.strip() for ln in raw.split("\n")]
n = len(lines)

# A–E options
opt_re = re.compile(r"^([A-E])\s*[\.\)\:]\s*(.*)$", re.I)
# pure answer letters (single or multi)
ans_pure = re.compile(r"^([A-E]{1,5})$", re.I)
# answer with note: A (....) or ABC (....)
ans_note = re.compile(r"^([A-E]{1,5})\s*[\(（].+", re.I)
kieu_re = re.compile(r"^\(?\s*Kiểu hỏi khác\s*[:：]?\s*(.*)$", re.I)
tuong_tu_re = re.compile(r"^\(?\s*Kiểu hỏi tương tự\s*[:：]?\s*(.*)$", re.I)


def is_empty(s):
    return not s


def skip_empty(i):
    while i < n and is_empty(lines[i]):
        i += 1
    return i


def norm(s):
    s = re.sub(r"\s+", " ", (s or "")).strip().lower()
    return s.strip(" .;:)?！？")


def clean_text(s):
    s = re.sub(r"\s+", " ", (s or "")).strip()
    while s.endswith(")") and s.count("(") < s.count(")"):
        s = s[:-1].strip()
    return s


def is_answer_line(s):
    if not s:
        return False
    return bool(ans_pure.match(s) or ans_note.match(s))


def parse_answer_value(s):
    """Return uppercase letter string e.g. 'A' or 'BDE'."""
    m = ans_pure.match(s)
    if m:
        return m.group(1).upper()
    m = ans_note.match(s)
    if m:
        return m.group(1).upper()
    return None


def look_like_new_question(s):
    if is_empty(s):
        return False
    if opt_re.match(s) or is_answer_line(s) or kieu_re.match(s) or tuong_tu_re.match(s):
        return False
    if s in (")", "("):
        return False
    return len(s) >= 8


def is_option_continuation(s):
    if is_empty(s):
        return False
    if opt_re.match(s) or is_answer_line(s) or kieu_re.match(s) or tuong_tu_re.match(s):
        return False
    # Mid-sentence wrap (starts lowercase / conjunction) = option continuation
    if s[:1].islower() or s.startswith(("cũng", "và ", "hoặc ", "hay ", "của ", "trong ", "với ")):
        return True
    if look_like_new_question(s):
        return False
    return len(s) < 120

def parse_options(i):
    options = {}
    i = skip_empty(i)
    while i < n:
        m = opt_re.match(lines[i])
        if not m:
            break
        letter = m.group(1).upper()
        body = [m.group(2).strip()]
        i += 1
        while i < n:
            if is_empty(lines[i]):
                j = skip_empty(i)
                if j >= n:
                    i = j
                    break
                if opt_re.match(lines[j]) or is_answer_line(lines[j]) or kieu_re.match(lines[j]) or tuong_tu_re.match(lines[j]):
                    i = j
                    break
                if not is_option_continuation(lines[j]):
                    i = j
                    break
                body.append(lines[j])
                i = j + 1
                continue
            if opt_re.match(lines[i]) or is_answer_line(lines[i]) or kieu_re.match(lines[i]) or tuong_tu_re.match(lines[i]):
                break
            if not is_option_continuation(lines[i]):
                break
            body.append(lines[i])
            i += 1
        options[letter] = clean_text(" ".join(x for x in body if x))
    return options, i


def parse_answer(i):
    i0 = skip_empty(i)
    if i0 < n and is_answer_line(lines[i0]):
        return parse_answer_value(lines[i0]), i0 + 1
    return None, i


def infer_alt_answer(question, options, parent=None):
    ql = (question or "").lower()
    if options and parent:
        p_ans = parent.get("answer")
        p_opts = parent.get("options") or {}
        p_text = p_opts.get(p_ans, "")
        if p_text:
            np = norm(p_text)
            for L, t in options.items():
                if norm(t) == np or np in norm(t) or norm(t) in np:
                    return L, t, "parent_text_match"
        if p_opts and set(norm(t) for t in options.values()) == set(norm(t) for t in p_opts.values()):
            inv = {norm(t): L for L, t in options.items()}
            if p_ans in p_opts and norm(p_opts[p_ans]) in inv:
                L = inv[norm(p_opts[p_ans])]
                return L, options[L], "same_options"

    checks = [
        (lambda q: "giai đoạn phát triển đó là" in q or ("các giai đoạn" in q and "đó là" in q),
         lambda t: "đại công nghiệp" in t.lower() and "công trường" in t.lower()),
        (lambda q: "cách mạng công nghiệp lần thứ hai" in q and "thời gian" in q,
         lambda t: "xix" in norm(t) and "xx" in norm(t)),
        (lambda q: "không đúng" in q and ("nguồn" in q or "vốn" in q),
         lambda t: "vay" in t.lower()),
        (lambda q: "giá trị thặng dư tuyệt đối" in q and "không đúng" in q,
         lambda t: "ngày lao động" in t.lower() and "không thay đổi" in t.lower()),
        (lambda q: "tích lũy tư bản là gì" in q,
         lambda t: "tư bản hóa giá trị thặng dư" in t.lower() or "biến giá trị thặng dư" in t.lower()),
        (lambda q: "cách mạng công nghiệp lần thứ ba" in q,
         lambda t: "60" in t or "thế kỷ xx" in t.lower()),
        (lambda q: "kinh tế" in q and "chính trị" in q and ("đầu tiên" in q or "ai là người" in q),
         lambda t: "montchrestien" in t.lower() or "montchrétien" in t.lower() or "antoine" in t.lower()),
        (lambda q: "công thức tính giá trị hàng hóa" in q or "gọi w là giá trị" in q,
         lambda t: "c + v" in t.lower() and "m" in t.lower() and "/" not in t),
    ]
    for qpred, tpred in checks:
        if qpred(ql):
            for L, t in options.items():
                if tpred(t):
                    return L, t, "heuristic"
    if "kinh tế chính trị cổ điển anh" in ql:
        for L, t in options.items():
            if "petty" in t.lower():
                return L, t, "heuristic"
        for L, t in options.items():
            if "adam smith" in t.lower():
                return L, t, "heuristic"
    return None, None, None


def build_alt(question_parts, options, answer, answer_text, parent):
    question = clean_text(" ".join(question_parts))
    options = {k: clean_text(v) for k, v in (options or {}).items() if clean_text(v)}
    inferred = None

    if answer and options:
        letters = list(answer)
        if all(L in options for L in letters):
            if len(letters) == 1:
                answer_text = answer_text or options.get(answer)
            else:
                answer_text = answer_text or ", ".join(options[L] for L in letters)
        elif answer[0] in options:
            answer = answer[0]
            answer_text = answer_text or options.get(answer)
    elif answer_text and options:
        nt = norm(answer_text)
        for L, t in options.items():
            if norm(t) == nt or nt in norm(t) or norm(t) in nt:
                answer = L
                break
    elif answer_text and not options:
        inferred = "arrow_text"
    elif options:
        a, t, inf = infer_alt_answer(question, options, parent)
        if a:
            answer, answer_text, inferred = a, t, inf
    elif not options and parent:
        answer = parent.get("answer")
        options = dict(parent.get("options") or {})
        answer_text = options.get(answer)
        inferred = "parent_rephrase"

    if answer and not answer_text and options:
        answer_text = options.get(answer[0]) if answer else None

    primary = answer[0] if answer else None
    return {
        "question": question or "(Biến thể)",
        "options": options,
        "answer": primary,
        "answers": list(answer) if answer and len(answer) > 1 else ([primary] if primary else []),
        "answerText": answer_text,
        "inferredFrom": inferred,
    }


def parse_variant_block(i, parent, header_re):
    """Parse Kiểu hỏi khác / tương tự starting at i."""
    if i >= n or not header_re.match(lines[i]):
        return None, i
    m = header_re.match(lines[i])
    rest = (m.group(1) or "").strip()
    i += 1
    question_parts = []
    answer_text = None
    options = {}
    answer = None

    if rest:
        one = rest
        closed = one.endswith(")")
        if closed:
            one = one[:-1].strip()
        if "->" in one:
            left, right = one.split("->", 1)
            return build_alt([left.strip()], {}, None, clean_text(right), parent), skip_empty(i)
        if closed:
            return build_alt([one], {}, None, None, parent), skip_empty(i)
        question_parts.append(rest)

    while i < n:
        if header_re.match(lines[i]) or kieu_re.match(lines[i]) or tuong_tu_re.match(lines[i]):
            if not (header_re.match(lines[i]) and i == i):  # other variant start
                if kieu_re.match(lines[i]) or tuong_tu_re.match(lines[i]):
                    break
        if opt_re.match(lines[i]) or is_answer_line(lines[i]):
            break
        if is_empty(lines[i]):
            j = skip_empty(i)
            if j >= n:
                i = j
                break
            if opt_re.match(lines[j]) or is_answer_line(lines[j]) or kieu_re.match(lines[j]) or tuong_tu_re.match(lines[j]):
                i = j
                break
            if question_parts and look_like_new_question(lines[j]):
                if "->" in lines[j]:
                    left, right = lines[j].split("->", 1)
                    question_parts.append(left.strip())
                    answer_text = clean_text(right)
                    i = j + 1
                    break
                question_parts.append(lines[j])
                i = j + 1
                continue
            if not question_parts:
                question_parts.append(lines[j])
                i = j + 1
                continue
            i = j
            break
        line = lines[i]
        if line == ")":
            i += 1
            break
        if "->" in line:
            left, right = line.split("->", 1)
            if left.strip():
                question_parts.append(left.strip())
            answer_text = clean_text(right)
            i += 1
            break
        question_parts.append(line)
        i += 1

    qjoin = " ".join(question_parts)
    if "->" in qjoin and not answer_text:
        left, right = qjoin.split("->", 1)
        question_parts = [left.strip()]
        answer_text = clean_text(right)

    if i < n and opt_re.match(lines[i]):
        options, i = parse_options(i)
        j = skip_empty(i)
        if j < n and is_answer_line(lines[j]):
            k = skip_empty(j + 1)
            if not (k < n and opt_re.match(lines[k])):
                answer = parse_answer_value(lines[j])
                i = j + 1
            else:
                i = j
        elif j < n and look_like_new_question(lines[j]):
            i = j

    i = skip_empty(i)
    if i < n and lines[i] == ")":
        i += 1

    return build_alt(question_parts, options, answer, answer_text, parent), skip_empty(i)


def make_question(question_text, options, answer, alternatives=None, source="main"):
    primary = answer[0]
    q = {
        "id": 0,
        "question": question_text,
        "options": options,
        "answer": primary,
        "alternatives": alternatives or [],
        "source": source,
    }
    if len(answer) > 1:
        q["answers"] = list(answer)
    return q


questions = []
i = 0
failed = []
promoted = []

while i < n:
    i = skip_empty(i)
    if i >= n:
        break

    if kieu_re.match(lines[i]) or tuong_tu_re.match(lines[i]):
        hdr = kieu_re if kieu_re.match(lines[i]) else tuong_tu_re
        alt, i = parse_variant_block(i, None, hdr)
        if alt and len(alt.get("options") or {}) >= 2 and alt.get("answer") and alt["answer"] in alt["options"]:
            promoted.append(alt)
        continue

    q_parts = []
    start = i
    while i < n:
        if is_empty(lines[i]):
            j = skip_empty(i)
            if j < n and opt_re.match(lines[j]):
                i = j
                break
            if j < n and (is_answer_line(lines[j]) or kieu_re.match(lines[j]) or tuong_tu_re.match(lines[j])):
                i = j
                break
            if j < n and look_like_new_question(lines[j]) and q_parts:
                q_parts.append(lines[j])
                i = j + 1
                continue
            i = j
            continue
        if opt_re.match(lines[i]) or is_answer_line(lines[i]) or kieu_re.match(lines[i]) or tuong_tu_re.match(lines[i]):
            break
        q_parts.append(lines[i])
        i += 1
        if len(q_parts) > 40:
            break

    if not q_parts:
        i += 1
        continue

    question_text = clean_text(" ".join(q_parts))
    if question_text.startswith("(") and ")" not in question_text:
        question_text = question_text.lstrip("(").strip()

    options, i = parse_options(i)
    answer, i = parse_answer(i)

    # Salvage known parenthetical notes without answer letter
    if not answer and len(options) >= 2:
        ql = question_text.lower()
        if "cơ bản nhất" in ql and "đời sống xã hội" in ql and "B" in options:
            answer = "B"
        elif "chức năng cất trữ" in ql and "C" in options:
            answer = "C"
        elif "mô hình kinh tế thị trường định hướng" in ql and "đại hội" in ql and "C" in options:
            answer = "C"  # Đại hội IX

    valid = bool(answer) and all(ch in options for ch in answer) and len(options) >= 2
    if not (question_text and valid):
        failed.append({"q": question_text[:90], "opts": list(options.keys()), "ans": answer, "at": start})
        continue

    q_obj = make_question(question_text, options, answer)

    i = skip_empty(i)
    while i < n and (kieu_re.match(lines[i]) or tuong_tu_re.match(lines[i])):
        hdr = kieu_re if kieu_re.match(lines[i]) else tuong_tu_re
        alt, i = parse_variant_block(i, q_obj, hdr)
        if alt and alt.get("question"):
            q_obj["alternatives"].append(
                {
                    "question": alt["question"],
                    "options": alt.get("options") or {},
                    "answer": alt.get("answer"),
                    "answerText": alt.get("answerText"),
                    "inferredFrom": alt.get("inferredFrom"),
                }
            )
            aopts = alt.get("options") or {}
            aans = alt.get("answer")
            if len(aopts) >= 2 and aans and aans in aopts and norm(alt["question"]) != norm(q_obj["question"]):
                promoted.append(alt)
        i = skip_empty(i)

    questions.append(q_obj)

for alt in promoted:
    aopts = alt.get("options") or {}
    aans = alt.get("answer")
    if not (len(aopts) >= 2 and aans and all(c in aopts for c in str(aans))):
        continue
    ans = str(aans)
    questions.append(make_question(alt["question"], aopts, ans, [], source="kieu"))

# Dedupe by normalized question text only (keep first = main preferred)
seen = set()
unique = []
for q in questions:
    key = norm(q["question"])
    if key in seen:
        # merge alternatives if newer has more
        for u in unique:
            if norm(u["question"]) == key:
                if len(q.get("alternatives") or []) > len(u.get("alternatives") or []):
                    u["alternatives"] = q["alternatives"]
                break
        continue
    seen.add(key)
    unique.append(q)

for idx, q in enumerate(unique, 1):
    q["id"] = idx
    if q.get("answers") == [q.get("answer")]:
        q.pop("answers", None)

print(f"Source: {src}")
print(f"Parsed: {len(questions)} raw → {len(unique)} unique, failed={len(failed)}")
print("option counts:", dict(Counter(len(q["options"]) for q in unique)))
print("answers primary:", dict(Counter(q["answer"] for q in unique)))
print("sources:", dict(Counter(q.get("source", "main") for q in unique)))
print("with alts:", sum(1 for q in unique if q.get("alternatives")))
print("multi-answer qs:", sum(1 for q in unique if q.get("answers")))

with open("questions.json", "w", encoding="utf-8") as f:
    json.dump(unique, f, ensure_ascii=False, indent=2)
with open("questions.js", "w", encoding="utf-8") as f:
    f.write("// Auto-generated from data.docx\n")
    f.write("window.QUIZ_QUESTIONS = ")
    json.dump(unique, f, ensure_ascii=False)
    f.write(";\n")
print("Wrote questions.json + questions.js")
if failed:
    print("failures:", len(failed))
    for fitem in failed[:10]:
        print(" ", fitem)
