# -*- coding: utf-8 -*-
"""
Sinh giải thích RÕ, CỤ THỂ cho từng câu quiz MLN.
Không dùng câu khuôn sáo «có thể đúng trong ngữ cảnh khác».
"""
from __future__ import annotations

import json
import re
import sys
from typing import Dict, List, Optional, Tuple

sys.stdout.reconfigure(encoding="utf-8")


def N(s: str) -> str:
    s = (s or "").lower()
    s = s.replace("é", "e").replace("è", "e")  # light normalize
    s = re.sub(r"\s+", " ", s).strip()
    return s


def letters_of(q) -> List[str]:
    if q.get("answers"):
        return [str(x) for x in q["answers"]]
    return [str(q["answer"])] if q.get("answer") else []


def is_negation(stem: str) -> bool:
    s = N(stem)
    keys = [
        "không phải",
        "không đúng",
        "sai ",
        "sai.",
        "sai,",
        "chọn phương án sai",
        "ý không đúng",
        "mệnh đề nào sau đây là ý không đúng",
        "nhận xét nào là không đúng",
        "đâu không",
        "không thuộc",
        "ngoại trừ",
        "loại trừ",
        "trừ ra",
        "sai vai trò",
        "sai về",
    ]
    # careful: "sai" alone matches too much; use phrases
    if any(k in s for k in keys):
        return True
    if s.startswith("sai ") or " phương án sai" in s:
        return True
    return False


def is_multi(stem: str, corrects: List[str]) -> bool:
    if len(corrects) > 1:
        return True
    s = N(stem)
    return any(
        k in s
        for k in (
            "chọn nhiều",
            "chọn 2",
            "chọn 3",
            "chọn hai",
            "chọn ba",
            "chọn các",
            "nhiều phương án",
        )
    )


# ─────────────────── Topic knowledge ───────────────────
# Each topic: keywords on stem, builder(stem, opts, corrects) -> (whyCorrect, whyWrong)

def topic_cmcn1_count(stem, opts, corrects):
    why = (
        "Khi nghiên cứu CMCN lần thứ nhất, C. Mác khái quát quy luật phát triển qua "
        "**ba giai đoạn**: (1) hiệp tác đơn giản, (2) công trường thủ công, (3) đại công nghiệp cơ khí. "
        "Vì vậy đáp án đúng là số giai đoạn = 3."
    )
    wrong = {}
    for L, t in opts.items():
        if L in corrects:
            continue
        wrong[L] = (
            f"«{t}» sai vì Mác không khái quát CMCN I thành số giai đoạn này. "
            "Chuỗi chuẩn chỉ có ba nấc: hiệp tác đơn giản → công trường thủ công → đại công nghiệp."
        )
    return why, wrong


def topic_cmcn1_stages(stem, opts, corrects):
    why = (
        "Ba giai đoạn CMCN lần thứ nhất theo Mác là: "
        "**hiệp tác đơn giản → công trường thủ công → đại công nghiệp**. "
        "Đáp án đúng nêu đúng trật tự và nội dung các giai đoạn đó."
    )
    wrong = {}
    for L, t in opts.items():
        if L in corrects:
            continue
        tl = N(t)
        if "lao động thủ công" in tl and "phức tạp" in tl:
            wrong[L] = (
                f"«{t}» nhầm: giai đoạn giữa không phải «lao động thủ công / lao động phức tạp» "
                "mà là **công trường thủ công** (phân công trong xưởng, vẫn dựa công cụ thủ công)."
            )
        elif "công nghiệp hóa" in tl and "đại công nghiệp" not in tl:
            wrong[L] = (
                f"«{t}» dùng «công nghiệp hóa» chung chung, không đúng thuật ngữ giai đoạn thứ ba "
                "là **đại công nghiệp** (cơ khí hóa bằng máy móc)."
            )
        elif "sản xuất thủ công" in tl or "sản xuất hiện đại" in tl:
            wrong[L] = (
                f"«{t}» diễn đạt mơ hồ («sản xuất thủ công / hiện đại»), không trùng ba phạm trù "
                "Mác dùng: hiệp tác đơn giản, công trường thủ công, đại công nghiệp."
            )
        else:
            wrong[L] = f"«{t}» không khớp chuỗi ba giai đoạn chuẩn của Mác về CMCN I."
    return why, wrong


def topic_kvi_kvii(stem, opts, corrects):
    why = (
        "Trong tái sản xuất tư bản xã hội, Marx chia nền kinh tế thành **hai khu vực**: "
        "**KVI** sản xuất **tư liệu sản xuất**; **KVII** sản xuất **tư liệu tiêu dùng**. "
        "Đây là sơ đồ để phân tích điều kiện cân bằng tái sản xuất giản đơn và mở rộng."
    )
    wrong = {}
    for L, t in opts.items():
        if L in corrects:
            continue
        tl = N(t)
        if "công nghiệp" in tl and "nông nghiệp" in tl:
            wrong[L] = f"«{t}» chia theo ngành (công nghiệp/nông nghiệp), không phải cách Marx chia theo công dụng sản phẩm (TLSX/TLTD)."
        elif "máy móc" in tl:
            wrong[L] = f"«{t}» thu hẹp KVI chỉ còn «máy móc»; KVI gồm mọi tư liệu sản xuất, không chỉ máy."
        else:
            wrong[L] = f"«{t}» gán sai nội dung KVI/KVII so với định nghĩa Marx (TLSX / TLTD)."
    return why, wrong


def topic_dia_to_ii(stem, opts, corrects):
    why = (
        "**Địa tô chênh lệch II** nảy sinh khi nhà tư bản **thâm canh** (đầu tư thêm tư bản trên cùng một diện tích đất), "
        "tạo ra sản lượng vượt mức trên đất đang canh tác. Khác địa tô chênh lệch I gắn với độ màu mỡ tự nhiên / vị trí."
    )
    wrong = {}
    for L, t in opts.items():
        if L in corrects:
            continue
        tl = N(t)
        if "màu mỡ" in tl or "vị trí" in tl or "trung bình" in tl:
            wrong[L] = (
                f"«{t}» thuộc logic **địa tô chênh lệch I** (chênh lệch do điều kiện tự nhiên/vị trí đất), "
                "không phải CL II (thâm canh, đầu tư thêm)."
            )
        else:
            wrong[L] = f"«{t}» không mô tả đúng điều kiện hình thành địa tô chênh lệch II."
    return why, wrong


def topic_dia_to_i(stem, opts, corrects):
    why = (
        "**Địa tô chênh lệch I** thu trên đất có độ màu mỡ tốt hơn hoặc vị trí thuận lợi hơn so với đất xấu nhất "
        "đang được canh tác (trong điều kiện thâm canh chưa là nhân tố chính). "
        "Khi đáp án là «cả ba/cả A–C», nghĩa là CL I có thể gắn màu mỡ trung bình–tốt và vị trí."
    )
    wrong = {}
    for L, t in opts.items():
        if L in corrects:
            continue
        wrong[L] = f"«{t}» không bao quát đủ các căn cứ tạo địa tô chênh lệch I theo cách hỏi của câu này."
    return why, wrong


def topic_phan_cong_1(stem, opts, corrects):
    why = (
        "**Đại phân công lao động xã hội lần thứ nhất**: **chăn nuôi tách khỏi trồng trọt** "
        "(nông nghiệp phân hóa thành các ngành). Đây là bước mở đầu cho trao đổi sản phẩm thường xuyên hơn."
    )
    wrong = {}
    for L, t in opts.items():
        if L in corrects:
            continue
        tl = N(t)
        if "thủ công" in tl:
            wrong[L] = f"«{t}» là nội dung **lần 2** (thủ công nghiệp tách khỏi nông nghiệp), không phải lần 1."
        elif "thương" in tl:
            wrong[L] = f"«{t}» gắn **lần 3** (thương nghiệp ra đời), không phải lần 1."
        elif "đại công nghiệp" in tl or "công nghiệp tách" in tl:
            wrong[L] = f"«{t}» thuộc giai đoạn công nghiệp hóa / phân công sau này, không phải lần phân công thứ nhất."
        else:
            wrong[L] = f"«{t}» đảo chiều hoặc sai nội dung lần phân công thứ nhất."
    return why, wrong


def topic_phan_cong_2(stem, opts, corrects):
    why = (
        "**Đại phân công LĐXH lần thứ hai**: **thủ công nghiệp tách khỏi nông nghiệp**, "
        "tạo điều kiện cho sản xuất hàng hóa và thị trường phát triển mạnh hơn."
    )
    wrong = {}
    for L, t in opts.items():
        if L in corrects:
            continue
        tl = N(t)
        if "chăn nuôi" in tl or "trồng trọt" in tl:
            wrong[L] = f"«{t}» là lần 1 (chăn nuôi/trồng trọt), không phải lần 2."
        elif "thương" in tl:
            wrong[L] = f"«{t}» là lần 3 (thương nghiệp), không phải lần 2."
        else:
            wrong[L] = f"«{t}» không đúng nội dung lần phân công thứ hai."
    return why, wrong


def topic_phan_cong_3(stem, opts, corrects):
    why = (
        "**Đại phân công LĐXH lần thứ ba**: **ngành thương nghiệp ra đời** "
        "(tách chức năng lưu thông, buôn bán khỏi sản xuất trực tiếp)."
    )
    wrong = {}
    for L, t in opts.items():
        if L in corrects:
            continue
        tl = N(t)
        if "chăn nuôi" in tl or "trồng trọt" in tl:
            wrong[L] = f"«{t}» thuộc lần 1."
        elif "thủ công" in tl:
            wrong[L] = f"«{t}» thuộc lần 2."
        else:
            wrong[L] = f"«{t}» không phải nội dung lần phân công thứ ba."
    return why, wrong


def topic_cntb_dac_trung(stem, opts, corrects):
    why = (
        "Đặc trưng CNTB: **sở hữu tư nhân** về tư liệu sản xuất, sản xuất hàng hóa vì lợi nhuận, "
        "tích lũy tư bản, quan hệ làm thuê, thị trường và cạnh tranh. "
        "«Sở hữu TLSX thuộc về nhà nước» không phải đặc trưng CNTB (gần mô hình công hữu/XHCN hơn)."
    )
    wrong = {}
    for L, t in opts.items():
        if L in corrects:
            continue
        wrong[L] = (
            f"«{t}» **đúng là** đặc trưng/biểu hiện của CNTB. "
            "Câu hỏi tìm cái *không phải* đặc trưng, nên không chọn phương án này."
        )
    return why, wrong


def topic_toan_cau_phan_chia_tt(stem, opts, corrects):
    why = (
        "Ở giai đoạn CNTB độc quyền, các liên minh độc quyền phân chia thị trường ngày càng vượt biên giới quốc gia. "
        "Biểu hiện **mới** nổi bật là **xu hướng toàn cầu hóa** phân chia thị trường (cùng xuất khẩu tư bản, TNC…), "
        "chứ không chỉ phân chia trong phạm vi một nước."
    )
    wrong = {}
    for L, t in opts.items():
        if L in corrects:
            continue
        tl = N(t)
        if "đa quốc gia" in tl:
            wrong[L] = (
                f"«{t}» nói đến hình thức tổ chức (công ty/đa quốc gia), "
                "không phải đúng «biểu hiện mới của sự *phân chia thị trường*» theo đáp án chuẩn (toàn cầu hóa)."
            )
        elif "trong nhà nước" in tl or "trong nước" in tl:
            wrong[L] = (
                f"«{t}» phản ánh phạm vi nội địa/quan hệ nhà nước–độc quyền, "
                "không phải nét mới mang tính toàn cầu của phân chia thị trường."
            )
        elif "khu vực" in tl:
            wrong[L] = (
                f"«{t}» (khu vực hóa) có xảy ra nhưng theo đáp án giáo trình, "
                "biểu hiện mới được nhấn mạnh của phân chia thị trường liên minh độc quyền là **toàn cầu hóa**."
            )
        else:
            wrong[L] = f"«{t}» không phải đáp án được chọn cho biểu hiện mới của phân chia thị trường."
    return why, wrong


def topic_cmcn_vai_tro_sai(stem, opts, corrects):
    # answer B is "wrong role"
    why = (
        "Câu hỏi **chọn phương án SAI** về vai trò CMCN. "
        "CMCN trước hết cách mạng hóa **lực lượng sản xuất** (công cụ, kỹ thuật, năng suất); "
        "quan hệ sản xuất thay đổi *do* LLSX biến đổi, nhưng cách diễn đạt «thúc đẩy các QHSX mới ra đời» "
        "là phương án được giáo trình coi là **sai/không chính xác** trong bộ đáp án này. "
        "Các phương án còn lại được xem là đúng/hợp lý hơn."
    )
    wrong = {}
    for L, t in opts.items():
        if L in corrects:
            continue
        wrong[L] = (
            f"«{t}» được coi là **đúng** về vai trò/tác động của CMCN "
            "(thúc đẩy LLSX, hoàn thiện QHSX, đổi mới quản trị…). "
            "Vì câu tìm cái SAI nên không chọn."
        )
    return why, wrong


def topic_ban_tay_vo_hinh(stem, opts, corrects):
    why = (
        "**Bàn tay vô hình** (Adam Smith): trong kinh tế thị trường, cá nhân theo đuổi lợi ích riêng "
        "nhưng thông qua trao đổi và giá cả, nguồn lực được điều phối, cung–cầu được điều chỉnh, "
        "thường **không cần** nhà nước can thiệp chi tiết vào từng giao dịch. "
        "Các phương án đúng làm rõ các khía cạnh: hiệu quả phân bổ, điều tiết cung cầu, động cơ lợi ích cá nhân."
    )
    wrong = {}
    for L, t in opts.items():
        if L in corrects:
            continue
        wrong[L] = (
            f"«{t}» không thuộc tập hợp các ý đúng cần chọn về «bàn tay vô hình» trong câu này "
            "(sai nội dung, cực đoan, hoặc không phải luận điểm Smith)."
        )
    return why, wrong


def topic_canh_tranh_doc_quyen(stem, opts, corrects):
    why = (
        "Trong CNTB độc quyền, cạnh tranh **không bị thủ tiêu** vì cạnh tranh là **quy luật khách quan** "
        "của kinh tế hàng hóa: còn sản xuất hàng hóa, còn mâu thuẫn lợi ích, còn cạnh tranh "
        "(giữa các độc quyền, trong nội bộ, với ngoài độc quyền…)."
    )
    wrong = {}
    for L, t in opts.items():
        if L in corrects:
            continue
        wrong[L] = (
            f"«{t}» có thể là một **biểu hiện** cạnh tranh vẫn tồn tại, "
            "nhưng chưa phải lý do mang tính quy luật/khách quan nhất mà đáp án chuẩn nhấn mạnh."
        )
    return why, wrong


def topic_gia_ca_doc_quyen(stem, opts, corrects):
    why = (
        "Giá cả độc quyền là công cụ để tổ chức độc quyền **chiếm đoạt giá trị thặng dư** "
        "(và một phần giá trị tạo ra ngoài khu vực độc quyền) thông qua giá bán cao / giá mua thấp. "
        "Đó là bản chất bóc lột trong quan hệ giá cả độc quyền."
    )
    wrong = {}
    for L, t in opts.items():
        if L in corrects:
            continue
        wrong[L] = (
            f"«{t}» là hệ quả hoặc mục tiêu phụ; bản chất việc dùng giá độc quyền "
            "được khái quát là chiếm đoạt giá trị thặng dư/lợi ích của chủ thể khác."
        )
    return why, wrong


def topic_co_che_dqnn(stem, opts, corrects):
    why = (
        "Cơ chế kinh tế CNTB độc quyền nhà nước thường được khái quát là sự kết hợp: "
        "**cơ chế thị trường + độc quyền tư nhân + sự can thiệp/điều tiết của nhà nước**."
    )
    wrong = {}
    for L, t in opts.items():
        if L in corrects:
            continue
        tl = N(t)
        if "tài phiệt" in tl:
            wrong[L] = f"«{t}» nhấn «nhà tài phiệt» thay vì cặp thị trường–độc quyền tư nhân–nhà nước theo đáp án chuẩn."
        elif "chỉ" in tl or ("thị trường" in tl and "nhà nước" not in tl):
            wrong[L] = f"«{t}» thiếu nhân tố nhà nước hoặc độc quyền — không đủ bộ ba của cơ chế ĐQNN."
        else:
            wrong[L] = f"«{t}» không đủ/không đúng cấu trúc cơ chế kinh tế độc quyền nhà nước."
    return why, wrong


def topic_tien_de_kt_thi_truong(stem, opts, corrects):
    why = (
        "Kinh tế thị trường ra đời và phát triển trên tiền đề **sản xuất hàng hóa** "
        "(có phân công LĐXH và sự tách biệt kinh tế giữa các chủ thể) **và trao đổi hàng hóa** thường xuyên. "
        "Thiếu một trong hai thì chưa thành kinh tế thị trường đầy đủ."
    )
    wrong = {}
    for L, t in opts.items():
        if L in corrects:
            continue
        wrong[L] = (
            f"«{t}» chỉ nêu một yếu tố đơn lẻ (sản xuất / trao đổi / «thị trường» chung chung), "
            "không đủ cặp tiền đề «sản xuất và trao đổi hàng hóa»."
        )
    return why, wrong


def topic_kt_thi_truong_hinh_thanh(stem, opts, corrects):
    why = (
        "Kinh tế thị trường **bắt đầu hình thành từ xã hội phong kiến** (khi sản xuất hàng hóa và trao đổi phát triển), "
        "rồi trở thành phổ biến ở CNTB — không phải chỉ xuất hiện từ CNTB hay XHCN."
    )
    wrong = {}
    for L, t in opts.items():
        if L in corrects:
            continue
        wrong[L] = (
            f"«{t}» sai giai đoạn: thị trường/hàng hóa manh nha từ trước CNTB; "
            "CNTB làm cho kinh tế thị trường thống trị, chứ không phải điểm khởi đầu duy nhất theo đáp án này."
        )
    return why, wrong


def topic_hang_hoa_dieu_kien(stem, opts, corrects):
    why = (
        "Hai điều kiện ra đời và tồn tại của sản xuất hàng hóa: "
        "(1) **phân công lao động xã hội**, (2) **sự tách biệt về kinh tế** giữa các chủ thể "
        "(thường gắn chế độ sở hữu khiến sản phẩm thuộc về chủ thể khác nhau, phải trao đổi)."
    )
    wrong = {}
    for L, t in opts.items():
        if L in corrects:
            continue
        wrong[L] = (
            f"«{t}» chỉ là một biểu hiện/bộ phận hoặc chưa đủ cặp điều kiện "
            "(phân công LĐXH + tách biệt kinh tế giữa các chủ thể)."
        )
    return why, wrong


def topic_tach_biet_so_huu(stem, opts, corrects):
    why = (
        "Sự tách biệt kinh tế giữa các chủ thể sản xuất dựa trên **sự tách biệt về quyền sở hữu** "
        "(sản phẩm thuộc về chủ thể khác nhau), chứ không chỉ khác nhau về tổ chức hay vai trò kỹ thuật."
    )
    wrong = {}
    for L, t in opts.items():
        if L in corrects:
            continue
        wrong[L] = f"«{t}» không phải cơ sở quyết định; cơ sở là **quyền sở hữu** tách biệt."
    return why, wrong


def topic_cmcn2_time(stem, opts, corrects):
    why = (
        "CMCN lần thứ hai gắn điện–thép–hóa chất, diễn ra khoảng **nửa cuối thế kỷ XIX đến đầu thế kỷ XX** "
        "(cũng có cách nói «từ giữa XIX đến giữa XX» tùy bộ đề). "
        "Cần khớp đúng đáp án của từng câu trong ngân hàng."
    )
    wrong = {}
    for L, t in opts.items():
        if L in corrects:
            continue
        wrong[L] = (
            f"«{t}» lệch mốc: hoặc quá sớm (nhầm CMCN I ~ giữa XVIII–XIX), "
            "hoặc sai nửa đầu/nửa cuối thế kỷ so với CMCN II."
        )
    return why, wrong


def topic_w_value(stem, opts, corrects):
    why = (
        "Giá trị hàng hóa (W) theo Marx: **W = c + v + m** "
        "(tư bản bất biến + tư bản khả biến + giá trị thặng dư). "
        "Đây là cấu trúc giá trị hàng hóa trong CNTB."
    )
    wrong = {}
    for L, t in opts.items():
        if L in corrects:
            continue
        tl = N(t).replace(" ", "")
        if "c+v" in tl and "m" not in tl:
            wrong[L] = f"«{t}» thiếu **m** (giá trị thặng dư) — chỉ gần chi phí tư bản, không đủ giá trị hàng hóa."
        elif "v+m" in tl and "c" not in tl:
            wrong[L] = f"«{t}» thiếu **c** (hao phí TLSX chuyển vào sản phẩm)."
        elif "/" in t:
            wrong[L] = f"«{t}» sai công thức (không chia (c+v)/m để tính W)."
        else:
            wrong[L] = f"«{t}» không đúng công thức W = c + v + m."
    return why, wrong


def topic_tich_luy(stem, opts, corrects):
    why = (
        "**Tích lũy tư bản** là biến một phần **giá trị thặng dư** thành tư bản thêm "
        "(tái sản xuất mở rộng), không phải chỉ «tích trữ» consum hoặc tư liệu tiêu dùng."
    )
    wrong = {}
    for L, t in opts.items():
        if L in corrects:
            continue
        wrong[L] = f"«{t}» sai bản chất tích lũy (nhầm tiêu dùng, lưu thông, hoặc không gắn tư bản hóa m)."
    return why, wrong


def topic_tuan_hoan(stem, opts, corrects):
    why = (
        "Tuần hoàn tư bản công nghiệp: **Lưu thông → Sản xuất → Lưu thông** "
        "(T–H…SX…H'–T'), tư bản lần lượt mang hình thái tiền tệ, sản xuất, hàng hóa."
    )
    wrong = {}
    for L, t in opts.items():
        if L in corrects:
            continue
        wrong[L] = f"«{t}» sai thứ tự hoặc thiếu/thừa giai đoạn so với sơ đồ tuần hoàn chuẩn."
    return why, wrong


def topic_lao_dong_phuc_tap(stem, opts, corrects):
    why = (
        "Lao động phức tạp là lao động đã được **đào tạo, huấn luyện**, trong cùng thời gian tạo ra **nhiều giá trị hơn** "
        "lao động giản đơn. Cách hiểu chỉ gói gọn «lao động trí tuệ trình độ cao» dễ bị coi là **không đúng/thiếu**."
    )
    wrong = {}
    for L, t in opts.items():
        if L in corrects:
            continue
        wrong[L] = f"«{t}» là nhận định **đúng** về lao động phức tạp; câu hỏi tìm ý không đúng nên loại."
    return why, wrong


TOPICS = [
    # (predicate on stem, builder)
    (lambda s: "mấy giai đoạn" in s and "cách mạng công nghiệp lần thứ nhất" in s, topic_cmcn1_count),
    (lambda s: "giai đoạn phát triển đó là" in s and ("mác" in s or "cách mạng công nghiệp" in s), topic_cmcn1_stages),
    (lambda s: "hiệp tác đơn giản" in s or ("công trường thủ công" in s and "đại công nghiệp" in s), topic_cmcn1_stages),
    (lambda s: "kvi" in s or "hai khu vực" in s or "tái sản xuất tư bản xã hội" in s, topic_kvi_kvii),
    (lambda s: "địa tô chênh lệch ii" in s or "địa tô chênh lệch 2" in s, topic_dia_to_ii),
    (lambda s: "địa tô" in s and ("chênh lệch i" in s or "chênh lệch 1" in s or "chênh lệch chính i" in s), topic_dia_to_i),
    (lambda s: "phân công" in s and "lần thứ nhất" in s, topic_phan_cong_1),
    (lambda s: "phân công" in s and "lần thứ hai" in s, topic_phan_cong_2),
    (lambda s: "phân công" in s and "lần thứ ba" in s, topic_phan_cong_3),
    (lambda s: "không phải đặc trưng của chủ nghĩa tư bản" in s, topic_cntb_dac_trung),
    (lambda s: "phân chia thị trường" in s and "độc quyền" in s, topic_toan_cau_phan_chia_tt),
    (lambda s: "phương án sai" in s and "cách mạng công nghiệp" in s, topic_cmcn_vai_tro_sai),
    (lambda s: "bàn tay vô hình" in s, topic_ban_tay_vo_hinh),
    (lambda s: "cạnh tranh không bị thủ tiêu" in s or ("độc quyền" in s and "cạnh tranh không" in s), topic_canh_tranh_doc_quyen),
    (lambda s: "giá cả độc quyền" in s, topic_gia_ca_doc_quyen),
    (lambda s: "cơ chế kinh tế của độc quyền nhà nước" in s or ("cơ chế" in s and "độc quyền nhà nước" in s), topic_co_che_dqnn),
    (lambda s: "tiền đề" in s and "kinh tế thị trường" in s, topic_tien_de_kt_thi_truong),
    (lambda s: "kinh tế thị trường đã hình thành trong xã hội" in s, topic_kt_thi_truong_hinh_thanh),
    (lambda s: "điều kiện" in s and ("sản xuất hàng hóa" in s or "ra đời và tồn tại" in s), topic_hang_hoa_dieu_kien),
    (lambda s: "tách biệt về mặt kinh tế" in s or "tách biệt về kinh tế" in s, topic_tach_biet_so_huu),
    (lambda s: "cách mạng công nghiệp lần thứ hai" in s and ("giai đoạn" in s or "thời gian" in s), topic_cmcn2_time),
    (lambda s: "công thức" in s and ("giá trị hàng hóa" in s or "gọi w" in s), topic_w_value),
    (lambda s: "w=" in s.replace(" ", "") or "w =" in s, topic_w_value),
    (lambda s: "tích lũy tư bản là gì" in s or (s.startswith("tích lũy tư bản") and "là gì" in s), topic_tich_luy),
    (lambda s: "tuần hoàn" in s and "tư bản" in s, topic_tuan_hoan),
    (lambda s: "lao động phức tạp" in s and ("không đúng" in s or "sai" in s), topic_lao_dong_phuc_tap),
]


def contrast_wrong(L: str, text: str, correct_join: str, neg: bool) -> str:
    """Specific fallback: always name the content difference."""
    if neg:
        return (
            f"**{L}. {text}** — Đây là nội dung **đúng/hợp lý** trong lý thuyết. "
            f"Câu hỏi đang tìm phương án SAI/KHÔNG PHẢI, trong khi đáp án sai cần chọn là: {correct_join}. "
            f"Vì vậy không chọn {L}."
        )
    return (
        f"**{L}. {text}** — Không khớp yêu cầu đề. "
        f"So với đáp án đúng ({correct_join}), phương án này hoặc nhầm khái niệm, "
        f"nhầm giai đoạn/phạm vi, hoặc chỉ đúng một phần/không đủ điều kiện. "
        f"Loại {L}."
    )


def build_generic(stem: str, opts: Dict[str, str], corrects: List[str]) -> Tuple[str, Dict[str, str]]:
    neg = is_negation(stem)
    multi = is_multi(stem, corrects)
    correct_parts = [f"{L}. {opts.get(L, '')}" for L in corrects if L in opts]
    correct_join = " | ".join(correct_parts)

    if multi:
        why = (
            f"Đây là câu **chọn nhiều đáp án**. Các phương án đúng là **{', '.join(corrects)}**:\n"
            + "".join(f"• {p}\n" for p in correct_parts)
            + "Cần chọn **đủ** các ý trên (và chỉ các ý đó) vì chúng cùng thỏa yêu cầu đề; "
            "các ý còn lại sai hoặc ngoài phạm vi cần chọn."
        )
    elif neg:
        why = (
            f"Đề yêu cầu tìm phương án **SAI / KHÔNG ĐÚNG / KHÔNG PHẢI**. "
            f"Đáp án là **{', '.join(corrects)}**: {correct_join}. "
            f"Đây là ý không chính xác hoặc không thuộc đặc điểm/đúng bản chất đang hỏi; "
            f"các phương án còn lại mới là nội dung đúng."
        )
    else:
        # richer generic
        why = (
            f"**Đáp án {', '.join(corrects)}**: {correct_join}. "
            f"Trong hệ thống kiến thức kinh tế chính trị (và các chủ đề nhà nước–thị trường–CNH liên quan), "
            f"đây là phương án phản ánh đúng bản chất/định nghĩa/mốc sự kiện mà câu hỏi đang yêu cầu. "
            f"Các lựa chọn khác lệch khái niệm, lệch giai đoạn, hoặc mô tả hiện tượng phụ không phải trọng tâm đáp án."
        )

    wrong = {}
    for L, t in opts.items():
        if L in corrects:
            continue
        wrong[L] = contrast_wrong(L, t, correct_join, neg)
    return why, wrong


def explain_one(q) -> dict:
    opts = dict(q.get("options") or {})
    corrects = letters_of(q)
    stem = q.get("question") or ""
    s = N(stem)

    # Also search option blob for topic hints
    blob = s + " " + N(" ".join(opts.values()))

    why_c, why_w = None, None
    for pred, builder in TOPICS:
        try:
            if pred(s) or pred(blob):
                why_c, why_w = builder(s, opts, corrects)
                break
        except Exception:
            continue

    if why_c is None:
        why_c, why_w = build_generic(stem, opts, corrects)
    else:
        # ensure all wrong letters filled
        for L, t in opts.items():
            if L not in corrects and L not in why_w:
                correct_join = " | ".join(f"{x}. {opts.get(x, '')}" for x in corrects)
                why_w[L] = contrast_wrong(L, t, correct_join, is_negation(stem))

    # Clean markdown-ish for UI (keep plain; UI escapes HTML)
    why_c = why_c.replace("**", "")
    why_w = {k: v.replace("**", "") for k, v in why_w.items()}

    return {"whyCorrect": why_c.strip(), "whyWrong": why_w}


def main():
    qs = json.load(open("questions.json", encoding="utf-8"))
    for q in qs:
        q["explanation"] = explain_one(q)
        for alt in q.get("alternatives") or []:
            mini = {
                "question": alt.get("question") or "",
                "options": alt.get("options") or {},
                "answer": alt.get("answer"),
            }
            if alt.get("answer") and not mini.get("answers"):
                # single
                pass
            if not mini["options"] and q.get("options"):
                mini["options"] = q["options"]
                mini["answer"] = alt.get("answer") or q.get("answer")
            if mini["options"]:
                alt["explanation"] = explain_one(mini)

    with open("questions.json", "w", encoding="utf-8") as f:
        json.dump(qs, f, ensure_ascii=False, indent=2)
    with open("questions.js", "w", encoding="utf-8") as f:
        f.write("// 526 questions + detailed explanations\n")
        f.write("window.QUIZ_QUESTIONS = ")
        json.dump(qs, f, ensure_ascii=False)
        f.write(";\n")

    # sample quality check
    for i in [0, 1, 2, 3, 15]:
        e = qs[i]["explanation"]
        print("====", qs[i]["id"], qs[i]["question"][:50])
        print("OK:", e["whyCorrect"][:180].replace("\n", " "))
        for L, t in list(e["whyWrong"].items())[:1]:
            print("W", L, ":", t[:140].replace("\n", " "))
    print("DONE", len(qs))


if __name__ == "__main__":
    main()
