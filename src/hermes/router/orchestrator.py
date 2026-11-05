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
    # Check for Deadline extraction first if text looks like an announcement
    if dl_score >= 2 or (".ics" in query_lower) or ("thông báo:" in query_lower):
        return {
            "intent": INTENT_EXTRACT_DEADLINE,
            "confidence": 0.90,
            "target_engine": "ai_extractor",
            "extracted_params": {"raw_text": clean_query},
            "message": "Trích xuất deadline và thông tin bài tập.",
        }

    # If scores are all 0
    max_score = max(gpa_score, sched_score, reg_score)
    if max_score == 0:
        return {
            "intent": INTENT_CLARIFY,
            "confidence": 0.50,
            "target_engine": "clarifier",
            "extracted_params": {},
            "message": "Câu hỏi chưa rõ ràng. Bạn có thể nói rõ hơn về vấn đề học vụ hoặc lịch học cần giúp đỡ không?",
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


def _get_retriever():
    global _RETRIEVER_INSTANCE
    if _RETRIEVER_INSTANCE is None:
        from hermes.rag.retriever import KeywordRetriever

        _RETRIEVER_INSTANCE = KeywordRetriever()
    return _RETRIEVER_INSTANCE


def _classify_academic_rank(gpa_10: float) -> str:
    """Phân loại học lực theo thang điểm 10 chuẩn HCMUS."""
    if gpa_10 >= 9.0:
        return "Xuất sắc 🌟"
    if gpa_10 >= 8.0:
        return "Giỏi 🏆"
    if gpa_10 >= 7.0:
        return "Khá 👍"
    if gpa_10 >= 6.0:
        return "Trung bình khá 📈"
    if gpa_10 >= 5.0:
        return "Trung bình ⚠️"
    return "Yếu / Nguy cơ cảnh báo 🚨"


def orchestrate(query: str, session_id: str = "default_user") -> Dict[str, Any]:
    """
    Master Pipeline điều phối toàn bộ hệ thống H.E.R.M.E.S.

    Quy trình:
    1. Quét an toàn qua Guardrails (R7)
    2. Phân loại ý định qua Router 2 tầng (R5)
    3. Điều hướng xử lý sang GPA Engine (R2), Scheduler (R2), RAG Quy chế (R3) hoặc AI (R4)
    4. Định dạng câu trả lời thân thiện, chuyên nghiệp cho Giao diện UI/CLI (R6)
    """
    from hermes.security.guardrails import validate_and_clean
    from hermes.engines.academic_calc import (
        calculate_gpa_10,
        calculate_gpa_4,
        check_academic_warning,
        convert_score_to_4_and_letter,
    )

    # 1. Quét an toàn đầu vào (R7)
    guard_res = validate_and_clean(query)
    if not guard_res.allowed:
        if guard_res.category == "academic_integrity":
            friendly_reject = (
                "🛡️ **Chính sách Liêm chính Học thuật (Academic Integrity)**\n\n"
                "Mình rất tiếc không thể giải trực tiếp bài tập hoặc viết code làm hộ đồ án được "
                f"(*Lý do: {guard_res.reason}*).\n\n"
                "💡 **Gợi ý từ H.E.R.M.E.S:** Dù không thể làm bài giúp bạn, mình luôn sẵn sàng hỗ trợ:\n"
                "- 📅 **Chia nhỏ lộ trình ôn tập & làm đồ án** theo thuật toán ưu tiên hạn chót (EDF).\n"
                "- 📥 **Bóc tách yêu cầu & hạn nộp (Deadline)** từ thông báo của giảng viên.\n"
                "- 🎯 **Tính điểm mục tiêu (What-If GPA)** để biết môn này cần đạt tối thiểu bao nhiêu điểm!"
            )
        else:
            friendly_reject = (
                "🛡️ **Hệ thống Bảo vệ An toàn H.E.R.M.E.S (Guardrails)**\n\n"
                f"Yêu cầu bị từ chối: {guard_res.reason}.\n\n"
                "💡 Bạn vui lòng đặt các câu hỏi liên quan đến **Quy chế học vụ HCMUS**, "
                "**Chuẩn đầu ra ngoại ngữ**, **Tính điểm GPA** hoặc **Lập lịch ôn thi** nhé!"
            )
        return {
            "status": "blocked",
            "intent": INTENT_REJECT,
            "target_engine": "guardrails",
            "response_text": friendly_reject,
            "data": {"category": guard_res.category},
            "provenance": None,
        }

    clean_query = guard_res.cleaned_text

    # 2. Phân loại ý định qua Router (R5)
    route_info = route_query(clean_query)
    intent = route_info["intent"]
    target_engine = route_info["target_engine"]
    extracted = route_info.get("extracted_params", {})

    # 3. Điều phối theo Intent
    # ----------------------------------------------------
    # Nhánh A: Tính điểm học vụ GPA (R2)
    # ----------------------------------------------------
    if intent == INTENT_CALC_GPA:
        grades = extracted.get("grades", [])
        if grades:
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
                f"🎓 **Kết quả Phân tích Điểm Học vụ ({len(grades)} học phần • Tổng {total_tc} tín chỉ)**\n",
                f"- **Điểm trung bình Hệ 10:** `{gpa_10:.2f} / 10.0`",
                f"- **Điểm trung bình Hệ 4:** `{gpa_4:.2f} / 4.0`",
                f"- **Xếp loại học lực dự kiến:** **{rank_label}**",
                f"- **Tín chỉ tích lũy đạt:** `{passed_tc}/{total_tc} TC`\n",
                "| Môn học / Học phần | Số tín chỉ | Điểm hệ 10 | Điểm hệ 4 | Điểm chữ | Kết quả |",
                "| :--- | :---: | :---: | :---: | :---: | :---: |",
            ]
            for g in grades:
                s4, letter = convert_score_to_4_and_letter(g["grade"])
                status_icon = "✅ Đạt" if g["grade"] >= 5.0 else "⚠️ Học lại"
                lines.append(
                    f"| **{g['subject']}** | {g['credits']} TC | `{g['grade']:.1f}` "
                    f"| `{s4:.1f}` | **{letter}** | {status_icon} |"
                )

            if warn_info["is_warning"]:
                lines.append(
                    f"\n⚠️ **Cảnh báo từ Cố vấn Học tập (Điều 16 - QĐ 1175):** "
                    f"Hiện tại bảng điểm của bạn có nguy cơ rơi vào diện **{warn_info['status']}** "
                    f"({'; '.join(warn_info['reasons'])}). Bạn nên ưu tiên đăng ký trả nợ các môn "
                    "dưới 5.0 và dùng tab **Mô phỏng Điểm mục tiêu (What-If GPA)** để lên kế hoạch kéo điểm nhé!"
                )
            elif gpa_10 >= 8.0:
                lines.append(
                    "\n💡 **Nhận xét từ H.E.R.M.E.S:** Kết quả học tập của bạn rất ấn tượng! "
                    "Hãy duy trì phong độ này để đủ điều kiện xét **Học bổng Khuyến khích Học tập** của trường nhé."
                )
            else:
                lines.append(
                    "\n💡 **Gợi ý từ H.E.R.M.E.S:** Trạng thái học vụ của bạn hoàn toàn **Bình thường (An toàn)**. "
                    "Nếu muốn nhắm tới mức GPA Giỏi (8.0+), bạn có thể thử công cụ **Dự báo What-If GPA** ở Tab 2 nhé!"
                )

            return {
                "status": "success",
                "intent": intent,
                "target_engine": target_engine,
                "response_text": "\n".join(lines),
                "data": {"gpa_10": gpa_10, "gpa_4": gpa_4, "grades": grades},
                "provenance": "Quy chế Đào tạo tín chỉ Trường ĐH Khoa học Tự nhiên, ĐHQG-HCM (QĐ 1175/QĐ-KHTN)",
            }
        else:
            return {
                "status": "needs_info",
                "intent": intent,
                "target_engine": target_engine,
                "response_text": (
                    "Chào bạn! Mình sẵn sàng tính **GPA Hệ 10, Hệ 4** và kiểm tra "
                    "**nguy cơ Cảnh báo học vụ (Điều 16)** giúp bạn ngay.\n\n"
                    "✍️ **Cách nhập nhanh trong khung chat:** Bạn hãy nhắn danh sách môn kèm điểm "
                    "và số tín chỉ theo mẫu:\n"
                    "- *Ví dụ 1:* `Tính GPA giúp mình: Giải tích 1 (8.5, 4TC), "
                    "Cấu trúc dữ liệu (7.5, 4 tín), Pháp luật (9.0, 2TC)`\n"
                    "- *Ví dụ 2:* `Tính GPA: 8.0 (4TC), 7.5 (3TC), 6.5 (3TC)`\n\n"
                    "👉 Hoặc bạn cũng có thể nhập trực tiếp từng môn ở bảng "
                    "**📊 Tính điểm GPA & Học vụ** ngay thanh bên trái màn hình nhé!"
                ),
                "data": extracted,
                "provenance": None,
            }

    # ----------------------------------------------------
    # Nhánh B: Tra cứu quy chế RAG (R3)
    # ----------------------------------------------------
    elif intent == INTENT_REGULATION_RAG:
        retriever = _get_retriever()
        rag_res = retriever.search(clean_query, top_k=5)
        hits = rag_res.get("ket_qua", [])

        if hits:
            top_hit = hits[0]
            q_lower = clean_query.lower()
            if "hồ sơ" not in q_lower and "thủ tục" not in q_lower:
                for h in hits:
                    if h.get("chung_chi_toi_thieu"):
                        top_hit = h
                        break

            citation = top_hit.get("trich_dan", "Sổ tay sinh viên HCMUS")
            pham_vi = top_hit.get("pham_vi", "")
            content = top_hit.get("text", "").strip()

            lines = [
                "👋 **Chào bạn! Dưới đây là thông tin quy chế chính thức từ "
                "Trường ĐH Khoa học Tự nhiên (ĐHQG-HCM):**\n",
                f"- 📄 **Văn bản pháp quy:** **{citation}**",
            ]
            if pham_vi:
                lines.append(f"- 🎯 **Đối tượng / Phạm vi áp dụng:** `{pham_vi}`")

            lines.append("\n#### 📖 Nội dung quy định chi tiết")
            lines.append(f"> {content}")

            cert_dict = top_hit.get("chung_chi_toi_thieu")
            if cert_dict:
                lines.append("\n#### 🏆 Bảng quy đổi Chứng chỉ Ngoại ngữ tối thiểu")
                lines.append("| Loại Chứng chỉ / Bài thi | Mức điểm / Bậc tối thiểu yêu cầu |")
                lines.append("| :--- | :--- |")
                for cert_name, cert_val in cert_dict.items():
                    lines.append(f"| **{cert_name}** | `{cert_val}` |")

            other_hits = [h for h in hits if h is not top_hit][:2]
            if other_hits:
                lines.append("\n**🔎 Các điều khoản liên quan khác bạn có thể tham khảo:**")
                for oh in other_hits:
                    oh_cit = oh.get("trich_dan", "Quy chế HCMUS")
                    oh_pv = f" (*{oh.get('pham_vi')}*)" if oh.get("pham_vi") else ""
                    lines.append(f"- 📌 {oh_cit}{oh_pv}")

            lines.append(
                "\n💡 *Mẹo nhỏ: Nếu bạn muốn tra cứu riêng cho một khóa cụ thể (K21–K25) hoặc chương trình "
                "(Hệ Chuẩn / Tăng cường Tiếng Anh / Tiên tiến), hãy ghi kèm tên khóa vào câu hỏi nhé!*"
            )

            return {
                "status": "success",
                "intent": intent,
                "target_engine": target_engine,
                "response_text": "\n".join(lines),
                "data": {"total_matches": len(hits), "top_hit": top_hit},
                "provenance": citation,
            }
        else:
            return {
                "status": "success",
                "intent": intent,
                "target_engine": target_engine,
                "response_text": (
                    "Hiện tại mình chưa tìm thấy điều khoản quy chế khớp chính xác 100% với từ khóa này "
                    "trong bộ 17 văn bản Sổ tay Sinh viên HCMUS.\n\n"
                    "💡 **Gợi ý:** Bạn thử hỏi cụ thể hơn về **Chuẩn đầu ra ngoại ngữ (IELTS/TOEIC/VSTEP)**, "
                    "**Cảnh báo học vụ (Điều 16)**, **Học cải thiện điểm**, hoặc **Điều kiện tốt nghiệp** nhé!"
                ),
                "data": {"total_matches": 0},
                "provenance": None,
            }

    # ----------------------------------------------------
    # Nhánh C: Câu hỏi mơ hồ / Chào hỏi cần làm rõ (R5)
    # ----------------------------------------------------
    elif intent == INTENT_CLARIFY:
        return {
            "status": "needs_clarification",
            "intent": intent,
            "target_engine": target_engine,
            "response_text": (
                "👋 **Xin chào! Mình là H.E.R.M.E.S – Trợ lý Học vụ Thông minh dành cho sinh viên HCMUS.**\n\n"
                "Mình có thể hỗ trợ bạn ngay 4 mảng công việc sau:\n"
                "1. 📖 **Tra cứu Quy chế & Chuẩn Ngoại ngữ:** Hỏi đáp chính xác từ 17 văn bản pháp quy "
                "(K21–K25, Chuẩn, TCTA, Tiên tiến).\n"
                "2. 🧮 **Tính GPA Hệ 10 / Hệ 4 & Cảnh báo Học vụ:** Quy đổi điểm chuẩn Quyết định 1175 "
                "và kiểm tra Điều 16.\n"
                "3. 📅 **Lập lịch Ôn thi Tự động (EDF):** Phân bổ giờ học tối ưu theo hạn thi, "
                "số tín chỉ và độ khó.\n"
                "4. 📥 **Bóc tách Deadline Bài tập:** Trích xuất thông báo giảng viên từ Moodle "
                "hoặc file lịch `.ics`.\n\n"
                "💬 *Bạn đang cần mình giúp về phần nào? Cứ nhắn tự nhiên ở bên dưới nhé!*"
            ),
            "data": {},
            "provenance": None,
        }

    # ----------------------------------------------------
    # Nhánh D: Trích xuất Deadline thông báo giảng viên (R4)
    # ----------------------------------------------------
    elif intent == INTENT_EXTRACT_DEADLINE:
        from hermes.ai.client import extract_announcement_info

        info = extract_announcement_info(clean_query)
        info_dict = info.to_dict()
        lines = [
            "📅 **Phiếu Tóm tắt Nhiệm vụ & Hạn nộp (Extracted Task Card)**\n",
            "| Hạng mục | Nội dung trích xuất |",
            "| :--- | :--- |",
            f"| 📚 **Môn học** | **{info.course_name}** |",
            f"| 📝 **Nội dung bài tập** | {info.assignment_content} |",
            f"| ⏰ **Hạn chót (Deadline)** | `{info.deadline}` |",
            f"| 📤 **Hình thức nộp bài** | {info.submission_format} |",
            f"| ⚠️ **Lưu ý / Yêu cầu khác** | {info.other_requirements} |",
            "\n💡 *Lời khuyên: Bạn nên hoàn thành và nộp bài lên Moodle trước hạn chót "
            "ít nhất 2 tiếng để tránh nghẽn mạng nhé!*",
        ]
        return {
            "status": "success",
            "intent": intent,
            "target_engine": target_engine,
            "response_text": "\n".join(lines),
            "data": info_dict,
            "provenance": "H.E.R.M.E.S AI Announcement Extractor (R4)",
        }

    # ----------------------------------------------------
    # Nhánh E: Lập lịch ôn tập (INTENT_SCHEDULING) & Fallback
    # ----------------------------------------------------
    elif intent == INTENT_SCHEDULING:
        from hermes.engines.scheduler import generate_study_plan

        default_subjects = [
            {"name": "Toán Rời Rạc", "credits": 4, "priority": 3},
            {"name": "Cấu Trúc Dữ Liệu & Giải Thuật", "credits": 4, "priority": 2},
            {"name": "Kiến Trúc Máy Tính", "credits": 3, "priority": 1},
        ]
        sample_plan = generate_study_plan(
            default_subjects, available_hours_per_day=6.0, days_remaining=10
        )
        lines = [
            "🗓️ **Kế hoạch Phân bổ Thời gian Ôn thi Gợi ý (Thuật toán EDF + Trọng số Tín chỉ)**\n",
            "Dựa trên nguyên tắc ưu tiên môn có **tín chỉ lớn** và **mức độ ưu tiên/độ khó cao**, "
            "dưới đây là lộ trình mẫu cho **10 ngày ôn tập (6 giờ/ngày = 60 giờ)**:\n",
            "| Môn học | Tín chỉ | Độ ưu tiên | Tổng giờ ôn tập | Thời lượng mỗi ngày | Khuyến nghị |",
            "| :--- | :---: | :---: | :---: | :---: | :--- |",
        ]
        for item in sample_plan:
            lines.append(
                f"| **{item['subject']}** | {item['credits']} TC | Mức {item['priority']} "
                f"| **{item['total_allocated_hours']} giờ** | `{item['daily_hours']} giờ/ngày` "
                f"| {item['recommendation']} |"
            )
        lines.append(
            "\n👉 **Tùy chỉnh theo lịch thi của riêng bạn:** Bạn hãy bấm sang tab "
            "**📅 Lập lịch Ôn thi & Dự báo GPA** ở phía trên để tự thêm môn học, ngày thi "
            "và kéo thanh trượt điều chỉnh số giờ rảnh mỗi ngày nhé!"
        )
        return {
            "status": "success",
            "intent": intent,
            "target_engine": target_engine,
            "response_text": "\n".join(lines),
            "data": {"sample_plan": sample_plan},
            "provenance": "H.E.R.M.E.S Deterministic EDF Study Scheduler (R2)",
        }

    else:
        return {
            "status": "success",
            "intent": intent,
            "target_engine": target_engine,
            "response_text": route_info.get("message", "Yêu cầu đã được tiếp nhận."),
            "data": extracted,
            "provenance": None,
        }
