# -*- coding: utf-8 -*-
"""
Parse data.docx → questions.json / questions.js

Đếm đúng nguồn gốc:
  • 1 câu chính = 1 dòng đáp án  → 526 câu
  • "Kiểu hỏi khác / tương tự" KHÔNG phải câu riêng
  • Chỉ gắn vào parent.alternatives (hiện sau khi chọn)
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

opt_re = re.compile(r"^([A-E])\s*[\.\)\:]\s*(.*)$", re.I)
ans_pure = re.compile(r"^([A-E]{1,5})$", re.I)
ans_note = re.compile(r"^([A-E]{1,5})\s*[\(（].+", re.I)
variant_re = re.compile(r"^\(?\s*Kiểu hỏi\s+(khác|tương tự)\b\s*[:：]?\s*(.*)$", re.I)


def is_empty(s):
    return not s


def norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip().lower().strip(" .;:)?！？")


def clean_text(s):
    s = re.sub(r"\s+", " ", (s or "")).strip()
    while s.endswith(")") and s.count("(") < s.count(")"):
        s = s[:-1].strip()
    return s


def is_answer_line(s):
    return bool(s) and (bool(ans_pure.match(s)) or bool(ans_note.match(s)))


def parse_answer_value(s):
    m = ans_pure.match(s) or ans_note.match(s)
    return m.group(1).upper() if m else None


def is_variant_header(s):
    return bool(s) and bool(variant_re.match(s))


def is_option_continuation(s):
    if is_empty(s):
        return False
    if opt_re.match(s) or is_answer_line(s) or is_variant_header(s):
        return False
    if s[:1].islower() or s.startswith(("cũng", "và ", "hoặc ", "hay ", "của ", "trong ", "với ")):
        return True
    # long line that looks like a new question — not continuation
    if len(s) >= 8 and not opt_re.match(s):
        # short fragments only
        if len(s) >= 100:
            return False
    return len(s) < 100


# ─── Collect every answer line index ───
answer_idxs = [i for i, l in enumerate(lines) if is_answer_line(l)]


def extract_options_ending_at(end_i):
    """
    Walk backward from end_i (exclusive, usually answer line)
    to collect contiguous A–E options.
    Returns (options_dict, first_option_index).
    """
    # find last option line before end_i
    j = end_i - 1
    while j >= 0 and is_empty(lines[j]):
        j -= 1
    if j < 0 or not opt_re.match(lines[j]):
        # might have junk; scan further back a bit
        k = end_i - 1
        found = None
        while k >= max(0, end_i - 30):
            if opt_re.match(lines[k]):
                found = k
                break
            k -= 1
        if found is None:
            return {}, end_i
        j = found

    # collect option lines from j backward until non-option block
    opt_lines = []  # (index, letter, text_start)
    while j >= 0:
        if is_empty(lines[j]):
            j -= 1
            continue
        m = opt_re.match(lines[j])
        if m:
            opt_lines.append((j, m.group(1).upper(), m.group(2).strip()))
            j -= 1
            continue
        # continuation of previous option? we're going backward so
        # non-option text between options is rare; stop
        break

    if not opt_lines:
        return {}, end_i

    opt_lines.reverse()  # chronological
    first_opt_i = opt_lines[0][0]

    # Build option texts; include forward continuations between option starts
    options = {}
    for idx, (oi, letter, rest) in enumerate(opt_lines):
        next_boundary = opt_lines[idx + 1][0] if idx + 1 < len(opt_lines) else end_i
        body = [rest] if rest else []
        t = oi + 1
        while t < next_boundary:
            if is_empty(lines[t]):
                t += 1
                continue
            if opt_re.match(lines[t]) or is_answer_line(lines[t]) or is_variant_header(lines[t]):
                break
            if is_option_continuation(lines[t]) or (lines[t] and not look_like_hard_question(lines[t])):
                # include soft wraps
                if not look_like_hard_question(lines[t]):
                    body.append(lines[t])
            t += 1
        options[letter] = clean_text(" ".join(body))

    return options, first_opt_i


def look_like_hard_question(s):
    """True if line is clearly a new stem, not option wrap."""
    if is_empty(s) or opt_re.match(s) or is_answer_line(s) or is_variant_header(s):
        return False
    if s[:1].islower():
        return False
    if len(s) < 12:
        return False
    # option wraps are usually short
    return len(s) >= 40 or s.endswith("?") or s.endswith(":") or s.endswith("là")


def extract_question_text(first_opt_i, prev_answer_i):
    """
    Question stem = non-empty lines after previous answer (or prev_answer+1)
    and before first_opt_i, excluding variant headers and their bodies.
    """
    start = (prev_answer_i + 1) if prev_answer_i is not None else 0
    # skip variant blocks entirely
    parts = []
    i = start
    while i < first_opt_i:
        if is_empty(lines[i]):
            i += 1
            continue
        if is_variant_header(lines[i]):
            # skip until first_opt or until we leave variant (options of variant
            # are BEFORE first_opt of main only if variant has no options)
            # Variant may have its own options which appear before main options —
            # those options are NOT main options; extract_options already found
            # main options ending at answer. Variant options sit between prev answer
            # and main question stem OR between stem and main options.
            # If variant is BETWEEN stem and options, first_opt is main's A.
            # Skip variant header + its option lines.
            i += 1
            while i < first_opt_i:
                if is_variant_header(lines[i]):
                    break
                # stop skipping when we hit text that will be part of stem?
                # safer: skip only option lines and empties and arrow lines of variant
                if opt_re.match(lines[i]):
                    i += 1
                    continue
                if is_empty(lines[i]):
                    i += 1
                    continue
                # variant question text or end
                # if next non-empty after this is options of main, this might be alt Q text
                i += 1
                # continue skip until options of main (first_opt_i)
                while i < first_opt_i and (is_empty(lines[i]) or opt_re.match(lines[i]) or not look_like_hard_question(lines[i])):
                    # if we see a hard question, that's main stem — break skip
                    if look_like_hard_question(lines[i]) and not is_variant_header(lines[i]):
                        break
                    if opt_re.match(lines[i]):
                        # still variant options or early main — if letter sequence restarts at A after variant Q
                        i += 1
                        continue
                    i += 1
                break
            continue
        if opt_re.match(lines[i]):
            # options belonging to a preceding variant — skip
            i += 1
            continue
        if is_answer_line(lines[i]):
            i += 1
            continue
        parts.append(lines[i])
        i += 1

    text = clean_text(" ".join(parts))
    if text.startswith("(") and not text.endswith(")"):
        text = text.lstrip("(").strip()
    return text


def parse_variants_between(prev_answer_i, first_opt_i, parent):
    """Parse variant blocks that appear after prev answer and before main options...
    Actually variants appear AFTER main answer in the file layout:

      Q stem
      A B C D
      ANS
      (Kiểu hỏi khác: ...)
      next Q

    So variants are BETWEEN this answer and the NEXT question's stem.
    We'll parse them in a second pass after all main Qs are known.
    """
    return []


def infer_alt(question, options, parent):
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
    rules = [
        (lambda q: "giai đoạn phát triển đó là" in q or ("các giai đoạn" in q and "đó là" in q),
         lambda t: "đại công nghiệp" in t.lower() and "công trường" in t.lower()),
        (lambda q: "cách mạng công nghiệp lần thứ hai" in q and "thời gian" in q,
         lambda t: "xix" in norm(t) and "xx" in norm(t)),
        (lambda q: "không đúng" in q and ("nguồn" in q or "vốn" in q),
         lambda t: "vay" in t.lower()),
        (lambda q: "giá trị thặng dư tuyệt đối" in q and "không đúng" in q,
         lambda t: "ngày lao động" in t.lower() and "không thay đổi" in t.lower()),
        (lambda q: "tích lũy tư bản là gì" in q,
         lambda t: "tư bản hóa giá trị thặng dư" in t.lower()),
        (lambda q: "cách mạng công nghiệp lần thứ ba" in q,
         lambda t: "60" in t or "thế kỷ xx" in t.lower()),
        (lambda q: "montchrestien" in " ".join(options.values()).lower() or ("ai là người" in q and "kinh tế" in q),
         lambda t: "montchrestien" in t.lower() or "antoine" in t.lower()),
    ]
    for qpred, tpred in rules:
        try:
            if qpred(ql):
                for L, t in options.items():
                    if tpred(t):
                        return L, t, "heuristic"
        except Exception:
            pass
    if "kinh tế chính trị cổ điển anh" in ql:
        for L, t in options.items():
            if "petty" in t.lower() or "adam smith" in t.lower():
                return L, t, "heuristic"
    return None, None, None


def parse_alt_block(start_i, end_i, parent):
    """Parse one variant block in [start_i, end_i)."""
    if start_i >= end_i or not is_variant_header(lines[start_i]):
        return None
    m = variant_re.match(lines[start_i])
    rest = (m.group(2) or "").strip() if m else ""
    question_parts = []
    answer_text = None
    options = {}

    if rest:
        one = rest[:-1].strip() if rest.endswith(")") else rest
        if "->" in one:
            left, right = one.split("->", 1)
            return {
                "question": clean_text(left),
                "options": {},
                "answer": None,
                "answerText": clean_text(right),
                "inferredFrom": "arrow_text",
            }
        if rest.endswith(")") and "->" not in rest:
            # rephrase only
            ans = parent.get("answer") if parent else None
            opts = dict(parent.get("options") or {}) if parent else {}
            return {
                "question": clean_text(one),
                "options": opts,
                "answer": ans,
                "answerText": opts.get(ans) if ans else None,
                "inferredFrom": "parent_rephrase",
            }
        question_parts.append(one if rest.endswith(")") else rest)

    i = start_i + 1
    while i < end_i:
        if is_variant_header(lines[i]):
            break
        if is_empty(lines[i]):
            i += 1
            continue
        if opt_re.match(lines[i]):
            break
        if is_answer_line(lines[i]):
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

    # options until end_i
    while i < end_i:
        if is_empty(lines[i]):
            i += 1
            continue
        m = opt_re.match(lines[i])
        if not m:
            break
        letter = m.group(1).upper()
        body = [m.group(2).strip()]
        i += 1
        while i < end_i:
            if is_empty(lines[i]):
                i += 1
                continue
            if opt_re.match(lines[i]) or is_answer_line(lines[i]) or is_variant_header(lines[i]):
                break
            if lines[i] == ")":
                i += 1
                break
            body.append(lines[i])
            i += 1
        options[letter] = clean_text(" ".join(x for x in body if x))

    question = clean_text(" ".join(question_parts))
    answer = None
    inferred = None
    if answer_text and not options:
        inferred = "arrow_text"
    elif options:
        a, t, inf = infer_alt(question, options, parent)
        if a:
            answer, answer_text, inferred = a, t, inf
    elif parent:
        answer = parent.get("answer")
        options = dict(parent.get("options") or {})
        answer_text = options.get(answer)
        inferred = "parent_rephrase"

    if answer and not answer_text and options:
        answer_text = options.get(answer)

    return {
        "question": question or "(Biến thể)",
        "options": options,
        "answer": answer,
        "answerText": answer_text,
        "inferredFrom": inferred,
    }


# ─── Build main questions from each answer line ───
questions = []
failed = []

for qi, ans_i in enumerate(answer_idxs):
    answer = parse_answer_value(lines[ans_i])
    prev_ans = answer_idxs[qi - 1] if qi > 0 else None

    options, first_opt_i = extract_options_ending_at(ans_i)
    if len(options) < 2 or not answer or not all(ch in options for ch in answer):
        failed.append({"at": ans_i, "ans": answer, "opts": list(options.keys()), "line": lines[ans_i]})
        continue

    # Question text: lines between prev answer and first option,
    # but exclude variant blocks that appear after prev answer
    # Layout:
    #   [prev ANS]
    #   [optional variants]
    #   [Q stem]
    #   [options]
    #   [ANS]
    stem_start = (prev_ans + 1) if prev_ans is not None else 0
    # If there are variants after prev_ans, stem starts after last variant block
    # Find last variant header in (stem_start, first_opt_i)
    variant_headers = [j for j in range(stem_start, first_opt_i) if is_variant_header(lines[j])]
    if variant_headers:
        # stem is after the last variant's content
        # last variant options end just before first_opt of MAIN
        # Actually if variant has options, first_opt_i found by walking back from answer
        # is MAIN's first option, so variant options are between variant header and main stem? 
        # Or variant options then main stem? Looking at data:
        #   ANS
        #   (Kiểu hỏi khác: Q? A B C D)   <- options of variant
        #   Next main Q stem
        #   A B C D
        #   ANS
        # So first_opt_i is main A. Variant options are BEFORE main stem text.
        # stem text is between end of variant options and first_opt_i.
        last_vh = variant_headers[-1]
        # find end of variant options
        k = last_vh + 1
        while k < first_opt_i:
            if is_empty(lines[k]):
                k += 1
                continue
            if opt_re.match(lines[k]):
                k += 1
                continue
            # non-option: could be variant Q text after header, or main stem
            # if followed later by options still before first_opt, it's variant body
            # collect from first hard question after variant options
            break
        # walk k forward: skip remaining variant options
        while k < first_opt_i and (is_empty(lines[k]) or opt_re.match(lines[k])):
            k += 1
        # also skip variant-only short lines right after header before options
        # re-scan: parts from k to first_opt_i
        stem_start = k

    parts = []
    for j in range(stem_start, first_opt_i):
        if is_empty(lines[j]):
            continue
        if is_variant_header(lines[j]):
            continue
        if opt_re.match(lines[j]):
            continue
        if is_answer_line(lines[j]):
            continue
        parts.append(lines[j])

    question_text = clean_text(" ".join(parts))
    if question_text.startswith("(") and ")" not in question_text[-3:]:
        question_text = question_text.lstrip("(").strip()

    if not question_text:
        failed.append({"at": ans_i, "ans": answer, "opts": list(options.keys()), "reason": "no_stem"})
        continue

    primary = answer[0]
    q = {
        "id": 0,
        "question": question_text,
        "options": options,
        "answer": primary,
        "alternatives": [],
        "_ans_line": ans_i,
    }
    if len(answer) > 1:
        q["answers"] = list(answer)
    questions.append(q)

# ─── Attach variants that sit after each answer, before next question ───
for qi, q in enumerate(questions):
    ans_i = q["_ans_line"]
    next_ans = questions[qi + 1]["_ans_line"] if qi + 1 < len(questions) else n
    # region after answer until next answer
    region_start = ans_i + 1
    region_end = next_ans
    # find variant headers in region
    j = region_start
    while j < region_end:
        if is_variant_header(lines[j]):
            # end of this variant = next variant or next main stem options area
            k = j + 1
            while k < region_end and not is_variant_header(lines[k]):
                # stop before next main question options? 
                # next main stem is before its options; hard to know
                # use: until next variant or end region
                k += 1
            # trim: variant shouldn't include next main stem + options + answer
            # next main's first option is before next_ans
            # find first_opt of next main
            if qi + 1 < len(questions):
                nopts, nfirst = extract_options_ending_at(next_ans)
                # variant ends before next main stem = text before nfirst
                # actually stem text is before nfirst; variant is before stem
                # so variant ends when we hit look_like_hard_question that starts next stem
                end = k
                # tighter end: before nfirst, and before long stem lines of next Q
                t = j + 1
                end2 = j + 1
                while t < nfirst:
                    if is_variant_header(lines[t]):
                        break
                    if opt_re.match(lines[t]) or is_empty(lines[t]):
                        end2 = t + 1
                        t += 1
                        continue
                    # text line — if we're still in variant Q or after variant options,
                    # if this is next stem (long), stop BEFORE it
                    if look_like_hard_question(lines[t]) and t > j + 1:
                        # could be variant multi-line Q right after header
                        # if no options yet in variant, it's alt Q text
                        has_opt_before = any(opt_re.match(lines[x]) for x in range(j + 1, t))
                        if has_opt_before:
                            break
                        end2 = t + 1
                        t += 1
                        continue
                    end2 = t + 1
                    t += 1
                end = min(end, end2, nfirst)
            else:
                end = k

            alt = parse_alt_block(j, end, q)
            if alt and alt.get("question"):
                q["alternatives"].append(alt)
            j = end
            continue
        j += 1

# finalize
for q in questions:
    q.pop("_ans_line", None)

for idx, q in enumerate(questions, 1):
    q["id"] = idx
    if q.get("answers") == [q.get("answer")]:
        q.pop("answers", None)

print(f"Source: {src}")
print(f"Answer lines in source: {len(answer_idxs)}")
print(f"Main questions parsed: {len(questions)}")
print(f"Failed answer lines: {len(failed)}")
print("option counts:", dict(Counter(len(q["options"]) for q in questions)))
print("answers:", dict(Counter(q["answer"] for q in questions)))
print("with alternatives:", sum(1 for q in questions if q.get("alternatives")))
print("multi-answer:", sum(1 for q in questions if q.get("answers")))

if len(questions) != 526:
    print(f"WARNING: expected 526, got {len(questions)}")
else:
    print("OK: exactly 526 main questions")

with open("questions.json", "w", encoding="utf-8") as f:
    json.dump(questions, f, ensure_ascii=False, indent=2)
with open("questions.js", "w", encoding="utf-8") as f:
    f.write("// Auto-generated — 526 main questions; kiểu hỏi khác only as alternatives\n")
    f.write("window.QUIZ_QUESTIONS = ")
    json.dump(questions, f, ensure_ascii=False)
    f.write(";\n")
print("Wrote questions.json + questions.js")
if failed:
    print("Failures:")
    for fitem in failed[:20]:
        print(" ", fitem)
