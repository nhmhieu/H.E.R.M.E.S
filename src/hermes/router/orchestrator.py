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
    "gpa", "điểm", "tính điểm", "tính gpa", "cảnh báo học vụ", "buộc thôi học",
    "học vụ", "tín chỉ tích lũy", "thang điểm 10", "thang điểm 4", "quy đổi điểm",
    "điểm rèn luyện", "học bổng", "xếp loại", "học kỳ", "what-if", "dự báo điểm"
]

SCHEDULING_KEYWORDS = [
    "lịch", "lịch thi", "xếp lịch", "lập lịch", "thời gian biểu", "ôn thi",
    "kế hoạch học", "thời khóa biểu", "phân bổ giờ", "giờ rảnh", "schedule",
    "study plan", "ngày thi", "học bài"
]

REGULATION_KEYWORDS = [
    "quy chế", "sổ tay", "điều khoản", "chuẩn đầu ra", "tiếng anh", "toeic",
    "ielts", "vstep", "học lại", "học cải thiện", "rút học phần", "rút môn",
    "đăng ký học phần", "chuyển ngành", "bảo lưu", "tốt nghiệp", "điều kiện tốt nghiệp",
    "miễn giảm", "chứng chỉ", "phòng đào tạo"
]

DEADLINE_KEYWORDS = [
    "deadline", "hạn nộp", "thông báo:", "bài tập lab", "nộp bài",
    ".ics", "ical", "moodle", "hạn chót", "thầy gửi", "cô gửi"
]

CLARIFY_TRIGGERS = [
    "cứu em", "cứu mình", "giúp em", "giúp mình", "alo", "ad ơi",
    "admin ơi", "chào bạn", "hello", "hi", "ơi"
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
            "message": "Vui lòng nhập câu hỏi hoặc yêu cầu cần trợ giúp."
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
            "message": "Yêu cầu vi phạm quy định an toàn hoặc nằm ngoài phạm vi hỗ trợ (Hệ thống không giải bài tập hộ sinh viên)."
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
                    "message": "Chào bạn! Bạn cần H.E.R.M.E.S hỗ trợ về tính điểm GPA, lập lịch ôn thi hay tra cứu quy chế học vụ?"
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
            "message": "Trích xuất deadline và thông tin bài tập."
        }

    # If scores are all 0
    max_score = max(gpa_score, sched_score, reg_score)
    if max_score == 0:
        return {
            "intent": INTENT_CLARIFY,
            "confidence": 0.50,
            "target_engine": "clarifier",
            "extracted_params": {},
            "message": "Câu hỏi chưa rõ ràng. Bạn có thể nói rõ hơn về vấn đề học vụ hoặc lịch học cần giúp đỡ không?"
        }

    # Scheduling intent
    if sched_score > gpa_score and sched_score >= reg_score:
        return {
            "intent": INTENT_SCHEDULING,
            "confidence": min(0.60 + sched_score * 0.15, 0.98),
            "target_engine": "scheduler_engine",
            "extracted_params": {},
            "message": "Định tuyến tới bộ lập lịch ôn tập."
        }

    # GPA Calculation intent
    if gpa_score >= sched_score and gpa_score >= reg_score:
        return {
            "intent": INTENT_CALC_GPA,
            "confidence": min(0.60 + gpa_score * 0.15, 0.98),
            "target_engine": "academic_engine",
            "extracted_params": {},
            "message": "Định tuyến tới bộ tính toán học vụ và GPA."
        }

    # Regulation / RAG intent
    return {
        "intent": INTENT_REGULATION_RAG,
        "confidence": min(0.60 + reg_score * 0.15, 0.98),
        "target_engine": "rag_retriever",
        "extracted_params": {},
        "message": "Định tuyến tới bộ tra cứu quy chế và sổ tay sinh viên."
    }
