# import re


# def sanitize_input(text: str) -> tuple[bool, str]:
#     """
#     Check for prompt injection patterns, forbidden keywords, and excessive length.
#     Returns a tuple of (is_safe, message).
#     """
#     if not text:
#         return False, "Input cannot be empty."

#     if len(text) > 1000:
#         return False, "Input exceeds maximum allowed length of 1000 characters."

#     # Very basic prompt injection patterns (for demonstration)
#     injection_patterns = [
#         r"ignore all previous instructions",
#         r"system prompt",
#         r"bypass",
#         r"you are now",
#         r"jailbreak",
#     ]

#     text_lower = text.lower()

#     for pattern in injection_patterns:
#         if re.search(pattern, text_lower):
#             return False, "Potential prompt injection detected."

#     # Forbidden keywords (e.g., related to non-goals like doing homework)
#     forbidden_keywords = [
#         "do my homework",
#         "write code for me",
#         "solve this assignment",
#     ]

#     for keyword in forbidden_keywords:
#         if keyword in text_lower:
#             return (
#                 False,
#                 "Request violates system boundaries (e.g., asking to do homework).",
#             )

#     return True, "Input is safe."
"""
Security Guardrails module for H.E.R.M.E.S (Member 4 - AI & System Security).

Provides multi-layer input validation, prompt injection detection,
homework policy enforcement, and text sanitization before routing to LLM engines.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import re

DEFAULT_MAX_INPUT_LENGTH = 1000

# Zero-width and invisible formatting characters often used to bypass filters
ZERO_WIDTH_CHARS = {
    "\u200b",  # Zero-width space
    "\u200c",  # Zero-width non-joiner
    "\u200d",  # Zero-width joiner
    "\u2060",  # Word joiner
    "\ufeff",  # Zero-width no-break space (BOM)
    "\u00ad",  # Soft hyphen
}

# Regular expression patterns for Prompt Injection detection (VN & EN)
INJECTION_PATTERNS = [
    (
        r"ignore\s+(?:all\s+|any\s+|the\s+)?"
        r"(?:previous|prior|above)\s+(?:instructions|prompts|rules)"
    ),
    (
        r"disregard\s+(?:all\s+|any\s+)?"
        r"(?:previous|prior|above)\s+(?:instructions|prompts|rules)"
    ),
    r"forget\s+(?:all\s+|everything\s+)?(?:previous|prior|above)",
    (
        r"bỏ\s+qua\s+(?:mọi\s+|tất\s+cả\s+|các\s+)?"
        r"(?:chỉ\s+dẫn|hướng\s+dẫn|quy\s+tắc|lệnh)\s*(?:trước|ở\s+trên)?"
    ),
    (
        r"phớt\s+lờ\s+(?:mọi\s+|tất\s+cả\s+|các\s+)?"
        r"(?:chỉ\s+dẫn|hướng\s+dẫn|quy\s+tắc)"
    ),
    r"system\s*prompt",
    r"developer\s*(?:mode|prompt|instructions)",
    r"chế\s+độ\s+(?:nhà\s+phát\s+triển|phát\s+triển|quản\s+trị|debug)",
    r"you\s+are\s+now\s+(?:a|an|in\s+developer|unrestricted|dan\b)",
    r"bạn\s+bây\s+giờ\s+là",
    r"từ\s+giờ\s+bạn\s+là",
    r"jailbreak",
    r"vượt\s+rào",
    (
        r"bypass\s*(?:filter|guardrail|security|restriction"
        r"|policy|rule|lọc|bảo\s+mật)?"
    ),
    r"vô\s+hiệu\s+hóa\s+(?:bộ\s+lọc|guardrail|bảo\s+mật|quy\s+tắc)",
    (
        r"(?:reveal|show|print|output|repeat|dump)\s+(?:your\s+|the\s+)?"
        r"(?:system|initial|hidden|secret|internal)\s*"
        r"(?:prompt|instructions|config|key|rules)"
    ),
    (
        r"(?:tiết\s+lộ|hiển\s+thị|in\s+ra|cho\s+tôi\s+xem)\s+"
        r"(?:toàn\s+bộ\s+)?(?:system\s*prompt|chỉ\s+dẫn\s+hệ\s+thống"
        r"|cấu\s+hình\s+bí\s+mật|api\s*key)"
    ),
    r"(?:\brole\b|\bvai\s+trò\b)\s*[:=]\s*(?:system|developer|admin|root)",
    r"\[\s*(?:system|developer|admin|override)\s*\]",
    r"<\s*(?:system|developer|admin)\s*>",
    r"ghi\s+đè\s+(?:chính\s+sách|system\s*prompt|quy\s+tắc|bảo\s+mật)",
    (
        r"override\s+(?:system|security|safety)\s+"
        r"(?:policy|prompt|rules|instructions)"
    ),
]

# Patterns for demanding raw/direct answers without explanation (Always blocked)
DIRECT_ANSWER_PATTERNS = [
    (
        r"chỉ\s+(?:cần\s+)?(?:trả\s+lời\s+|cho\s+|đưa\s+|xin\s+|lấy\s+)*"
        r"(?:mình\s+|tôi\s+|em\s+)?đáp\s+án(?:.*?)không\s+(?:cần\s+)?giải\s+thích"
    ),
    (
        r"(?:đưa|cho|trả|xin)\s+đáp\s+án\s+(?:cuối\s+cùng\s+|luôn\s+|trực\s+tiếp\s+)?"
        r"(?:,\s*|\s+)không\s+(?:cần\s+)?giải\s+thích"
    ),
    (
        r"không\s+(?:cần\s+)?giải\s+thích\s*(?:,\s*|\s+)"
        r"chỉ\s+(?:cần\s+)?(?:cho\s+|đưa\s+|xin\s+|lấy\s+)*đáp\s+án"
    ),
    (
        r"(?:give|provide|tell|send)\s+me\s+(?:only\s+|just\s+)?"
        r"the\s+(?:final\s+|exact\s+|direct\s+)?answer(?:.*)"
        r"(?:no|without)\s+explanation"
    ),
    (
        r"just\s+(?:give\s+me\s+)?the\s+(?:final\s+)?(?:answer|code|solution)"
        r"(?:.*)(?:no|without)\s+(?:explanation|explaining)"
    ),
]

# Patterns indicating a student is asking for a hint, explanation, or concept
LEARNING_INTENT_PATTERNS = [
    r"\bgợi\s+ý\b",
    r"\bhướng\s+dẫn\s+(?:cách|phương\s+pháp|hướng)\b",
    r"(?<!không\s)(?<!không\scần\s)\bgiải\s+thích\b",
    r"\bkhái\s+niệm\b",
    r"\bý\s+tưởng\b",
    r"\bphương\s+pháp\b",
    r"\blàm\s+sao\s+để\s+hiểu\b",
    r"\btại\s+sao\b",
    r"\bhint\b",
    r"(?<!no\s)(?<!without\s)\bexplain\b",
    r"\bhow\s+does\b",
    r"\bconcept\b",
    r"\bapproach\b",
    r"\bstep\s+by\s+step\s+guide\b",
]

# Strict forbidden patterns for complete homework solving
FORBIDDEN_HOMEWORK_PATTERNS = [
    r"do\s+my\s+(?:homework|assignment|lab|exam|test)",
    r"write\s+(?:the\s+)?(?:full\s+|complete\s+|entire\s+)?code\s+for\s+me",
    (
        r"solve\s+this\s+(?:entire\s+|whole\s+)?"
        r"(?:assignment|homework|problem|exam)"
        r"(?:\s+for\s+me|\s+completely)?"
    ),
    (
        r"(?:làm|giải)\s+(?:hộ|giúp|dùm)\s+(?:tôi\s+|mình\s+|em\s+)?"
        r"(?:toàn\s+bộ\s+|trọn\s+vẹn\s+|hết\s+)?"
        r"(?:bài\s+tập|đề\s+bài|bài\s+thi|bài\s+kiểm\s+tra|bài\s+lab|assignment)"
    ),
    (
        r"giải\s+(?:toàn\s+bộ|trọn\s+vẹn|hết|chi\s+tiết\s+từng\s+bước\s+ra\s+đáp\s+án)\s+"
        r"(?:bài\s+tập|đề\s+bài|bài\s+toán)(?:\s+này)?(?:\s+cho\s+(?:tôi|mình|em))?"
    ),
    (
        r"viết\s+(?:hộ\s+|giúp\s+)?(?:toàn\s+bộ\s+|trọn\s+vẹn\s+)?code\s+"
        r"(?:giải\s+)?(?:bài\s+tập\s+)?cho\s+(?:tôi|mình|em)"
    ),
]


@dataclass(frozen=True)
class GuardrailResult:
    """Structured result returned by the security guardrail pipeline."""

    allowed: bool
    cleaned_text: str
    reason: str
    category: str


def _get_max_input_length(override_max_length: int | None = None) -> int:
    """Resolve max input length from parameter or environment variable."""
    if override_max_length is not None:
        return override_max_length
    raw_env = os.getenv("HERMES_MAX_INPUT_LENGTH", str(DEFAULT_MAX_INPUT_LENGTH))
    try:
        val = int(raw_env)
        return val if val > 0 else DEFAULT_MAX_INPUT_LENGTH
    except ValueError:
        return DEFAULT_MAX_INPUT_LENGTH


def _normalize_for_detection(text: str) -> str:
    """
    Create a normalized lowercase copy of text for security scanning:
    - Strip zero-width characters
    - Collapse spaced-out letters (obfuscation defense) BEFORE collapsing
      whitespace, so the wider gaps between words are still visible
    - Collapse whitespace
    """
    no_zw = "".join(ch for ch in text if ch not in ZERO_WIDTH_CHARS)
    deobfuscated = _collapse_spaced_letters(no_zw)
    return " ".join(deobfuscated.split())


def _collapse_spaced_letters(text: str) -> str:
    """
    Detect obfuscated words where a single space/dot/hyphen is inserted between
    single characters (e.g., 'I.g.n.o.r.e' or 'i g n o r e').
    Only ONE separator is removed at a time: wider gaps between words
    (e.g. 'e   a') are kept, so patterns that expect whitespace between words
    still match after normalization.
    """
    return re.sub(r"(?<=\b[a-zA-Z])[\s._-](?=[a-zA-Z]\b)", "", text.lower())


def validate_and_clean(
    text: str,
    max_length: int | None = None,
) -> GuardrailResult:
    """
    Comprehensive multi-layer security guardrail pipeline.
    Returns a GuardrailResult with:
      - allowed: whether the query is safe to pass to Member 1 / AI Engine
      - cleaned_text: normalized query (strictly "" when rejected)
      - reason: human-readable explanation
      - category: violation category for automated testing
    """
    if not isinstance(text, str):
        return GuardrailResult(
            allowed=False,
            cleaned_text="",
            reason="Input cannot be empty or non-string.",
            category="empty_input",
        )

    limit = _get_max_input_length(max_length)

    # Layer A1: Empty or whitespace-only check
    stripped = text.strip()
    if not stripped:
        return GuardrailResult(
            allowed=False,
            cleaned_text="",
            reason="Input cannot be empty.",
            category="empty_input",
        )

    # Layer A2: Maximum length check
    if len(text) > limit:
        return GuardrailResult(
            allowed=False,
            cleaned_text="",
            reason=f"Input exceeds maximum allowed length of {limit} characters.",
            category="excessive_length",
        )

    # Layer A3: Invisible/zero-width characters or abnormal control characters
    has_zero_width = any(ch in ZERO_WIDTH_CHARS for ch in text)
    control_chars_count = sum(1 for ch in text if ord(ch) < 32 and ch not in "\t\n\r")
    if has_zero_width or control_chars_count > 0:
        return GuardrailResult(
            allowed=False,
            cleaned_text="",
            reason=(
                "Potential prompt injection or obfuscation detected "
                "(hidden/control characters)."
            ),
            category="obfuscated_or_control_chars",
        )

    # Layer A4: Garbage / punctuation-only / repetitive noise check
    has_alnum = any(ch.isalnum() for ch in stripped)
    no_space = "".join(stripped.split())
    is_repetitive_noise = (
        len(no_space) >= 8 and len(set(no_space.lower())) <= 2
    ) or bool(re.search(r"(.)\1{9,}", no_space.lower()))

    if not has_alnum or is_repetitive_noise:
        return GuardrailResult(
            allowed=False,
            cleaned_text="",
            reason="Input contains invalid repetitive noise or lacks meaningful text.",
            category="garbage_input",
        )

    # Layer B: Prompt Injection detection (checks normal and de-obfuscated text)
    scan_text = _normalize_for_detection(stripped)
    deobfuscated_text = _collapse_spaced_letters(stripped)

    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, scan_text, re.IGNORECASE) or re.search(
            pattern, deobfuscated_text, re.IGNORECASE
        ):
            return GuardrailResult(
                allowed=False,
                cleaned_text="",
                reason="Potential prompt injection detected.",
                category="prompt_injection",
            )

    # Layer C: Homework Policy Enforcement
    for pattern in DIRECT_ANSWER_PATTERNS:
        if re.search(pattern, scan_text, re.IGNORECASE):
            return GuardrailResult(
                allowed=False,
                cleaned_text="",
                reason=(
                    "Request violates system boundaries "
                    "(e.g., asking to do homework or only providing raw answers)."
                ),
                category="homework_policy_violation",
            )

    has_learning_intent = any(
        re.search(pat, scan_text, re.IGNORECASE) for pat in LEARNING_INTENT_PATTERNS
    )

    if not has_learning_intent:
        for pattern in FORBIDDEN_HOMEWORK_PATTERNS:
            if re.search(pattern, scan_text, re.IGNORECASE):
                return GuardrailResult(
                    allowed=False,
                    cleaned_text="",
                    reason=(
                        "Request violates system boundaries "
                        "(e.g., asking to do homework)."
                    ),
                    category="homework_policy_violation",
                )

    # Layer D: Safe Content Normalization (preserve math symbols & academic syntax)
    cleaned_normalized = " ".join(stripped.split())

    return GuardrailResult(
        allowed=True,
        cleaned_text=cleaned_normalized,
        reason="Input is safe.",
        category="safe",
    )


def sanitize_input(text: str) -> tuple[bool, str]:
    """
    Public interface used by CLI (`src/hermes/cli.py`) and existing unit tests.
    Returns a tuple of (is_safe, message).
    """
    result = validate_and_clean(text)
    return result.allowed, result.reason
