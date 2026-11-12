"""
Orchestrator and Intent Router for H.E.R.M.E.S.

Routes user queries to appropriate specialized engines:
- CALC_GPA: Deterministic Academic Engine (R2)
- SCHEDULING: Deterministic Scheduler (R2)
- REGULATION_RAG: Retrieval Augmented Generation Engine (R3)
- EXTRACT_DEADLINE: AI Entity Extraction (R4)
- CLARIFY: System needs clarification (R5)
- REJECT: System rejects query due to policy violation or out-of-scope (R5/R7)
"""

from __future__ import annotations

import re
from typing import Any, Dict

# Constants for Intents
INTENT_CALC_GPA = "CALC_GPA"
INTENT_SCHEDULING = "SCHEDULING"
INTENT_REGULATION_RAG = "REGULATION_RAG"
INTENT_EXTRACT_DEADLINE = "EXTRACT_DEADLINE"
INTENT_CLARIFY = "CLARIFY"
INTENT_REJECT = "REJECT"

# Patterns for REJECT (Prompt injection, Non-goals: homework solving)
REJECT_PATTERNS = [
    r"bỏ qua (các )?chỉ dẫn",
    r"ignore (all )?previous instructions",
    r"system prompt",
    r"jailbreak",
    r"giải (hộ|giúp|dùm) (bài tập|đề thi|bài lab)",
    r"làm (hộ|giúp|dùm) (bài tập|đồ án|assignment)",
    r"viết (code|chương trình) (hộ|giúp|dùm|thay) mình",
    r"do my homework",
    r"solve (this|my) (assignment|exam)",
    r"hack portal",
]

# Keyword dictionaries with weights
GPA_KEYWORDS = [
    "gpa",
    "điểm",
    "tính điểm",
    "tính gpa",
    "cảnh báo học vụ",
    "buộc thôi học",
    "học vụ",
    "tín chỉ tích lũy",
    "thang điểm 10",
    "thang điểm 4",
    "quy đổi điểm",
    "điểm rèn luyện",
    "học bổng",
    "xếp loại",
    "học kỳ",
    "what-if",
    "dự báo điểm",
]

SCHEDULING_KEYWORDS = [
    "lịch",
    "lịch thi",
    "xếp lịch",
    "lập lịch",
    "thời gian biểu",
    "ôn thi",
    "kế hoạch học",
    "thời khóa biểu",
    "phân bổ giờ",
    "giờ rảnh",
    "schedule",
    "study plan",
    "ngày thi",
    "học bài",
]

REGULATION_KEYWORDS = [
    "quy chế",
    "sổ tay",
    "điều khoản",
    "chuẩn đầu ra",
    "tiếng anh",
    "toeic",
    "ielts",
    "vstep",
    "học lại",
    "học cải thiện",
    "rút học phần",
    "rút môn",
    "đăng ký học phần",
    "chuyển ngành",
    "bảo lưu",
    "tốt nghiệp",
    "điều kiện tốt nghiệp",
    "miễn giảm",
    "chứng chỉ",
    "phòng đào tạo",
]

DEADLINE_KEYWORDS = [
    "deadline",
    "hạn nộp",
    "thông báo:",
    "bài tập lab",
    "nộp bài",
    ".ics",
    "ical",
    "moodle",
    "hạn chót",
    "thầy gửi",
    "cô gửi",
]

CLARIFY_TRIGGERS = [
    "cứu em",
    "cứu mình",
    "giúp em",
    "giúp mình",
    "alo",
    "ad ơi",
    "admin ơi",
    "chào bạn",
    "hello",
    "hi",
    "ơi",
]


def _match_any_pattern(text: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def _score_keywords(text_lower: str, keywords: list[str]) -> int:
    score = 0
    for kw in keywords:
        if kw in text_lower:
            score += 1
    return score


def route_query(query: str) -> Dict[str, Any]:
    """
    Route an incoming query to the appropriate engine.

    Returns a dictionary conforming to the Router Contract:
    {
        "intent": str,
        "confidence": float,
        "target_engine": str,
        "extracted_params": dict,
        "message": str
    }
    """
    if not query or not query.strip():
        return {
            "intent": INTENT_CLARIFY,
            "confidence": 1.0,
            "target_engine": "clarifier",
            "extracted_params": {},
            "message": "Vui lòng nhập câu hỏi hoặc yêu cầu cần trợ giúp.",
        }

    clean_query = query.strip()
    query_lower = clean_query.lower()

    # 1. Check for Rejection / Policy violations
    if _match_any_pattern(clean_query, REJECT_PATTERNS):
        return {
            "intent": INTENT_REJECT,
            "confidence": 0.99,
            "target_engine": "guardrails",
            "extracted_params": {"reason": "Policy violation or Non-goal"},
            "message": (
                "Yêu cầu vi phạm quy định an toàn hoặc nằm ngoài phạm vi hỗ trợ "
                "(Hệ thống không giải bài tập hộ sinh viên)."
            ),
        }

    # 2. Check for Ambiguous / Clarification queries
    words = clean_query.split()
    if len(words) <= 3:
        for trigger in CLARIFY_TRIGGERS:
            if trigger in query_lower:
                return {
                    "intent": INTENT_CLARIFY,
                    "confidence": 0.90,
                    "target_engine": "clarifier",
                    "extracted_params": {},
                    "message": (
                        "Chào bạn! Bạn cần H.E.R.M.E.S hỗ trợ về tính điểm GPA, "
                        "lập lịch ôn thi hay tra cứu quy chế học vụ?"
                    ),
                }

    # 3. Score categories (Fast-Path)
    gpa_score = _score_keywords(query_lower, GPA_KEYWORDS)
    sched_score = _score_keywords(query_lower, SCHEDULING_KEYWORDS)
    reg_score = _score_keywords(query_lower, REGULATION_KEYWORDS)
    dl_score = _score_keywords(query_lower, DEADLINE_KEYWORDS)

    # Contextual priority checks
    if dl_score >= 2 or (".ics" in query_lower) or ("thông báo:" in query_lower):
        return {
            "intent": INTENT_EXTRACT_DEADLINE,
            "confidence": 0.90,
            "target_engine": "ai_extractor",
            "extracted_params": {"raw_text": clean_query},
            "message": "Trích xuất deadline và thông tin bài tập.",
        }

    max_score = max(gpa_score, sched_score, reg_score)
    if max_score == 0:
        return {
            "intent": INTENT_CLARIFY,
            "confidence": 0.50,
            "target_engine": "clarifier",
            "extracted_params": {},
            "message": (
                "Câu hỏi chưa rõ ràng. Bạn có thể nói rõ hơn về vấn đề học vụ "
                "hoặc lịch học cần giúp đỡ không?"
            ),
        }

    # Scheduling intent
    if sched_score > gpa_score and sched_score >= reg_score:
        return {
            "intent": INTENT_SCHEDULING,
            "confidence": min(0.60 + sched_score * 0.15, 0.98),
            "target_engine": "scheduler_engine",
            "extracted_params": {},
            "message": "Định tuyến tới bộ lập lịch ôn tập.",
        }

    # GPA Calculation intent
    if gpa_score >= sched_score and gpa_score >= reg_score:
        extracted_grades = extract_grades_from_text(clean_query)
        return {
            "intent": INTENT_CALC_GPA,
            "confidence": min(0.60 + gpa_score * 0.15, 0.98),
            "target_engine": "academic_engine",
            "extracted_params": {
                "grades": extracted_grades,
                "raw_text": clean_query,
            },
            "message": "Định tuyến tới bộ tính toán học vụ và GPA.",
        }

    # Regulation / RAG intent
    return {
        "intent": INTENT_REGULATION_RAG,
        "confidence": min(0.60 + reg_score * 0.15, 0.98),
        "target_engine": "rag_retriever",
        "extracted_params": {"query": clean_query},
        "message": "Định tuyến tới bộ tra cứu quy chế và sổ tay sinh viên.",
    }


def extract_grades_from_text(text: str) -> list[dict]:
    results = []
    # Pattern 1: Subject Name (Grade, Credits) e.g. "Giải tích 1 (8.0, 4TC)"
    pattern = (
        r"([A-Za-zÀ-ỹ0-9\s\+\#\.\-]+)\s*\(\s*(\d+(?:\.\d+)?)\s*,\s*(\d+)"
        r"\s*(?:tc|tín(?:\s*ch[ỉi\?])?)?\s*\)"
    )

    for match in re.finditer(pattern, text, re.IGNORECASE):
        raw_subject = match.group(1).strip()
        cleaned_parts = re.split(
            r"[,;\n:]|(?:\b(?:và|với|môn|gồm|học\s+kỳ\s+này|học\s+phần|cho|là)\b)",
            raw_subject,
            flags=re.IGNORECASE,
        )
        subject_name = cleaned_parts[-1].strip() if cleaned_parts else raw_subject
        grade_val = float(match.group(2))
        credits_val = int(match.group(3))
        results.append(
            {
                "subject": subject_name,
                "grade": grade_val,
                "credits": credits_val,
            }
        )

    # Pattern 2: Shorthand Grade (Credits) e.g. "8.5 (4 tín chỉ), 7.0 (3TC)"
    if not results:
        shorthand_pattern = (
            r"(\d+(?:\.\d+)?)\s*\(\s*(\d+)\s*(?:tc|tín(?:\s*ch[ỉi\?])?)?\s*\)"
        )
        for idx, match in enumerate(
            re.finditer(shorthand_pattern, text, re.IGNORECASE), start=1
        ):
            results.append(
                {
                    "subject": f"Học phần {idx}",
                    "grade": float(match.group(1)),
                    "credits": int(match.group(2)),
                }
            )

    return results


_RETRIEVER_INSTANCE = None
_SESSION_MANAGER = None


def _get_retriever():
    global _RETRIEVER_INSTANCE
    if _RETRIEVER_INSTANCE is None:
        from hermes.rag.retriever import KeywordRetriever

        _RETRIEVER_INSTANCE = KeywordRetriever()
    return _RETRIEVER_INSTANCE


def get_session_manager():
    """Return singleton SessionManager instance for multi-turn state tracking (R5)."""
    global _SESSION_MANAGER
    if _SESSION_MANAGER is None:
        from hermes.router.session import SessionManager

        _SESSION_MANAGER = SessionManager()
    return _SESSION_MANAGER


def _extract_student_context(text_lower: str) -> Dict[str, str]:
    """Extract cohort (K20-K25) and program context from user query."""
    ctx: Dict[str, str] = {}
    cohort_match = re.search(r"\b(k2[0-5])\b", text_lower)
    if cohort_match:
        ctx["cohort"] = cohort_match.group(1).upper()
    if (
        "tăng cường tiếng anh" in text_lower
        or "tcta" in text_lower
        or "chất lượng cao" in text_lower
        or "clc" in text_lower
    ):
        ctx["program"] = "chương trình tăng cường tiếng Anh"
    elif "tiên tiến" in text_lower or "apcs" in text_lower or "cttt" in text_lower:
        ctx["program"] = "chương trình tiên tiến"
    elif "hệ chuẩn" in text_lower or "đại trà" in text_lower:
        ctx["program"] = "hệ chuẩn"
    return ctx


def _classify_academic_rank(gpa_10: float) -> str:
    """Phân loại học lực theo thang điểm 10 chuẩn HCMUS."""
    if gpa_10 >= 9.0:
        return "Xuất sắc"
    if gpa_10 >= 8.0:
        return "Giỏi"
    if gpa_10 >= 7.0:
        return "Khá"
    if gpa_10 >= 6.0:
        return "Trung bình khá"
    if gpa_10 >= 5.0:
        return "Trung bình"
    return "Yếu (Cần lưu ý cảnh báo học vụ)"


_CERT_DISPLAY_NAMES = {
    "IELTS": "IELTS",
    "TOEFL_iBT": "TOEFL iBT",
    "TOEIC": "TOEIC",
    "TOEIC_4_ky_nang": "TOEIC (4 kỹ năng)",
    "TOEIC_Nghe_Doc": "TOEIC (Nghe - Đọc)",
    "TOEIC_Noi_Viet": "TOEIC (Nói - Viết)",
    "TOEFL_ITP": "TOEFL ITP",
    "TOEFL_ITP_va_TOEIC_Noi_Viet": "TOEFL ITP + TOEIC Nói-Viết",
    "VSTEP": "VSTEP",
    "Bac_3_VN": "Khung năng lực Ngoại ngữ 6 bậc VN (Bậc 3)",
    "Bac_4_VN": "Khung năng lực Ngoại ngữ 6 bậc VN (Bậc 4)",
    "FCE": "Cambridge B2 First (FCE)",
    "PET": "Cambridge B1 Preliminary (PET)",
    "BEC_Busines_Vantage": "Cambridge BEC Business Vantage",
    "BEC_Preliminary": "Cambridge BEC Preliminary",
    "BULATS": "BULATS",
    "JLPT": "Tiếng Nhật JLPT",
    "PTE_Academic": "PTE Academic",
}


def _format_clean_regulation_body(raw_text: str, has_structured_table: bool) -> str:
    """
    Làm sạch văn bản quy chế để hiển thị dễ đọc như một cố vấn viết lại,
    loại bỏ đoạn dump 'Bảng (...):' nếu đã có bảng cấu trúc riêng.
    """
    lines = [ln.strip() for ln in raw_text.strip().splitlines() if ln.strip()]
    cleaned_lines: list[str] = []

    for ln in lines:
        if has_structured_table and (ln.startswith("Bảng (") or "|" in ln):
            continue
        # Chuyển các ý a), b), c), d) thành gạch đầu dòng dễ nhìn
        sub_match = re.match(r"^([a-h])\)\s+(.*)$", ln)
        if sub_match:
            cleaned_lines.append(f"- **{sub_match.group(1)})** {sub_match.group(2)}")
        else:
            cleaned_lines.append(ln)

    return "\n\n".join(cleaned_lines)


def _render_structured_table(bang: dict[str, Any]) -> str:
    """Chuyển trường 'bang' trong JSON quy chế thành bảng Markdown chuẩn."""
    cols = bang.get("cot") or []
    rows = bang.get("dong") or []
    if not cols or not rows:
        return ""

    col_labels = {
        "tieu_chi": "Tiêu chí đánh giá",
        "noi_dung": "Nội dung chi tiết",
        "ty_le": "Tỷ lệ điểm",
        "ten_hoc_phan": "Học phần",
        "nghe": "Nghe",
        "noi": "Nói",
        "doc": "Đọc",
        "viet": "Viết",
        "khoa": "Khóa tuyển",
        "hoc_phan_dat": "Yêu cầu học phần",
        "chung_chi": "Chứng chỉ tương đương",
    }
    headers = [col_labels.get(str(c), str(c).replace("_", " ").title()) for c in cols]
    md = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join([":---"] * len(headers)) + " |",
    ]
    for r in rows:
        cells = [str(cell) if cell is not None else "—" for cell in r]
        md.append("| " + " | ".join(cells) + " |")
    return "\n".join(md)


def _build_regulation_advisor_response(
    query: str,
    rag_res: dict[str, Any],
) -> tuple[str, str | None, list[str]]:
    """
    Tổng hợp câu trả lời tư vấn quy chế tự nhiên, đi thẳng vào câu hỏi của sinh viên,
    không lặp lại mẫu câu cứng nhắc và hỗ trợ so sánh khi câu hỏi chưa rõ hệ/khóa.
    """
    hits = rag_res.get("ket_qua", [])
    if not hits:
        resp = (
            "Mình chưa tìm thấy điều khoản nào khớp trực tiếp với câu hỏi này "
            "trong cơ sở dữ liệu quy chế hiện tại của trường.\n\n"
            "Bạn có thể nói rõ hơn vấn đề đang gặp phải (ví dụ: *chuẩn ngoại ngữ đầu ra theo khóa*, "
            "*quy định học phần Anh văn*, *điều kiện cảnh báo học vụ*, hoặc *xác minh chứng chỉ*) "
            "để mình tra cứu chính xác hơn nhé."
        )
        follow_ups = [
            "Chuẩn đầu ra ngoại ngữ chương trình đại trà khóa 2024 là gì?",
            "Chuẩn đầu ra ngoại ngữ ngành Công nghệ thông tin hệ tăng cường tiếng Anh?",
            "Sinh viên vắng quá mấy buổi học Anh văn thì bị mất điểm quá trình?",
        ]
        return resp, None, follow_ups

    q_lower = query.lower()
    top_hit = hits[0]

    # Chỉ ưu tiên nhảy sang chunk bảng điểm chứng chỉ khi người dùng thực sự hỏi về chuẩn/chứng chỉ/điểm
    asking_cert_scores = any(
        kw in q_lower
        for kw in [
            "chuẩn đầu ra",
            "ngoại ngữ",
            "tiếng anh",
            "ielts",
            "toeic",
            "toefl",
            "vstep",
            "jlpt",
            "chứng chỉ",
            "bao nhiêu điểm",
            "mấy chấm",
        ]
    ) and not any(
        kw in q_lower
        for kw in [
            "hồ sơ",
            "thủ tục",
            "giả",
            "hiệu lực",
            "mấy năm",
            "vắng",
            "quá trình",
        ]
    )

    if asking_cert_scores and not top_hit.get("chung_chi_toi_thieu"):
        top_vb_prefix = str(top_hit.get("chunk_id", "")).split("_")[0]
        for h in hits:
            h_prefix = str(h.get("chunk_id", "")).split("_")[0]
            if h.get("chung_chi_toi_thieu") and h_prefix == top_vb_prefix:
                top_hit = h
                break

    citation = top_hit.get("trich_dan", "Quy định Đào tạo ĐH Khoa học Tự nhiên")
    pham_vi = top_hit.get("pham_vi", "sinh viên ĐH chính quy")
    ten_dieu = top_hit.get("ten_dieu", "")
    cert_dict = top_hit.get("chung_chi_toi_thieu") or {}
    bang_data = top_hit.get("bang")
    body_text = _format_clean_regulation_body(
        top_hit.get("text", ""), has_structured_table=bool(bang_data)
    )

    sections: list[str] = []

    # 1. Cảnh báo nếu khóa tuyển người dùng hỏi nằm ngoài phạm vi văn bản hiện có
    if rag_res.get("canh_bao"):
        sections.append(f"> **Lưu ý về khóa tuyển:** {rag_res['canh_bao']}")

    # 2. Mở đầu trực diện như một người cố vấn thực thụ
    if cert_dict:
        # Kiểm tra xem sinh viên có hỏi đích danh 1 chứng chỉ cụ thể không
        specific_matches: list[tuple[str, str]] = []
        for k, v in cert_dict.items():
            k_low = k.lower()
            if (
                ("ielts" in q_lower and "ielts" in k_low)
                or ("toeic" in q_lower and "toeic" in k_low)
                or ("toefl" in q_lower and "toefl" in k_low)
                or ("vstep" in q_lower and ("vstep" in k_low or "bac_" in k_low))
                or ("jlpt" in q_lower or "nhật" in q_lower)
                and "jlpt" in k_low
            ):
                specific_matches.append((_CERT_DISPLAY_NAMES.get(k, k), v))

        if specific_matches:
            summary_items = "; ".join(
                f"**{name}**: {val}" for name, val in specific_matches
            )
            sections.append(
                f"Đối với **{pham_vi}**, mức chuẩn tối thiểu bạn cần đạt là {summary_items}."
            )
        else:
            ielts_val = cert_dict.get("IELTS")
            toeic_val = cert_dict.get("TOEIC_4_ky_nang") or cert_dict.get("TOEIC")
            quick_highlights = []
            if ielts_val:
                quick_highlights.append(f"**IELTS {ielts_val.split('(')[0].strip()}**")
            if toeic_val:
                quick_highlights.append(f"**TOEIC {toeic_val.split('(')[0].strip()}**")
            highlight_str = (
                f" (phổ biến nhất là {' hoặc '.join(quick_highlights)})"
                if quick_highlights
                else ""
            )
            sections.append(
                f"Theo quy định áp dụng cho **{pham_vi}**, sinh viên cần đạt một trong "
                f"các mức chứng chỉ ngoại ngữ tối thiểu dưới đây{highlight_str} để đủ "
                "điều kiện xét tốt nghiệp:"
            )

        table_lines = [
            "| Chứng chỉ / Bài thi | Yêu cầu tối thiểu được công nhận |",
            "| :--- | :--- |",
        ]
        for k, v in cert_dict.items():
            display_k = _CERT_DISPLAY_NAMES.get(k, k.replace("_", " "))
            table_lines.append(f"| **{display_k}** | {v} |")
        sections.append("\n".join(table_lines))
    else:
        if ten_dieu:
            sections.append(
                f"Về **{ten_dieu}** (*áp dụng cho {pham_vi}*), quy định cụ thể như sau:"
            )
        sections.append(body_text)

    if bang_data:
        rendered_table = _render_structured_table(bang_data)
        if rendered_table:
            sections.append(rendered_table)

    # 3. Nếu câu hỏi còn chung chung, tự động so sánh giúp sinh viên
    if rag_res.get("can_hoi_lai") and len(hits) > 1:
        comp_rows = []
        seen_programs = set()
        for h in hits:
            cc = h.get("chung_chi_toi_thieu")
            pv = h.get("pham_vi", "")
            if cc and pv and pv not in seen_programs:
                seen_programs.add(pv)
                ielts_v = cc.get("IELTS", "—").split("(")[0].strip()
                toeic_v = (
                    (cc.get("TOEIC_4_ky_nang") or cc.get("TOEIC") or "—")
                    .split("(")[0]
                    .strip()
                )
                comp_rows.append(f"| {pv} | {ielts_v} | {toeic_v} |")
        if len(comp_rows) > 1:
            sections.append(
                "**So sánh nhanh giữa các chương trình đào tạo:**\n"
                "Vì mỗi hệ đào tạo có mức chuẩn khác nhau, bạn có thể đối chiếu bảng "
                "dưới đây (hoặc chọn đúng Khóa/Hệ của bạn ở thanh bên trái):\n\n"
                "| Chương trình & Khóa áp dụng | IELTS tối thiểu | TOEIC tối thiểu |\n"
                "| :--- | :--- | :--- |\n" + "\n".join(comp_rows)
            )

    # 4. Căn cứ pháp lý gọn gàng ở cuối
    sections.append(f"---\n*Căn cứ pháp lý: {citation} • Phạm vi: {pham_vi}*")

    # 5. Gợi ý câu hỏi tiếp theo theo đúng mạch đang hỏi
    if cert_dict:
        follow_ups = [
            "Hồ sơ xét đạt chuẩn ngoại ngữ đầu ra gồm những giấy tờ gì?",
            "Chứng chỉ ngoại ngữ có thời hạn hiệu lực mấy năm khi nộp xét tốt nghiệp?",
            "Trường xử lý thế nào nếu phát hiện nộp chứng chỉ ngoại ngữ không hợp lệ?",
        ]
    elif "hồ sơ" in q_lower or "thủ tục" in q_lower:
        follow_ups = [
            "Chuẩn đầu ra ngoại ngữ ngành Công nghệ thông tin hệ tăng cường tiếng Anh là gì?",
            "Chứng chỉ không ghi thời hạn thì hiệu lực được tính bao lâu?",
            "Thời điểm nào sinh viên phải hoàn tất nộp chứng chỉ ngoại ngữ?",
        ]
    else:
        follow_ups = [
            "Điểm đánh giá quá trình môn Anh văn chiếm bao nhiêu phần trăm?",
            "Sinh viên vắng quá 3 buổi học Anh văn sẽ bị xử lý thế nào?",
            "Chuẩn tiếng Anh để được học các học phần chuyên ngành là gì?",
        ]

    return "\n\n".join(sections), citation, follow_ups


def _parse_schedule_params_from_query(
    query: str, session_grades: list[dict] | None = None
) -> tuple[list[dict], float, int]:
    """
    Trích xuất linh hoạt số ngày, số giờ học mỗi ngày và danh sách môn thi
    ngay từ câu chat của người dùng (thay vì luôn trả về bộ môn cố định).
    """
    q_lower = query.lower()

    # 1. Số ngày ôn tập
    days_left = 10
    week_match = re.search(r"(\d+)\s*tuần", q_lower)
    day_match = re.search(r"(\d+)\s*ngày", q_lower)
    if day_match:
        days_left = max(1, min(60, int(day_match.group(1))))
    elif week_match:
        days_left = max(1, min(60, int(week_match.group(1)) * 7))
    elif "tuần sau" in q_lower or "tuần tới" in q_lower:
        days_left = 7

    # 2. Số giờ rảnh mỗi ngày
    daily_hours = 6.0
    hour_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:giờ|tiếng|h)\b", q_lower)
    if hour_match:
        daily_hours = max(1.0, min(14.0, float(hour_match.group(1))))

    # 3. Danh sách môn học (nếu người dùng có nhắc tới trong câu hỏi)
    known_subjects = [
        ("Giải tích 1", 4, 3, ["giải tích 1", "giải tích", "toán"]),
        ("Đại số Tuyến tính", 4, 2, ["đại số", "tuyến tính"]),
        (
            "Cấu trúc Dữ liệu & Giải thuật",
            4,
            3,
            ["cấu trúc dữ liệu", "ctdl", "giải thuật"],
        ),
        ("Hệ điều hành", 4, 3, ["hệ điều hành", "hdh"]),
        ("Mạng máy tính", 4, 2, ["mạng máy tính", "mạng"]),
        ("Cơ sở dữ liệu", 4, 2, ["cơ sở dữ liệu", "csdl"]),
        ("Vật lý đại cương", 3, 2, ["vật lý", "lý"]),
        ("Nhập môn Lập trình", 4, 2, ["lập trình", "c++", "code"]),
        ("Kiến trúc Máy tính", 3, 2, ["kiến trúc máy tính", "ktmt"]),
        ("Toán Rời Rạc", 4, 3, ["rời rạc"]),
    ]
    matched_subjects: list[dict] = []
    for name, cred, prio, aliases in known_subjects:
        if any(a in q_lower for a in aliases):
            matched_subjects.append({"name": name, "credits": cred, "priority": prio})

    if matched_subjects:
        return matched_subjects, daily_hours, days_left

    if session_grades:
        from_session = [
            {
                "name": g["subject"],
                "credits": int(g["credits"]),
                "priority": 3 if g["grade"] < 6.5 else (2 if g["grade"] < 8.0 else 1),
            }
            for g in session_grades
        ]
        if from_session:
            return from_session, daily_hours, days_left

    default_subjects = [
        {"name": "Toán Rời Rạc", "credits": 4, "priority": 3},
        {"name": "Cấu trúc Dữ liệu & Giải thuật", "credits": 4, "priority": 2},
        {"name": "Kiến trúc Máy tính", "credits": 3, "priority": 1},
    ]
    return default_subjects, daily_hours, days_left


def _try_parse_what_if_query(
    query: str,
    session_grades: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """
    Phát hiện và giải bài toán Dự báo GPA Mục tiêu (What-If Simulation - UC03)
    bằng thuật toán tất định simulate_gpa() (R2).
    """
    from hermes.engines.academic_calc import calculate_gpa_10
    from hermes.engines.scheduler import simulate_gpa

    q_lower = query.lower()
    what_if_triggers = [
        "kéo gpa",
        "lên gpa",
        "mục tiêu",
        "cần đạt",
        "cần mấy điểm",
        "dự báo gpa",
        "kỳ sau",
        "kỳ tới",
        "để kéo",
        "để lên",
    ]
    if not any(t in q_lower for t in what_if_triggers):
        return None

    # 1. Tìm target_gpa (VD: "lên 7.0", "lên GPA 8.0", "mục tiêu 7.5")
    target_match = re.search(
        r"(?:lên(?:\s+gpa)?(?:\s+tích\s+lũy)?|mục\s+tiêu(?:\s+gpa)?)\s*(?:là\s*)?(\d+(?:[.,]\d+)?)",
        q_lower,
    )
    if not target_match:
        return None
    target_gpa = float(target_match.group(1).replace(",", "."))

    # 2. Tìm remaining_credits (VD: "kỳ này học 15TC", "đăng ký 12 tín chỉ")
    rem_match = re.search(
        r"(?:kỳ\s+(?:này|sau|tới)\s*(?:mình\s*)?(?:học|đăng\s+ký)?|"
        r"đăng\s+ký(?:\s+thêm)?|học\s+thêm)\s*(\d{1,3})\s*(?:tc|tín(?:\s*chỉ)?)",
        q_lower,
    )
    if not rem_match:
        return None
    remaining_credits = int(rem_match.group(1))
    if remaining_credits <= 0:
        return None

    # 3. Tìm current_gpa & current_credits từ câu hỏi hoặc từ session_grades
    cur_gpa_match = re.search(
        r"gpa(?:\s+hiện\s+tại|\s+tích\s+lũy)?(?:\s+của\s+mình)?(?:\s+là)?\s*(\d+(?:[.,]\d+)?)",
        q_lower,
    )
    cur_tc_match = re.search(
        r"(?:tích\s+lũy|đã\s+học|hiện\s+có)\s*(\d{1,3})\s*(?:tc|tín(?:\s*chỉ)?)",
        q_lower,
    )

    if cur_gpa_match and cur_tc_match:
        current_gpa = float(cur_gpa_match.group(1).replace(",", "."))
        current_credits = int(cur_tc_match.group(1))
        current_courses = [{"credits": current_credits, "grade": current_gpa}]
    elif session_grades:
        current_courses = [
            {"credits": int(g["credits"]), "grade": float(g["grade"])}
            for g in session_grades
        ]
        current_credits = sum(c["credits"] for c in current_courses)
        current_gpa = calculate_gpa_10(
            [(c["grade"], c["credits"]) for c in current_courses]
        )
    else:
        return None

    required_gpa = simulate_gpa(
        current_courses=current_courses,
        target_gpa=target_gpa,
        remaining_credits=remaining_credits,
    )
    total_future_tc = current_credits + remaining_credits
    feasible = required_gpa <= 10.0

    if feasible:
        req_display = max(0.0, required_gpa)
        feasibility_str = (
            "Khả thi trong 1 học kỳ"
            if req_display <= 8.5
            else "Khả thi nhưng đòi hỏi nỗ lực rất cao (cần đạt mức Giỏi/Xuất sắc)"
        )
        advice = (
            f"Để nâng GPA tích lũy từ **{current_gpa:.2f}** ({current_credits} TC) lên **{target_gpa:.2f}** "
            f"sau khi học thêm **{remaining_credits} tín chỉ** (tổng `{total_future_tc} TC`), "
            f"bạn cần đạt điểm trung bình học kỳ tới tối thiểu là **`{req_display:.2f}/10`**."
        )
    else:
        max_possible_gpa = round(
            (current_gpa * current_credits + 10.0 * remaining_credits)
            / total_future_tc,
            2,
        )
        feasibility_str = f"Chưa khả thi trong 1 học kỳ (vượt thang điểm 10.0 — cần {required_gpa:.2f}/10)"
        advice = (
            f"Ngay cả khi bạn đạt tuyệt đối **10.0/10** cho toàn bộ **{remaining_credits} tín chỉ** sắp tới, "
            f"GPA tích lũy tối đa sau kỳ này sẽ là **`{max_possible_gpa:.2f}/10`**. "
            "Bạn nên chia lộ trình kéo điểm qua **2 học kỳ** hoặc đăng ký học cải thiện các môn điểm thấp (D/D+)."
        )

    resp_lines = [
        "**Kết quả Mô phỏng GPA Mục tiêu (What-If Simulation — UC03):**\n",
        advice + "\n",
        "| Chỉ số học vụ | Giá trị tính toán |",
        "| :--- | :--- |",
        f"| **GPA tích lũy hiện tại** | `{current_gpa:.2f} / 10` ({current_credits} tín chỉ) |",
        f"| **Số tín chỉ đăng ký thêm** | `{remaining_credits} tín chỉ` (Tổng sau kỳ tới: `{total_future_tc} TC`) |",
        f"| **GPA tích lũy mục tiêu** | **`{target_gpa:.2f} / 10`** |",
        f"| **GPA học kỳ tối thiểu cần đạt** | **`{required_gpa:.2f} / 10`** |",
        f"| **Đánh giá tính khả thi** | {feasibility_str} |",
    ]
    return {
        "response_text": "\n".join(resp_lines),
        "what_if": {
            "current_gpa": current_gpa,
            "current_credits": current_credits,
            "remaining_credits": remaining_credits,
            "target_gpa": target_gpa,
            "required_gpa": required_gpa,
            "feasible": feasible,
        },
    }


def _try_answer_academic_warning_query(query: str) -> dict[str, Any] | None:
    """
    Trả lời chính xác điều kiện Cảnh báo học vụ & Buộc thôi học theo Điều 16
    Quy chế Đào tạo Học chế Tín chỉ (1175/QĐ-KHTN) và kiểm tra số liệu nếu có (UC02).
    """
    from hermes.engines.academic_calc import check_academic_warning

    q_lower = query.lower()
    if not any(
        kw in q_lower for kw in ["cảnh báo học vụ", "cảnh báo kết quả", "buộc thôi học"]
    ):
        return None

    # Kiểm tra xem sinh viên có nêu số tín chỉ đạt hoặc điểm trung bình cụ thể không
    tc_match = re.search(
        r"(?:đạt|có|học|tích\s+lũy)\s*(\d{1,2})\s*(?:tc|tín(?:\s*chỉ)?)", q_lower
    )
    gpa_match = re.search(
        r"(?:gpa|điểm\s+trung\s+bình|đtb)\s*(?:học\s+kỳ\s*)?(?:là\s*)?(\d+(?:[.,]\d+)?)",
        q_lower,
    )

    eval_section = ""
    warn_res = None
    if tc_match or gpa_match:
        earned_tc = int(tc_match.group(1)) if tc_match else 12
        sem_gpa = float(gpa_match.group(1).replace(",", ".")) if gpa_match else 6.0
        warn_res = check_academic_warning(
            current_semester_earned_credits=earned_tc,
            accumulated_credits=max(earned_tc, 15),
            previous_semester_gpa=sem_gpa,
            two_previous_semesters_gpa=sem_gpa,
        )
        if warn_res["is_warning"]:
            eval_section = (
                f"**Đánh giá trường hợp của bạn:** Với số liệu bạn cung cấp "
                f"(tín chỉ đạt trong kỳ: `{earned_tc} TC`, ĐTB học kỳ: `{sem_gpa:.2f}/10`), "
                f"bạn thuộc diện **{warn_res['status']}** do: *{'; '.join(warn_res['reasons'])}*.\n\n"
            )
        else:
            eval_section = (
                f"**Đánh giá trường hợp của bạn:** Với số liệu bạn cung cấp "
                f"(tín chỉ đạt trong kỳ: `{earned_tc} TC`, ĐTB học kỳ: `{sem_gpa:.2f}/10`), "
                "bạn **An toàn (không bị cảnh báo học vụ)** trong học kỳ này.\n\n"
            )

    lines = [
        eval_section
        + "Theo **Điều 16 – Quy chế Đào tạo theo Hệ thống Tín chỉ (1175/QĐ-KHTN)** "
        "của Trường ĐH Khoa học Tự nhiên (ĐHQG-HCM), sinh viên sẽ bị **Cảnh báo kết quả "
        "học tập (Cảnh báo học vụ)** hoặc **Buộc thôi học** khi rơi vào một trong các ngưỡng sau:\n",
        "| Phân loại | Tiêu chí kiểm tra theo Quy chế (Điều 16) | Ngưỡng vi phạm | Hệ quả học vụ |",
        "| :--- | :--- | :---: | :--- |",
        (
            "| **Ngưỡng 1 (Tín chỉ học kỳ)** | Tổng số tín chỉ đạt trong 1 học kỳ chính "
            "*(không tính học kỳ cuối khóa)* | **`< 7 tín chỉ`** | **Cảnh báo học vụ** |"
        ),
        (
            "| **Ngưỡng 2 (ĐTB 1 học kỳ)** | Điểm trung bình học kỳ "
            "(GPA hệ 10 của học kỳ chính) | **`< 3.00 / 10`** | **Cảnh báo học vụ** |"
        ),
        (
            "| **Ngưỡng 3 (ĐTB 2 kỳ liên tiếp)** | Điểm trung bình của "
            "**2 học kỳ chính liên tiếp** | **`< 4.00 / 10`** | **Cảnh báo học vụ** |"
        ),
        (
            "| **Ngưỡng 4 (Buộc thôi học)** | Số lần bị cảnh báo học vụ liên tiếp "
            "hoặc vượt thời gian tối đa | **3 lần liên tiếp** | **Xem xét Buộc thôi học** |"
        ),
        "\n*Gợi ý:* Nếu bạn muốn mình tính GPA chính xác kèm kiểm tra tự động "
        "từ danh sách môn học, hãy nhắn theo mẫu: "
        "`Giải tích 1 (6.5, 4TC), Cấu trúc dữ liệu (5.5, 4TC)` nhé.",
    ]
    return {
        "response_text": "\n".join(lines),
        "warning_evaluation": warn_res,
    }


def orchestrate(query: str, session_id: str = "default_user") -> Dict[str, Any]:
    """
    Master Pipeline điều phối toàn bộ hệ thống H.E.R.M.E.S.

    Quy trình:
    1. Quét an toàn qua Guardrails (R7)
    2. Cập nhật và đồng bộ trạng thái hội thoại qua SessionManager (R5)
    3. Phân loại ý định qua Router 2 tầng (R5)
    4. Điều hướng xử lý sang GPA Engine (R2), Scheduler (R2), RAG Quy chế (R3) hoặc AI (R4)
    5. Định dạng câu trả lời tự nhiên, tập trung vào người dùng (R6)
    """
    from hermes.engines.academic_calc import (
        calculate_gpa_4,
        calculate_gpa_10,
        check_academic_warning,
        convert_score_to_4_and_letter,
    )
    from hermes.router.session import DialogueState
    from hermes.security.guardrails import validate_and_clean

    session = get_session_manager().get_or_create(session_id)

    # 1. Quét an toàn đầu vào (R7)
    guard_res = validate_and_clean(query)
    if not guard_res.allowed:
        if guard_res.category == "academic_integrity":
            friendly_reject = (
                "**Mình không thể giải trực tiếp bài tập hoặc làm hộ bài thi/đồ án** "
                "theo nguyên tắc liêm chính học thuật của trường.\n\n"
                "Tuy nhiên, nếu bạn đang bị quá tải với bài tập này, mình có thể giúp bạn ngay:\n"
                "- **Bóc tách yêu cầu & hạn nộp:** Dán thông báo của giảng viên vào đây "
                "để mình trích xuất checklist cần nộp và cài nhắc hẹn.\n"
                "- **Chia nhỏ lịch làm bài:** Cho mình biết bạn còn mấy ngày trước hạn nộp "
                "để mình phân bổ số giờ làm mỗi ngày hợp lý."
            )
        else:
            friendly_reject = (
                f"**Yêu cầu không thể thực hiện:** {guard_res.reason}.\n\n"
                "Mình chỉ hỗ trợ các vấn đề học vụ tại ĐH Khoa học Tự nhiên (tra cứu quy chế, "
                "tính điểm GPA, dự báo học lực, bóc tách hạn nộp bài và lập lịch ôn thi)."
            )
        return {
            "status": "blocked",
            "intent": INTENT_REJECT,
            "target_engine": "guardrails",
            "response_text": friendly_reject,
            "data": {
                "category": guard_res.category,
                "session_state": session.state.value,
                "follow_ups": [
                    "Lập kế hoạch ôn thi trong 7 ngày giúp mình",
                    "Chuẩn đầu ra ngoại ngữ ngành Công nghệ thông tin là gì?",
                    "Tính điểm GPA học kỳ này giúp mình",
                ],
            },
            "provenance": None,
        }

    clean_query = guard_res.cleaned_text
    session.add_message("user", clean_query)

    # Lưu ngữ cảnh Khóa / Hệ đào tạo vào Session Slots nếu có
    detected_ctx = _extract_student_context(clean_query.lower())
    for k, v in detected_ctx.items():
        session.fill_slot(k, v)

    # 2. Phân loại ý định qua Router (R5) + Kế thừa trạng thái Session (Multi-turn)
    route_info = route_query(clean_query)
    intent = route_info["intent"]
    target_engine = route_info["target_engine"]
    extracted = route_info.get("extracted_params", {})

    if session.state == DialogueState.AWAITING_GRADES:
        followup_grades = extract_grades_from_text(clean_query)
        if followup_grades:
            intent = INTENT_CALC_GPA
            target_engine = "academic_engine"
            extracted = {"grades": followup_grades, "raw_text": clean_query}

    # ----------------------------------------------------
    # Nhánh A: Tính điểm học vụ GPA (R2)
    # ----------------------------------------------------
    if intent == INTENT_CALC_GPA:
        grades = extracted.get("grades", [])
        if grades:
            session.set_state(DialogueState.IDLE, {"last_grades": grades})
            grade_tuples = [(g["grade"], g["credits"]) for g in grades]
            gpa_10 = calculate_gpa_10(grade_tuples)
            gpa_4 = calculate_gpa_4(grade_tuples)
            total_tc = sum(g["credits"] for g in grades)
            passed_tc = sum(g["credits"] for g in grades if g["grade"] >= 5.0)
            rank_label = _classify_academic_rank(gpa_10)

            warn_info = check_academic_warning(
                current_semester_earned_credits=passed_tc,
                accumulated_credits=max(total_tc, 15),
                previous_semester_gpa=gpa_10,
                two_previous_semesters_gpa=gpa_10,
            )

            lines = [
                f"Với **{len(grades)} học phần** vừa nhập (tổng **{total_tc} tín chỉ**), "
                f"điểm trung bình của bạn đạt **{gpa_10:.2f}/10** "
                f"(tương đương **{gpa_4:.2f}/4.0** — xếp loại **{rank_label}**).\n",
                "| Học phần | Tín chỉ | Điểm hệ 10 | Điểm hệ 4 | Điểm chữ | Trạng thái |",
                "| :--- | :---: | :---: | :---: | :---: | :---: |",
            ]
            low_courses = []
            retake_courses = []
            for g in grades:
                s4, letter = convert_score_to_4_and_letter(g["grade"])
                if g["grade"] < 5.0:
                    status_str = "Không đạt (Học lại)"
                    retake_courses.append(g["subject"])
                elif g["grade"] < 6.5:
                    status_str = "Đạt (Có thể cải thiện)"
                    low_courses.append(g["subject"])
                else:
                    status_str = "Đạt tốt"
                lines.append(
                    f"| **{g['subject']}** | {g['credits']} TC | `{g['grade']:.1f}` "
                    f"| `{s4:.1f}` | **{letter}** | {status_str} |"
                )

            # Lời khuyên cá nhân hóa sát với bảng điểm thật của sinh viên
            advice_parts: list[str] = []
            if warn_info["is_warning"]:
                advice_parts.append(
                    f"- **Cảnh báo học vụ (Điều 16):** Bạn đang có nguy cơ rơi vào diện **{warn_info['status']}** "
                    f"do *{'; '.join(warn_info['reasons'])}* (số tín chỉ đạt trong kỳ hiện là `{passed_tc} TC`)."
                )
            else:
                advice_parts.append(
                    f"- **Đánh giá an toàn học vụ:** Bạn đã tích lũy đạt **{passed_tc}/{total_tc} tín chỉ** "
                    "trong kỳ và hoàn toàn **không nằm trong diện cảnh báo học vụ**."
                )

            if retake_courses:
                advice_parts.append(
                    f"- **Ưu tiên đăng ký học lại:** Bạn có học phần **{', '.join(retake_courses)}** "
                    "dưới 5.0 (điểm F). Bạn nên ưu tiên mở lớp học lại sớm để không ảnh hưởng "
                    "tiến độ xét tốt nghiệp."
                )
            elif low_courses and gpa_10 < 8.0:
                advice_parts.append(
                    f"- **Chiến lược kéo GPA:** Nếu muốn nâng GPA lên mức Giỏi (8.0+), học phần "
                    f"**{', '.join(low_courses)}** đang có hệ số quy đổi hệ 4 khá thấp — bạn có thể "
                    "cân nhắc học cải thiện hoặc tập trung gỡ điểm ở học kỳ tới trong tab "
                    "**Lập lịch & Dự báo GPA**."
                )
            elif gpa_10 >= 8.0:
                advice_parts.append(
                    "- **Cơ hội học bổng:** Mức GPA hiện tại của bạn đủ chuẩn cạnh tranh "
                    "**Học bổng Khuyến khích Học tập** nếu không có học phần nào dưới 5.0 "
                    "và điểm rèn luyện đạt từ loại Tốt trở lên."
                )

            lines.append(
                "\n**Nhận xét & Gợi ý dành cho bạn:**\n" + "\n".join(advice_parts)
            )
            resp_text = "\n".join(lines)
            session.add_message("assistant", resp_text)
            return {
                "status": "success",
                "intent": intent,
                "target_engine": target_engine,
                "response_text": resp_text,
                "data": {
                    "gpa_10": gpa_10,
                    "gpa_4": gpa_4,
                    "grades": grades,
                    "session_state": session.state.value,
                    "follow_ups": [
                        "Lập lịch ôn tập cho các môn này trong 10 ngày",
                        "Chuẩn đầu ra ngoại ngữ để xét tốt nghiệp là bao nhiêu?",
                        "Nếu kỳ sau mình đăng ký 12 tín chỉ thì cần đạt mấy điểm để lên GPA 8.0?",
                    ],
                },
                "provenance": "Quy chế Đào tạo theo Hệ thống Tín chỉ – ĐH Khoa học Tự nhiên, ĐHQG-HCM",
            }
        else:
            # Kiểm tra bài toán Mô phỏng GPA mục tiêu (What-If Simulation - UC03)
            what_if_res = _try_parse_what_if_query(
                clean_query, session_grades=session.get_slot("last_grades")
            )
            if what_if_res is not None:
                session.set_state(DialogueState.IDLE)
                resp_text = what_if_res["response_text"]
                session.add_message("assistant", resp_text)
                return {
                    "status": "success",
                    "intent": intent,
                    "target_engine": target_engine,
                    "response_text": resp_text,
                    "data": {
                        **extracted,
                        "what_if": what_if_res["what_if"],
                        "session_state": session.state.value,
                        "follow_ups": [
                            "Điểm tích lũy bao nhiêu thì bị cảnh báo học vụ?",
                            "Lập lịch ôn thi trong 7 ngày với 4 giờ mỗi ngày",
                        ],
                    },
                    "provenance": "Thuật toán Mô phỏng GPA Tất định (What-If Simulation — Quy chế 1175/QĐ-KHTN)",
                }

            # Kiểm tra câu hỏi về ngưỡng Cảnh báo học vụ / Buộc thôi học (Điều 16 - UC02)
            warn_query_res = _try_answer_academic_warning_query(clean_query)
            if warn_query_res is not None:
                session.set_state(DialogueState.IDLE)
                resp_text = warn_query_res["response_text"]
                session.add_message("assistant", resp_text)
                return {
                    "status": "success",
                    "intent": intent,
                    "target_engine": target_engine,
                    "response_text": resp_text,
                    "data": {
                        **extracted,
                        "warning_evaluation": warn_query_res["warning_evaluation"],
                        "session_state": session.state.value,
                        "follow_ups": [
                            "Giải tích 1 (4.5, 4TC), Vật lý 1 (5.5, 3TC)",
                            (
                                "GPA hiện tại của mình là 6.5 (tích lũy 30TC). "
                                "Kỳ này học 15TC, cần đạt bao nhiêu để lên GPA 7.0?"
                            ),
                        ],
                    },
                    "provenance": "Quy chế Đào tạo theo Hệ thống Tín chỉ (1175/QĐ-KHTN) — Điều 16",
                }

            session.set_state(DialogueState.AWAITING_GRADES)
            resp_text = (
                "Để mình tính chính xác **GPA hệ 10, hệ 4** và kiểm tra **điều kiện an toàn học vụ**, "
                "bạn hãy nhắn tên các môn kèm điểm và số tín chỉ ở tin nhắn tiếp theo nhé.\n\n"
                "**Ví dụ cách nhắn nhanh:**\n"
                "`Giải tích 1 (8.5, 4TC), Cấu trúc dữ liệu (7.5, 4 tín), Pháp luật đại cương (9.0, 2TC)`\n\n"
                "*Hoặc bạn có thể bấm nút **Phân tích bảng điểm hiện tại** ở thanh bên trái "
                "để gửi bảng điểm của bạn vào đây ngay lập tức.*"
            )
            session.add_message("assistant", resp_text)
            return {
                "status": "needs_info",
                "intent": intent,
                "target_engine": target_engine,
                "response_text": resp_text,
                "data": {
                    **extracted,
                    "session_state": session.state.value,
                    "follow_ups": [
                        "Giải tích 1 (8.5, 4TC), Cấu trúc dữ liệu (7.5, 4TC), Tư duy tính toán (9.0, 3TC)",
                        "Giải tích 1 (4.5, 4TC), Vật lý 1 (5.5, 3TC)",
                    ],
                },
                "provenance": None,
            }

    # ----------------------------------------------------
    # Nhánh B: Tra cứu quy chế RAG (R3)
    # ----------------------------------------------------
    elif intent == INTENT_REGULATION_RAG:
        session.set_state(DialogueState.IDLE)
        effective_rag_query = clean_query
        if "cohort" not in detected_ctx and session.get_slot("cohort"):
            effective_rag_query = f"{clean_query} {session.get_slot('cohort')}"

        retriever = _get_retriever()
        rag_res = retriever.search(effective_rag_query, top_k=5)
        hits = rag_res.get("ket_qua", [])

        resp_text, citation, follow_ups = _build_regulation_advisor_response(
            effective_rag_query, rag_res
        )
        session.add_message("assistant", resp_text)
        return {
            "status": "success",
            "intent": intent,
            "target_engine": target_engine,
            "response_text": resp_text,
            "data": {
                "total_matches": len(hits),
                "top_hit": hits[0] if hits else None,
                "can_hoi_lai": rag_res.get("can_hoi_lai", False),
                "can_hoi_khoa": rag_res.get("can_hoi_khoa", False),
                "session_state": session.state.value,
                "follow_ups": follow_ups,
            },
            "provenance": citation,
        }

    # ----------------------------------------------------
    # Nhánh C: Câu hỏi mơ hồ / Chào hỏi cần làm rõ (R5)
    # ----------------------------------------------------
    elif intent == INTENT_CLARIFY:
        session.set_state(DialogueState.AWAITING_CLARIFICATION)
        resp_text = (
            "Chào bạn! Mình là **H.E.R.M.E.S** — cố vấn học tập dành riêng cho "
            "sinh viên ĐH Khoa học Tự nhiên (ĐHQG-HCM).\n\n"
            "Hôm nay bạn đang cần mình tháo gỡ vấn đề nào? Bạn có thể nhắn trực tiếp "
            "hoặc chọn nhanh một chủ đề dưới đây:\n"
            "- **Tra cứu Quy chế & Chuẩn ngoại ngữ:** Kiểm tra điều kiện IELTS/TOEIC/VSTEP "
            "theo đúng khóa tuyển và ngành học của bạn.\n"
            "- **Tính điểm GPA & Đánh giá Học vụ:** Quy đổi điểm Hệ 10 sang Hệ 4 "
            "và kiểm tra nguy cơ cảnh báo học vụ.\n"
            "- **Quản lý Deadline & Lập lịch Ôn thi:** Bóc tách hạn nộp bài từ thông báo "
            "giảng viên/Moodle để bật thông báo nhắc hẹn và chia lịch học."
        )
        session.add_message("assistant", resp_text)
        return {
            "status": "needs_clarification",
            "intent": intent,
            "target_engine": target_engine,
            "response_text": resp_text,
            "data": {
                "session_state": session.state.value,
                "follow_ups": [
                    "Chuẩn đầu ra ngoại ngữ chương trình tăng cường tiếng Anh ngành CNTT là gì?",
                    "Tính GPA giúp mình: Giải tích 1 (8.5, 4TC), Cấu trúc dữ liệu (7.5, 4TC)",
                    "Xếp lịch ôn thi tuần sau cho mình, thứ 4 thi Toán và thứ 6 thi Lý",
                ],
            },
            "provenance": None,
        }

    # ----------------------------------------------------
    # Nhánh D: Trích xuất Deadline thông báo giảng viên (R4)
    # ----------------------------------------------------
    elif intent == INTENT_EXTRACT_DEADLINE:
        from hermes.ai.client import extract_announcement_info
        from hermes.engines.deadline_parser import compute_deadline_status

        session.set_state(DialogueState.IDLE)
        info = extract_announcement_info(clean_query)
        info_dict = info.to_dict()
        dl_status = compute_deadline_status(info.deadline)

        lines = [
            f"Mình đã trích xuất xong thông tin nhiệm vụ của môn **{info.course_name}**:\n",
            "| Hạng mục | Chi tiết trích xuất |",
            "| :--- | :--- |",
            f"| **Môn học** | **{info.course_name}** |",
            f"| **Nội dung nhiệm vụ** | {info.assignment_content} |",
            f"| **Hạn nộp (Deadline)** | `{info.deadline}` (**{dl_status['countdown_label']}**) |",
            f"| **Hình thức nộp** | {info.submission_format} |",
            f"| **Lưu ý khi nộp** | {info.other_requirements} |",
        ]
        if info.missing_fields:
            missing_vn = {
                "course_name": "Tên môn học",
                "assignment_content": "Nội dung bài tập",
                "deadline": "Thời hạn nộp",
                "submission_format": "Hình thức/Nơi nộp",
            }
            missing_labels = [missing_vn.get(m, m) for m in info.missing_fields]
            lines.append(
                f"\n*Lưu ý:* Trong thông báo gốc chưa nêu rõ **{', '.join(missing_labels)}**, "
                "bạn nhớ kiểm tra lại trên Moodle hoặc hỏi giảng viên nhé."
            )
        else:
            lines.append(
                "\n*Bạn có thể bấm nút **Lưu vào Bộ nhắc hạn Deadline** bên dưới để hệ thống "
                "tự động đếm ngược và bật thông báo nhắc bạn trước giờ nộp bài.*"
            )

        resp_text = "\n".join(lines)
        session.add_message("assistant", resp_text)
        return {
            "status": "success",
            "intent": intent,
            "target_engine": target_engine,
            "response_text": resp_text,
            "data": {
                **info_dict,
                "deadline_status": dl_status,
                "extracted_deadline_item": {
                    "course": info.course_name,
                    "summary": info.assignment_content,
                    "deadline": (
                        dl_status["normalized_dt"]
                        if dl_status["urgency"] != "unknown"
                        else info.deadline
                    ),
                    "description": f"Hình thức: {info.submission_format}. Lưu ý: {info.other_requirements}",
                },
                "session_state": session.state.value,
                "follow_ups": [
                    "Lập lịch ôn tập và làm bài trong 7 ngày tới giúp mình",
                    "Tính điểm GPA học kỳ này giúp mình",
                ],
            },
            "provenance": "Trích xuất thông báo có kiểm chứng chống ảo giác (Grounding Verified)",
        }

    # ----------------------------------------------------
    # Nhánh E: Lập lịch ôn tập (INTENT_SCHEDULING)
    # ----------------------------------------------------
    elif intent == INTENT_SCHEDULING:
        from hermes.engines.scheduler import generate_study_plan

        session.set_state(DialogueState.IDLE)
        last_grades = session.get_slot("last_grades")
        subjects, daily_hours, days_left = _parse_schedule_params_from_query(
            clean_query, session_grades=last_grades
        )
        plan = generate_study_plan(
            subjects=subjects,
            available_daily_hours=daily_hours,
            days_left=days_left,
        )

        total_hours = round(daily_hours * days_left, 1)
        prio_labels = {3: "Cao (Trọng tâm)", 2: "Trung bình", 1: "Cơ bản"}
        lines = [
            f"Dưới đây là kế hoạch phân bổ thời gian ôn tập cho **{len(plan)} học phần** "
            f"trong **{days_left} ngày tới** (với quỹ thời gian **{daily_hours:g} giờ/ngày**, "
            f"tổng cộng **{total_hours:g} giờ**):\n",
            "| Học phần | Số tín chỉ | Mức ưu tiên | Tổng giờ phân bổ | Thời lượng mỗi ngày | Gợi ý thực hiện |",
            "| :--- | :---: | :---: | :---: | :---: | :--- |",
        ]
        for item in plan:
            p_val = item.get("priority", 2)
            p_text = prio_labels.get(p_val, f"Mức {p_val}")
            d_hrs = item.get("daily_hours", 0.0)
            tip = (
                "Ôn vào khung giờ sáng/đầu buổi khi tập trung nhất"
                if p_val >= 3
                else (
                    "Luyện giải đề & bài tập thực hành"
                    if p_val == 2
                    else "Hệ thống hóa lý thuyết & ghi chú"
                )
            )
            lines.append(
                f"| **{item['name']}** | {item['credits']} TC | {p_text} "
                f"| **{item['allocated_hours']:g} giờ** | `{d_hrs:g} giờ/ngày` | {tip} |"
            )

        lines.append(
            "\n*Mẹo nhỏ: Nếu bạn muốn thay đổi danh sách môn thi, kéo thanh trượt điều chỉnh "
            "số ngày hoặc đồng bộ từ Deadline Moodle, hãy mở tab **Lập lịch Ôn thi & Dự báo GPA** nhé.*"
        )
        resp_text = "\n".join(lines)
        session.add_message("assistant", resp_text)
        return {
            "status": "success",
            "intent": intent,
            "target_engine": target_engine,
            "response_text": resp_text,
            "data": {
                "sample_plan": plan,
                "days_left": days_left,
                "daily_hours": daily_hours,
                "session_state": session.state.value,
                "follow_ups": [
                    "Xếp lịch ôn thi trong 5 ngày với 4 giờ mỗi ngày cho môn Giải tích và Cấu trúc dữ liệu",
                    "Chuẩn đầu ra ngoại ngữ chương trình đại trà là gì?",
                ],
            },
            "provenance": "Thuật toán Phân bổ Thời gian Ôn tập Tất định (EDF & Trọng số Tín chỉ)",
        }

    else:
        return {
            "status": "success",
            "intent": intent,
            "target_engine": target_engine,
            "response_text": route_info.get("message", "Yêu cầu đã được tiếp nhận."),
            "data": {**extracted, "session_state": session.state.value},
            "provenance": None,
        }
