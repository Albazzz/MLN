# -*- coding: utf-8 -*-
"""
Generate explanation blocks for each quiz question:
  whyCorrect: string
  whyWrong: { letter: string }
"""
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

qs = json.load(open("questions.json", encoding="utf-8"))


def norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def correct_letters(q):
    if q.get("answers"):
        return list(q["answers"])
    return [q["answer"]] if q.get("answer") else []


def detect_type(question):
    q = norm(question)
    if any(
        k in q
        for k in (
            "không phải",
            "không đúng",
            "sai",
            "không thuộc",
            "loại trừ",
            "ngoại trừ",
            "trừ",
            "không phải là",
            "đâu không",
            "chọn phương án sai",
            "ý không đúng",
            "mệnh đề nào sau đây là ý không đúng",
            "nhận xét nào là không đúng",
        )
    ):
        return "negation"  # correct option is the FALSE one
    if "chọn nhiều" in q or "chọn 2" in q or "chọn 3" in q or "chọn hai" in q or "chọn ba" in q:
        return "multi"
    if any(k in q for k in ("là gì", "hiểu là", "được hiểu", "khái niệm", "định nghĩa")):
        return "definition"
    if any(k in q for k in ("khi nào", "thời gian", "giai đoạn", "năm nào", "thế kỷ")):
        return "time"
    if any(k in q for k in ("ai là", "ai đã", "nhà kinh tế", "tác giả")):
        return "person"
    return "general"


def build_explanation(q):
    opts = q.get("options") or {}
    corrects = correct_letters(q)
    qtype = detect_type(q.get("question", ""))
    if len(corrects) > 1:
        qtype = "multi"

    correct_texts = [f"{L}. {opts.get(L, '')}" for L in corrects if L in opts]
    wrong_letters = [L for L in sorted(opts.keys()) if L not in corrects]

    # —— whyCorrect ——
    if qtype == "negation":
        why_correct = (
            "Câu hỏi yêu cầu tìm phương án SAI / KHÔNG ĐÚNG / KHÔNG PHẢI. "
            f"Đáp án đúng là {', '.join(corrects)} — đây là nội dung không phù hợp (hoặc sai) so với lý thuyết: "
            + "; ".join(correct_texts)
            + ". Các phương án còn lại là nội dung đúng nên bị loại."
        )
    elif qtype == "multi":
        why_correct = (
            "Đây là câu chọn nhiều phương án. Các đáp án đúng gồm "
            f"{', '.join(corrects)}: "
            + " | ".join(correct_texts)
            + ". Cần chọn đủ và đúng tập phương án trên theo giáo trình kinh tế chính trị."
        )
    elif qtype == "definition":
        why_correct = (
            f"Đáp án {', '.join(corrects)} khớp định nghĩa / bản chất của khái niệm trong câu hỏi: "
            + "; ".join(correct_texts)
            + ". Đây là cách diễn đạt chuẩn nhất trong hệ thống lý luận được học."
        )
    elif qtype == "time":
        why_correct = (
            f"Đáp án {', '.join(corrects)} đúng về mốc thời gian / giai đoạn lịch sử: "
            + "; ".join(correct_texts)
            + ". Các mốc khác lệch giai đoạn hoặc nhầm cuộc cách mạng / sự kiện."
        )
    elif qtype == "person":
        why_correct = (
            f"Đáp án {', '.join(corrects)} chỉ đúng tác giả / nhân vật gắn với học thuyết hoặc sự kiện: "
            + "; ".join(correct_texts)
            + "."
        )
    else:
        why_correct = (
            f"Đáp án {', '.join(corrects)} đúng vì phản ánh chính xác nội dung câu hỏi: "
            + "; ".join(correct_texts)
            + ". Đây là kết luận phù hợp với kinh tế chính trị Mác – Lênin và các chủ đề liên quan trong giáo trình."
        )

    # —— whyWrong ——
    why_wrong = {}
    for L in wrong_letters:
        text = opts.get(L, "")
        if qtype == "negation":
            why_wrong[L] = (
                f"Phương án {L} là nội dung ĐÚNG (hoặc phù hợp lý thuyết): «{text}». "
                "Vì câu hỏi tìm cái SAI/KHÔNG PHẢI nên không chọn phương án này."
            )
        elif qtype == "multi":
            why_wrong[L] = (
                f"Phương án {L} không thuộc tập đáp án đúng: «{text}». "
                "Nội dung này sai, không liên quan, hoặc không được tính trong các phương án cần chọn."
            )
        elif qtype == "definition":
            why_wrong[L] = (
                f"Phương án {L} sai hoặc không đủ/không chính xác về định nghĩa: «{text}». "
                "Có thể nhầm sang khái niệm gần, phạm vi hẹp hơn, hoặc mâu thuẫn bản chất."
            )
        elif qtype == "time":
            why_wrong[L] = (
                f"Phương án {L} sai mốc thời gian/giai đoạn: «{text}». "
                "Dễ nhầm với cuộc cách mạng công nghiệp hoặc sự kiện lịch sử khác."
            )
        elif qtype == "person":
            why_wrong[L] = (
                f"Phương án {L} chỉ nhầm nhân vật/tác giả: «{text}». "
                "Người này gắn với học thuyết hoặc thời kỳ khác, không khớp câu hỏi."
            )
        else:
            why_wrong[L] = (
                f"Phương án {L} không đúng với yêu cầu câu hỏi: «{text}». "
                "Có thể đúng trong ngữ cảnh khác, nhưng không phải đáp án của câu này."
            )

    # Enrich a few well-known items by id/keyword for higher quality
    why_correct, why_wrong = enrich_special(q, corrects, opts, why_correct, why_wrong)

    return {
        "whyCorrect": why_correct,
        "whyWrong": why_wrong,
    }


def enrich_special(q, corrects, opts, why_correct, why_wrong):
    """Override templates for frequent textbook items when we can be specific."""
    stem = norm(q.get("question", ""))
    ans = corrects[0] if corrects else ""

    overrides = []

    # CMCN I stages count
    if "mấy giai đoạn" in stem and "cách mạng công nghiệp lần thứ nhất" in stem:
        why_correct = (
            "C. Mác khái quát quy luật CMCN lần thứ nhất qua ba giai đoạn: "
            "hiệp tác đơn giản → công trường thủ công → đại công nghiệp cơ khí. "
            "Vì vậy đáp án đúng là C (Ba giai đoạn)."
        )
        for L, t in opts.items():
            if L == "C":
                continue
            why_wrong[L] = f"«{t}» sai số giai đoạn; Mác chỉ ra ba giai đoạn, không phải {t.lower()}."

    if "giai đoạn phát triển đó là" in stem or (
        "hiệp tác đơn giản" in " ".join(opts.values()).lower() and "đại công nghiệp" in " ".join(opts.values()).lower()
    ):
        if ans == "D" or (opts.get("D") and "đại công nghiệp" in opts.get("D", "").lower()):
            pass  # handled when this is main Q

    # KVI KVII
    if "hai khu vực" in stem or "kvi" in stem:
        why_correct = (
            "Khi nghiên cứu tái sản xuất tư bản xã hội, Marx chia nền kinh tế thành: "
            "KVI — sản xuất tư liệu sản xuất; KVII — sản xuất tư liệu tiêu dùng. "
            f"Đáp án đúng: {ans}."
        )
        for L, t in opts.items():
            if L in corrects:
                continue
            why_wrong[L] = f"«{t}» phân chia khu vực không đúng cách Marx đặt vấn đề (TLSX / TLTD)."

    # Địa tô CL II
    if "địa tô chênh lệch ii" in stem or "địa tô chênh lệch 2" in stem:
        why_correct = (
            "Địa tô chênh lệch II thu được trên đất đã thâm canh (đầu tư thêm tư bản trên cùng diện tích). "
            f"Đáp án đúng: {ans}."
        )
        for L, t in opts.items():
            if L in corrects:
                continue
            why_wrong[L] = (
                f"«{t}» gắn với địa tô chênh lệch I (độ màu mỡ tự nhiên / vị trí), không phải CL II."
            )

    # Đặc trưng CNTB - sở hữu nhà nước
    if "không phải đặc trưng của chủ nghĩa tư bản" in stem:
        why_correct = (
            "Đặc trưng CNTB: sở hữu tư nhân về TLSX, tích lũy tư bản, trao đổi tự nguyện, thị trường cạnh tranh. "
            "«Quyền sở hữu TLSX thuộc về nhà nước» không phải đặc trưng CNTB (gần XHCN hơn). "
            f"Đáp án đúng: {ans}."
        )
        for L, t in opts.items():
            if L in corrects:
                continue
            why_wrong[L] = f"«{t}» là đặc trưng / biểu hiện đúng của CNTB, nên không phải đáp án «không phải»."

    # Bàn tay vô hình
    if "bàn tay vô hình" in stem:
        why_correct = (
            "Lý thuyết «bàn tay vô hình» của Adam Smith nhấn mạnh cơ chế thị trường tự điều chỉnh: "
            "người tham gia theo lợi ích riêng nhưng vô hình điều phối nguồn lực, điều chỉnh cung cầu, "
            "mà không cần can thiệp hành chính thường xuyên. Các phương án đúng phản ánh các khía cạnh đó."
        )
        for L, t in opts.items():
            if L in corrects:
                continue
            why_wrong[L] = (
                f"«{t}» không thuộc nội dung cốt lõi cần chọn của «bàn tay vô hình» trong câu này "
                "(sai hoặc không phải một trong các phương án đúng)."
            )

    # Phân công LĐ XH
    if "đại phân công lao động xã hội lần thứ nhất" in stem:
        why_correct = "Lần 1: chăn nuôi tách khỏi trồng trọt (nông nghiệp tách thành các ngành)."
        for L, t in opts.items():
            if L in corrects:
                continue
            why_wrong[L] = f"«{t}» là nội dung lần phân công khác (thường lần 2/3), không phải lần 1."
    if "đại phân công lao động xã hội lần thứ hai" in stem:
        why_correct = "Lần 2: thủ công nghiệp tách khỏi nông nghiệp."
        for L, t in opts.items():
            if L in corrects:
                continue
            why_wrong[L] = f"«{t}» không phải nội dung lần phân công thứ hai."
    if "đại phân công lao động xã hội lần thứ ba" in stem:
        why_correct = "Lần 3: ngành thương nghiệp ra đời (tách lưu thông khỏi sản xuất)."
        for L, t in opts.items():
            if L in corrects:
                continue
            why_wrong[L] = f"«{t}» không phải nội dung lần phân công thứ ba."

    return why_correct, why_wrong


# Apply to all questions
for q in qs:
    exp = build_explanation(q)
    q["explanation"] = exp
    # Also explain alternatives briefly if present
    for alt in q.get("alternatives") or []:
        if not alt.get("options") and not alt.get("answer"):
            continue
        # build mini question object
        mini = {
            "question": alt.get("question", ""),
            "options": alt.get("options") or {},
            "answer": alt.get("answer"),
            "answers": [alt["answer"]] if alt.get("answer") else [],
        }
        if not mini["options"] and q.get("options"):
            mini["options"] = q["options"]
            mini["answer"] = alt.get("answer") or q.get("answer")
        alt["explanation"] = build_explanation(mini)

with open("questions.json", "w", encoding="utf-8") as f:
    json.dump(qs, f, ensure_ascii=False, indent=2)

with open("questions.js", "w", encoding="utf-8") as f:
    f.write("// Auto-generated — 526 main questions + explanations\n")
    f.write("window.QUIZ_QUESTIONS = ")
    json.dump(qs, f, ensure_ascii=False)
    f.write(";\n")

print(f"Updated {len(qs)} questions with explanations")
sample = qs[0]["explanation"]
print("Sample Q1 whyCorrect:", sample["whyCorrect"][:120], "...")
print("Sample Q1 whyWrong keys:", list(sample["whyWrong"].keys()))
