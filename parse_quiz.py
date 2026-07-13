# -*- coding: utf-8 -*-
"""
Parse data_extracted.txt → questions.json / questions.js
Attaches 'Kiểu hỏi khác' alternatives to the preceding question.
"""
import re
import json
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

raw = open("data_extracted.txt", encoding="utf-8").read()
raw = raw.replace("\r\n", "\n").replace("\r", "\n")
# strip author tags (no newlines)
raw = re.sub(r"[ \t]*\(NHUNG HOÀNG\)", "", raw)

lines = [ln.strip() for ln in raw.split("\n")]
n = len(lines)

opt_re = re.compile(r"^([A-D])\s*[\.\)\:]\s*(.*)$", re.I)
ans_re = re.compile(r"^([A-D])$", re.I)
# multi-select answers e.g. AC, ABD, ABC
ans_multi_re = re.compile(r"^([A-D]{2,4})$", re.I)
kieu_re = re.compile(r"^\(?\s*Kiểu hỏi khác\s*[:：]?\s*(.*)$", re.I)

def is_empty(s):
    return s is None or str(s).strip() == ""


def norm(s):
    s = re.sub(r"\s+", " ", (s or "")).strip().lower()
    return s.strip(" .;:)?！？")


def clean_text(s):
    s = re.sub(r"\s+", " ", (s or "")).strip()
    # unwrap trailing lone )
    while s.endswith(")") and s.count("(") < s.count(")"):
        s = s[:-1].strip()
    return s


def skip_empty(i):
    while i < n and is_empty(lines[i]):
        i += 1
    return i


def is_answer_line(s):
    return bool(s) and (bool(ans_re.match(s)) or bool(ans_multi_re.match(s)))


def is_option_continuation(s):
    """True only for short wrap lines of the same option, not a new question."""
    if is_empty(s):
        return False
    if opt_re.match(s) or is_answer_line(s) or kieu_re.match(s):
        return False
    # New question heuristics: long, or ends with question mark / "là" / "gì"
    if look_like_new_question(s):
        return False
    # allow short fragments (wrapped option text)
    return len(s) < 80

def parse_options(i):
    """Return (options:dict, next_index). Stops before non-option content."""
    options = {}
    i = skip_empty(i)
    while i < n:
        m = opt_re.match(lines[i])
        if not m:
            break
        letter = m.group(1).upper()
        body = [m.group(2).strip()]
        i += 1
        # continuation lines (soft wrap only — never swallow next question)
        while i < n:
            if is_empty(lines[i]):
                j = skip_empty(i)
                if j >= n:
                    i = j
                    break
                if opt_re.match(lines[j]) or is_answer_line(lines[j]) or kieu_re.match(lines[j]):
                    i = j
                    break
                if not is_option_continuation(lines[j]):
                    # next question / other block — leave i at that line
                    i = j
                    break
                body.append(lines[j])
                i = j + 1
                continue
            if opt_re.match(lines[i]) or is_answer_line(lines[i]) or kieu_re.match(lines[i]):
                break
            if not is_option_continuation(lines[i]):
                break
            body.append(lines[i])
            i += 1
        options[letter] = clean_text(" ".join(x for x in body if x))
    return options, i
def parse_answer_letter(i):
    """If current line is lone A-D or multi like AC, return (letter(s), next_i)."""
    i0 = skip_empty(i)
    if i0 < n and ans_re.match(lines[i0]):
        return lines[i0].upper(), i0 + 1
    if i0 < n and ans_multi_re.match(lines[i0]):
        return lines[i0].upper(), i0 + 1
    return None, i

def look_like_new_question(s):
    """Heuristic: non-empty, not option/answer/kieu, reasonably long."""
    if is_empty(s):
        return False
    if opt_re.match(s) or ans_re.match(s) or kieu_re.match(s):
        return False
    if s in (")", "(", "->"):
        return False
    return len(s) >= 8


def parse_kieu_at(i, parent):
    """
    Parse exactly one Kiểu hỏi khác block starting at i.
    Returns (alt_dict|None, next_i).

    End conditions for the block:
    - Closed parenthesis on header/option
    - After options: do NOT consume following main question
    - Never consume a lone answer letter that belongs to a following full MCQ
      (we only take answer letter if it appears BEFORE a new question and
       immediately after this block's own options)
    """
    if i >= n or not kieu_re.match(lines[i]):
        return None, i

    m = kieu_re.match(lines[i])
    rest = (m.group(1) or "").strip()
    i += 1

    question_parts = []
    answer_text = None
    options = {}
    answer = None

    # Case: whole alt on one line: (Kiểu hỏi khác: ... )  or with ->
    if rest:
        # one-line closed
        one = rest
        closed_one = one.endswith(")")
        if closed_one:
            one = one[:-1].strip()
        if "->" in one:
            left, right = one.split("->", 1)
            question_parts.append(left.strip())
            answer_text = clean_text(right)
            # done with one-liner
            i = skip_empty(i)
            alt = build_alt(question_parts, options, answer, answer_text, parent)
            return alt, i
        if closed_one:
            question_parts.append(one)
            i = skip_empty(i)
            alt = build_alt(question_parts, options, answer, answer_text, parent)
            return alt, i
        # multi-line header continues
        question_parts.append(rest)

    # Multi-line body: gather question lines until options or end
    while i < n:
        if kieu_re.match(lines[i]):
            break
        if opt_re.match(lines[i]):
            break
        if ans_re.match(lines[i]):
            # lone letter without options — treat as end (parent's domain)
            break
        if is_empty(lines[i]):
            j = skip_empty(i)
            if j >= n:
                i = j
                break
            if opt_re.match(lines[j]):
                i = j
                break
            if kieu_re.match(lines[j]):
                i = j
                break
            if ans_re.match(lines[j]):
                i = j
                break
            # blank then text: if we already have a question phrase, this is next main Q
            if question_parts and look_like_new_question(lines[j]):
                i = j
                break
            question_parts.append(lines[j])
            i = j + 1
            continue

        line = lines[i]
        if line == ")":
            i += 1
            break
        # arrow on its own line pieces already in question
        if "->" in line:
            left, right = line.split("->", 1)
            if left.strip():
                question_parts.append(left.strip())
            answer_text = clean_text(right)
            i += 1
            # skip trailing )
            i = skip_empty(i)
            if i < n and lines[i] == ")":
                i += 1
            alt = build_alt(question_parts, options, answer, answer_text, parent)
            return alt, i
        question_parts.append(line)
        i += 1

    # Options for this alt only
    if i < n and opt_re.match(lines[i]):
        options, i = parse_options(i)

        # Answer letter only if it comes RIGHT AFTER these options,
        # and what follows the letter is NOT more options of a main question.
        j = skip_empty(i)
        if j < n and ans_re.match(lines[j]):
            k = skip_empty(j + 1)
            follows_opts = k < n and opt_re.match(lines[k])
            follows_q = k < n and look_like_new_question(lines[k])
            # Valid alt answer: letter then new question / kieu / EOF / )
            # Invalid: letter then options (that would be main Q's answer mid-stream — shouldn't happen)
            # Also invalid if before letter we already hit new question text (i points there)
            if not follows_opts:
                answer = lines[j].upper()
                i = j + 1
            else:
                i = j
        else:
            # If i landed on a new question line, do not advance past it
            i = j if (j < n and look_like_new_question(lines[j])) else i
            if j < n and look_like_new_question(lines[j]):
                i = j
    # strip trailing )
    i = skip_empty(i)
    if i < n and lines[i] == ")":
        i += 1

    # If question has -> embedded
    qjoin = " ".join(question_parts)
    if "->" in qjoin and not answer_text:
        left, right = qjoin.split("->", 1)
        question_parts = [left.strip()]
        answer_text = clean_text(right)

    alt = build_alt(question_parts, options, answer, answer_text, parent)
    return alt, skip_empty(i)


def build_alt(question_parts, options, answer, answer_text, parent):
    question = clean_text(" ".join(question_parts))
    options = {k: clean_text(v) for k, v in (options or {}).items() if clean_text(v)}
    inferred = None

    # Explicit letter
    if answer and options:
        if answer not in options and len(answer) == 1:
            pass
        if answer in options:
            answer_text = answer_text or options[answer]
    elif answer_text and options:
        nt = norm(answer_text)
        for L, t in options.items():
            if norm(t) == nt or nt in norm(t) or norm(t) in nt:
                answer = L
                break
    elif answer_text and not options:
        # Arrow form: "câu hỏi? -> đáp án text" — keep text, do NOT overwrite with parent
        inferred = "arrow_text"
    elif options and parent:
        p_ans = parent.get("answer")
        p_opts = parent.get("options") or {}
        p_text = p_opts.get(p_ans, "")
        # match parent correct text to an alt option
        if p_text:
            np = norm(p_text)
            for L, t in options.items():
                if norm(t) == np or np in norm(t) or norm(t) in np:
                    answer = L
                    answer_text = t
                    inferred = "parent_text_match"
                    break
        # identical option texts → same letter mapping
        if not answer and p_opts:
            p_map = {norm(t): L for L, t in p_opts.items()}
            a_map = {norm(t): L for L, t in options.items()}
            if set(p_map.keys()) == set(a_map.keys()) and p_ans in p_opts:
                answer = a_map.get(norm(p_opts[p_ans]))
                if answer:
                    answer_text = options[answer]
                    inferred = "same_options"
    elif not options and parent:
        # rephrase only — inherit parent answer & options for display
        answer = parent.get("answer")
        options = dict(parent.get("options") or {})
        answer_text = options.get(answer)
        inferred = "parent_rephrase"
    if answer and not answer_text and options:
        answer_text = options.get(answer)

    # Heuristic answers for known alt forms without a letter in the file
    if options and not answer:
        answer, answer_text, inferred2 = infer_hardcoded(question, options)
        if answer:
            inferred = inferred2

    return {
        "question": question or "(Biến thể)",
        "options": options,
        "answer": answer,
        "answerText": answer_text,
        "inferredFrom": inferred,
    }


def infer_hardcoded(question, options):
    """Best-effort answers when file omits the letter for an alternate form."""
    ql = (question or "").lower()

    # CM lần 1 — các giai đoạn: Hiệp tác đơn giản → công trường thủ công → đại công nghiệp
    if "giai đoạn phát triển đó là" in ql or "các giai đoạn" in ql and "đó là" in ql:
        for L, t in options.items():
            if "đại công nghiệp" in t.lower() and "công trường" in t.lower():
                return L, t, "heuristic"

    # CM lần 2 — thời gian alternate
    if "cách mạng công nghiệp lần thứ hai" in ql and "thời gian" in ql:
        for L, t in options.items():
            tl = t.lower()
            if "xix" in norm(t) and "xx" in norm(t):
                return L, t, "heuristic"
            if "thế kỷ xix" in tl and "thế kỷ xx" in tl:
                return L, t, "heuristic"

    # Nguồn gốc nào KHÔNG đúng (đáp án là "Đi vay nhà nước")
    if "không đúng" in ql and ("nguồn" in ql or "vốn" in ql):
        for L, t in options.items():
            if "vay" in t.lower():
                return L, t, "heuristic"

    # GTTD tuyệt đối — nhận xét không đúng
    if "giá trị thặng dư tuyệt đối" in ql and "không đúng" in ql:
        for L, t in options.items():
            if "ngày lao động" in t.lower() and "không thay đổi" in t.lower():
                return L, t, "heuristic"
        if "C" in options and len(options) <= 3:
            return "C", options["C"], "heuristic"

    # Kinh tế chính trị cổ điển Anh — mở đầu bằng W. Petty / Adam Smith tùy đáp án
    if "kinh tế chính trị cổ điển anh" in ql:
        for L, t in options.items():
            if "william petty" in t.lower() or "w. petty" in t.lower() or "adam smith" in t.lower():
                # dataset often: Petty or Smith — prefer Petty if present else Smith
                pass
        for L, t in options.items():
            if "petty" in t.lower():
                return L, t, "heuristic"
        for L, t in options.items():
            if "adam smith" in t.lower():
                return L, t, "heuristic"

    # Tích lũy tư bản
    if "tích lũy tư bản là gì" in ql or ql.rstrip("?").endswith("tích lũy tư bản là gì"):
        for L, t in options.items():
            if "tư bản hóa giá trị thặng dư" in t.lower() or "biến giá trị thặng dư" in t.lower():
                return L, t, "heuristic"

    # CM lần 3 thời gian
    if "cách mạng công nghiệp lần thứ ba" in ql and ("thời gian" in ql or "giai đoạn" in ql):
        for L, t in options.items():
            if "xx" in norm(t) or "thế kỷ xx" in t.lower() or "1970" in t or "chiến tranh thế giới" in t.lower():
                return L, t, "heuristic"

    # Ai đưa ra khái niệm kinh tế chính trị
    if "kinh tế" in ql and "chính trị" in ql and ("đầu tiên" in ql or "ai là người" in ql):
        for L, t in options.items():
            if "montchrestien" in t.lower() or "montchrétien" in t.lower() or "antoine" in t.lower():
                return L, t, "heuristic"

    return None, None, None

# ─── Main scan ───
questions = []
i = 0
failed = []

while i < n:
    i = skip_empty(i)
    if i >= n:
        break

    # stray kieu (shouldn't happen often)
    if kieu_re.match(lines[i]):
        _, i = parse_kieu_at(i, None)
        continue

    # question text
    q_parts = []
    start = i
    while i < n:
        if is_empty(lines[i]):
            j = skip_empty(i)
            if j < n and opt_re.match(lines[j]):
                i = j
                break
            if j < n and (ans_re.match(lines[j]) or kieu_re.match(lines[j])):
                i = j
                break
            if j < n and look_like_new_question(lines[j]) and q_parts:
                # another paragraph — keep if no options yet? treat as continuation
                q_parts.append(lines[j])
                i = j + 1
                continue
            i = j
            if j < n and opt_re.match(lines[j]):
                break
            continue
        if opt_re.match(lines[i]):
            break
        if ans_re.match(lines[i]):
            break
        if kieu_re.match(lines[i]):
            break
        q_parts.append(lines[i])
        i += 1
        if len(q_parts) > 40:
            break

    if not q_parts:
        i += 1
        continue

    question_text = clean_text(" ".join(q_parts))
    options, i = parse_options(i)
    answer, i = parse_answer_letter(i)

    # answer may be multi-letter (AC); require all letters exist in options
    valid_ans = bool(answer) and all(ch in options for ch in answer)
    if not (question_text and len(options) >= 2 and valid_ans):
        failed.append({"q": question_text[:80], "opts": list(options.keys()), "ans": answer, "at": start})
        continue

    # Primary letter for single-choice UI (first letter if multi)
    primary = answer[0]
    q_obj = {
        "id": 0,
        "question": question_text,
        "options": options,
        "answer": primary,
        "answers": list(answer) if len(answer) > 1 else [primary],
        "alternatives": [],
    }
    # Attach following kieu blocks (can be multiple)
    i = skip_empty(i)
    while i < n and kieu_re.match(lines[i]):
        alt, i = parse_kieu_at(i, q_obj)
        if alt and alt.get("question"):
            q_obj["alternatives"].append(alt)
        i = skip_empty(i)

    questions.append(q_obj)

# Dedupe
seen = {}
unique = []
for q in questions:
    key = norm(q["question"])
    if key in seen:
        idx = seen[key]
        if len(q["alternatives"]) > len(unique[idx]["alternatives"]):
            unique[idx] = q
        continue
    seen[key] = len(unique)
    unique.append(q)

for idx, q in enumerate(unique, 1):
    q["id"] = idx
    # Drop redundant answers field when single choice
    if q.get("answers") == [q.get("answer")]:
        q.pop("answers", None)

print(f"Parsed: {len(questions)} raw → {len(unique)} unique, failed={len(failed)}")
print("option counts:", dict(Counter(len(q["options"]) for q in unique)))
print("answers:", dict(Counter(q["answer"] for q in unique)))
with_alt = [q for q in unique if q["alternatives"]]
print(f"with alternatives: {len(with_alt)}")
alt_n = sum(len(q["alternatives"]) for q in unique)
ans_n = sum(1 for q in unique for a in q["alternatives"] if a.get("answer") or a.get("answerText"))
print(f"alt blocks: {alt_n}, with answer: {ans_n}")

# dump first alts summary
for q in with_alt[:6]:
    print("Q", q["id"], ":", q["question"][:60])
    for a in q["alternatives"]:
        print(
            "  ALT:",
            a["question"][:55],
            "|",
            a.get("answer"),
            "|",
            (a.get("answerText") or "")[:40],
            "| opts",
            len(a.get("options") or {}),
            "|",
            a.get("inferredFrom"),
        )

with open("questions.json", "w", encoding="utf-8") as f:
    json.dump(unique, f, ensure_ascii=False, indent=2)

with open("questions.js", "w", encoding="utf-8") as f:
    f.write("// Auto-generated from data.docx\n")
    f.write("window.QUIZ_QUESTIONS = ")
    json.dump(unique, f, ensure_ascii=False)
    f.write(";\n")

print("Wrote questions.json + questions.js")
if failed[:3]:
    print("failures sample:", failed[:3])
