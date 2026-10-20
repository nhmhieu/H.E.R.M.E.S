"""
Security Guardrails module for H.E.R.M.E.S (Member 4 - AI & System Security).

Provides multi-layer input validation, prompt injection detection,
homework policy enforcement, and text sanitization before routing to LLM engines.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
import unicodedata

DEFAULT_MAX_INPUT_LENGTH = 1000

# Zero-width and invisible formatting characters often used to bypass filters
ZERO_WIDTH_CHARS = {
    "\u200b",  # Zero-width space
    "\u200c",  # Zero-width non-joiner
    "\u200d",  # Zero-width joiner
    "\u200e",  # Left-to-right mark
    "\u200f",  # Right-to-left mark
    "\u202a",  # Left-to-right embedding
    "\u202b",  # Right-to-left embedding
    "\u202c",  # Pop directional formatting
    "\u202d",  # Left-to-right override
    "\u202e",  # Right-to-left override
    "\u2060",  # Word joiner
    "\u2066",  # Left-to-right isolate
    "\u2067",  # Right-to-left isolate
    "\u2068",  # First strong isolate
    "\u2069",  # Pop directional isolate
    "\ufeff",  # Zero-width no-break space (BOM)
    "\u00ad",  # Soft hyphen
}

# Regular expression patterns for Prompt Injection detection (VN & EN)
INJECTION_PATTERNS = [
    (
        r"ignore\s+(?:all\s+|any\s+|the\s+)?"
        r"(?:previous|prior|above|earlier|preceding|system|initial)\s+"
        r"(?:instructions|prompts|rules|directions|constraints|guidelines)"
    ),
    (
        r"disregard\s+(?:all\s+|any\s+|the\s+)?"
        r"(?:previous|prior|above|earlier|system)\s+"
        r"(?:instructions|prompts|rules|directions|constraints)"
    ),
    (
        r"forget\s+(?:all\s+|everything\s+|any\s+)?"
        r"(?:previous|prior|above|earlier|your\s+instructions|your\s+rules)"
    ),
    (
        r"bỏ\s+qua\s+(?:mọi\s+|tất\s+cả\s+|các\s+|toàn\s+bộ\s+)?"
        r"(?:chỉ\s+dẫn|hướng\s+dẫn|quy\s+tắc|lệnh|ràng\s+buộc|chính\s+sách)"
        r"(?:\s+(?:trước(?:\s+đó)?|ở\s+trên|ban\s+đầu|hệ\s+thống))?"
    ),
    (
        r"phớt\s+lờ\s+(?:mọi\s+|tất\s+cả\s+|các\s+|toàn\s+bộ\s+)?"
        r"(?:chỉ\s+dẫn|hướng\s+dẫn|quy\s+tắc|lệnh|chính\s+sách)"
    ),
    (
        r"quên\s+(?:hết\s+|mọi\s+|tất\s+cả\s+)?"
        r"(?:chỉ\s+dẫn|hướng\s+dẫn|quy\s+tắc|lệnh)"
        r"\s*(?:trước(?:\s+đó)?|ở\s+trên|ban\s+đầu)?"
    ),
    r"system\s*prompt",
    r"developer\s*(?:mode|prompt|instructions|override)",
    (
        r"chế\s+độ\s+"
        r"(?:nhà\s+phát\s+triển|phát\s+triển|quản\s+trị|debug|không\s+giới\s+hạn)"
    ),
    r"you\s+are\s+now\s+(?:a|an|in\s+developer|unrestricted|free\s+from|dan\b)",
    (
        r"act\s+as\s+(?:an?\s+)?"
        r"(?:unrestricted|unfiltered|jailbroken|developer|system|admin|root|dan\b)"
    ),
    r"bạn\s+bây\s+giờ\s+là",
    r"từ\s+giờ\s+bạn\s+là",
    (
        r"hãy\s+đóng\s+vai\s+(?:một\s+)?"
        r"(?:ai\s+không\s+bị\s+giới\s+hạn|hệ\s+thống\s+quản\s+trị"
        r"|developer|admin|root|dan\b)"
    ),
    r"jailbreak",
    r"vượt\s+rào",
    (
        r"bypass\s*(?:the\s+|all\s+|your\s+)?"
        r"(?:filter|filters|guardrail|guardrails|security|restriction"
        r"|restrictions|policy|policies|rule|rules|lọc|bảo\s+mật)?"
    ),
    (
        r"(?:vô\s+hiệu\s+hóa|tắt)\s+"
        r"(?:bộ\s+lọc|guardrail|guardrails|bảo\s+mật|quy\s+tắc|chính\s+sách)"
    ),
    (
        r"(?:disable|turn\s+off|deactivate)\s+(?:all\s+|the\s+|your\s+)?"
        r"(?:safety|security|guardrails?|filters?|restrictions?|policies|policy)"
    ),
    (
        r"(?:reveal|show|print|output|repeat|dump|display|leak|expose)\s+"
        r"(?:me\s+)?(?:your\s+|the\s+|all\s+)?"
        r"(?:system|initial|hidden|secret|internal|developer|original)\s*"
        r"(?:prompt|instructions|config|configuration|key|api\s*key|rules|env)"
    ),
    (
        r"(?:reveal|show|print|output|dump|leak|expose)\s+"
        r"(?:your\s+|the\s+)?"
        r"(?:api\s*key|secret\s*key|gemini_api_key|environment\s+variables)"
    ),
    (
        r"(?:tiết\s+lộ|hiển\s+thị|in\s+ra|cho\s+(?:tôi|mình|em)\s+xem"
        r"|xuất\s+ra|lặp\s+lại)\s+(?:toàn\s+bộ\s+)?"
        r"(?:system\s*prompt|chỉ\s+dẫn\s+hệ\s+thống|hướng\s+dẫn\s+hệ\s+thống"
        r"|cấu\s+hình\s+bí\s+mật|api\s*key|khóa\s+bí\s+mật)"
    ),
    r"(?:\brole\b|\bvai\s+trò\b)\s*[:=]\s*(?:system|developer|admin|root|superuser)",
    r"\[\s*(?:system\vert{}developer\vert{}admin\vert{}root\vert{}override\vert{}inst)\s*\]",
    r"<\s*\|?\s*(?:system|developer|admin|root|im_start)\s*\|?\s*>",
    r"(?:###|---)\s*(?:system|developer|admin|override|new\s+instructions)\b",
    (
        r"ghi\s+đè\s+"
        r"(?:chính\s+sách|system\s*prompt|quy\s+tắc|bảo\s+mật|hướng\s+dẫn|chỉ\s+dẫn)"
    ),
    (
        r"override\s+(?:all\s+|your\s+|the\s+)?"
        r"(?:system|security|safety|previous|existing)\s+"
        r"(?:policy|policies|prompt|rules|instructions|constraints)"
    ),
    (
        r"\bi(?:\s*[.\-_/~*|\\]\s*g)(?:\s*[.\-_/~*|\\]\s*n)"
        r"(?:\s*[.\-_/~*|\\]\s*o)(?:\s*[.\-_/~*|\\]\s*r)"
        r"(?:\s*[.\-_/~*|\\]\s*e)\b"
    ),
]

# Patterns for demanding raw/direct answers without explanation (Always blocked)
DIRECT_ANSWER_PATTERNS = [
    (
        r"chỉ\s+(?:cần\s+)?(?:trả\s+lời\s+|cho\s+|đưa\s+|xin\s+|lấy\s+)*"
        r"(?:mình\s+|tôi\s+|em\s+)?đáp\s+án(?:.*?)"
        r"(?:không\s+(?:cần\s+)?(?:phải\s+)?|đừng\s+|khỏi\s+|miễn\s+)giải\s+thích"
    ),
    (
        r"(?:đưa|cho|trả|xin|lấy)\s+(?:mình\s+|tôi\s+|em\s+)?đáp\s+án\s*"
        r"(?:cuối\s+cùng\s+|luôn\s+|trực\s+tiếp\s+|ngay\s+|thôi\s+)*"
        r"(?:,\s*|\s+|-\s*)"
        r"(?:không\s+(?:cần\s+)?(?:phải\s+)?|đừng\s+|khỏi\s+|miễn\s+)giải\s+thích"
    ),
    (
        r"(?:không\s+(?:cần\s+)?(?:phải\s+)?|đừng\s+|khỏi\s+|miễn\s+)giải\s+thích"
        r"(?:.*?)(?:chỉ\s+(?:cần\s+)?|đưa\s+|cho\s+|xin\s+|lấy\s+)đáp\s+án"
    ),
    (
        r"(?:give|provide|tell|send|show)\s+(?:me\s+)?(?:only\s+|just\s+)?"
        r"the\s+(?:final\s+|exact\s+|direct\s+|correct\s+)?(?:answer|solution|output)"
        r"(?:.*?)(?:no\s+|without\s+(?:any\s+)?|don'?t\s+|do\s+not\s+)"
        r"(?:explanation|explaining|explain)"
    ),
    (
        r"just\s+(?:give\s+me\s+|send\s+|output\s+)?"
        r"the\s+(?:final\s+|exact\s+|direct\s+)?(?:answer|code|solution)"
        r"(?:.*?)(?:no\s+|without\s+(?:any\s+)?|don'?t\s+|do\s+not\s+)"
        r"(?:explanation|explaining|explain)"
    ),
    (
        r"(?:no\s+|without\s+(?:any\s+)?)(?:explanation|explaining)\s*"
        r"(?:,\s*|\s+|-\s*)(?:just|only)\s+(?:give\s+(?:me\s+)?)?"
        r"(?:the\s+)?(?:final\s+|exact\s+)?(?:answer|solution|code)"
    ),
]

# Patterns indicating a student is asking for a hint, explanation, or concept
LEARNING_INTENT_PATTERNS = [
    r"\bgợi\s+ý\b",
    r"\bhướng\s+dẫn\s+(?:cách|phương\s+pháp|hướng|từng\s+bước)\b",
    (
        r"(?<!không\s)(?<!không\scần\s)(?<!không\sphải\s)"
        r"(?<!không\scần\sphải\s)(?<!đừng\s)(?<!khỏi\s)(?<!miễn\s)"
        r"\bgiải\s+thích\b"
    ),
    r"\bkhái\s+niệm\b",
    r"\bý\s+tưởng\b",
    r"\bphương\s+pháp\b",
    r"\bhướng\s+tiếp\s+cận\b",
    r"\blàm\s+sao\s+để\s+hiểu\b",
    r"\btại\s+sao\b",
    r"\bphân\s+tích\s+lỗi\b",
    r"\bsai\s+ở\s+đâu\b",
    r"\bhint\b",
    (
        r"(?<!no\s)(?<!without\s)(?<!not\s)(?<!don't\s)(?<!dont\s)"
        r"(?<!need\sto\s)\bexplain\b"
    ),
    r"(?<!no\s)(?<!without\s)(?<!without\sany\s)\bexplanation\b",
    r"\bhow\s+(?:does|do|to\s+understand)\b",
    r"\bconcept\b",
    r"\bapproach\b",
    r"\bstep\s+by\s+step\s+guide\b",
]

# Strict forbidden patterns for complete homework solving
FORBIDDEN_HOMEWORK_PATTERNS = [
    (
        r"do\s+my\s+(?:entire\s+|whole\s+|full\s+)?"
        r"(?:homework|assignment|lab|exam|test|project)"
    ),
    (
        r"write\s+(?:the\s+|my\s+)?"
        r"(?:full\s+|complete\s+|entire\s+|whole\s+)?code\s+for\s+me"
    ),
    (
        r"solve\s+this\s+(?:entire\s+|whole\s+|full\s+|complete\s+)?"
        r"(?:assignment|homework|problem|exam|lab|test)"
        r"(?:\s+for\s+me|\s+completely|\s+from\s+scratch)?"
    ),
    (
        r"complete\s+(?:this|my)\s+(?:entire\s+|whole\s+)?"
        r"(?:homework|assignment|lab|exam)\s+for\s+me"
    ),
    (
        r"(?:làm|giải)\s+(?:hộ|giúp|dùm|giùm)\s+(?:cho\s+)?(?:tôi\s+|mình\s+|em\s+)?"
        r"(?:toàn\s+bộ\s+|trọn\s+vẹn\s+|hết\s+|nguyên\s+)?"
        r"(?:bài\s+tập|đề\s+bài|bài\s+thi|bài\s+kiểm\s+tra"
        r"|bài\s+lab|đề\s+thi|assignment)"
    ),
    (
        r"giải\s+"
        r"(?:toàn\s+bộ|trọn\s+vẹn|hết|chi\s+tiết\s+từng\s+bước\s+ra\s+đáp\s+án)\s+"
        r"(?:bài\s+tập|đề\s+bài|bài\s+toán|đề\s+thi|bài\s+lab)"
        r"(?:\s+này)?(?:\s+cho\s+(?:tôi|mình|em))?"
    ),
    (
        r"viết\s+(?:hộ\s+|giúp\s+|dùm\s+|giùm\s+)?"
        r"(?:cho\s+(?:tôi|mình|em)\s+)?"
        r"(?:toàn\s+bộ\s+|trọn\s+vẹn\s+|hết\s+|full\s+)code\s+"
        r"(?:giải\s+)?(?:bài\s+tập|bài\s+lab|đề\s+bài|bài\s+toán)?"
    ),
    (
        r"viết\s+(?:hộ\s+|giúp\s+|dùm\s+|giùm\s+)"
        r"(?:toàn\s+bộ\s+|trọn\s+vẹn\s+|hết\s+|full\s+)?code\s+"
        r"(?:giải\s+)?(?:bài\s+tập\s+|bài\s+này\s+)?"
        r"(?:cho\s+(?:tôi|mình|em))?"
    ),
    (
        r"code\s+(?:hộ|giúp|dùm|giùm)\s+(?:tôi\s+|mình\s+|em\s+)?"
        r"(?:toàn\s+bộ\s+|hết\s+|trọn\s+vẹn\s+)?"
        r"(?:bài\s+tập|bài\s+lab|đồ\s+án|assignment)"
    ),
]

# Negation prefixes that indicate a student is explicitly stating they do NOT
# want the AI to solve the homework for them (e.g., "Đừng giải hộ bài tập...")
_NEGATED_HOMEWORK_PREFIX_RE = re.compile(
    r"(?:không\s+(?:cần|yêu\s+cầu|muốn|nhờ|đòi|bắt|phải)\s+"
    r"|đừng\s+|chứ\s+đừng\s+|thay\s+vì\s+"
    r"|not\s+(?:asking(?:\s+you)?\s+to\s+|to\s+)?"
    r"|don'?t\s+|do\s+not\s+|instead\s+of\s+)\s*$",
    re.IGNORECASE,
)

# Regex matching single Unicode letters separated by punctuation/underscores/dashes
_PUNCT_SEPARATED_LETTERS_RE = re.compile(
    r"(?<![^\W\d_])[^\W\d_](?:[\s]*[.\-_/~*|\\]+[\s]*[^\W\d_]){2,}(?![^\W\d_])",
    re.UNICODE,
)


@dataclass(frozen=True)
class GuardrailResult:
    """Structured result returned by the security guardrail pipeline."""

    allowed: bool
    cleaned_text: str
    reason: str
    category: str


def _get_max_input_length(override_max_length: int | None = None) -> int:
    """Resolve max input length from parameter or environment variable safely."""
    if override_max_length is not None:
        if (
            isinstance(override_max_length, int)
            and not isinstance(override_max_length, bool)
            and override_max_length > 0
        ):
            return override_max_length
        return DEFAULT_MAX_INPUT_LENGTH

    raw_env = os.getenv("HERMES_MAX_INPUT_LENGTH", str(DEFAULT_MAX_INPUT_LENGTH))
    try:
        val = int(str(raw_env).strip())
        return val if val > 0 else DEFAULT_MAX_INPUT_LENGTH
    except (ValueError, TypeError):
        return DEFAULT_MAX_INPUT_LENGTH


def _collapse_spaced_letters(text: str) -> str:
    """
    Reconstruct words obfuscated by inserting dots, hyphens, underscores, or
    spaces between single Unicode letters (e.g., 'I.g.n.o.r.e', 'I_g_n_o_r_e',
    'I g n o r e   a l l', or 'I g n o r e a l l').
    """
    lowered = text.lower()

    # Step 1: Collapse sequences of single letters joined by punctuation/separators
    def _strip_punct_separators(match: re.Match[str]) -> str:
        return "".join(ch for ch in match.group(0) if ch.isalnum())

    step1 = _PUNCT_SEPARATED_LETTERS_RE.sub(_strip_punct_separators, lowered)

    # Step 2: If single letters use single spaces while words use 2+ spaces,
    # remove the single space between single Unicode letters first.
    if re.search(r"[^\W\d_]\s{2,}[^\W\d_]", step1):
        step2 = re.sub(
            r"(?<![^\W\d_])([^\W\d_])\s(?![\s])(?=[^\W\d_](?![^\W\d_]))",
            r"\1",
            step1,
        )
        return " ".join(step2.split())

    # Step 3: Collapse runs of 4 or more consecutive space-separated single letters
    tokens = step1.split()
    out_tokens: list[str] = []
    single_letter_run: list[str] = []

    for tok in tokens:
        if len(tok) == 1 and tok.isalpha():
            single_letter_run.append(tok)
        else:
            if len(single_letter_run) >= 4:
                out_tokens.append("".join(single_letter_run))
            else:
                out_tokens.extend(single_letter_run)
            single_letter_run = []
            out_tokens.append(tok)

    if len(single_letter_run) >= 4:
        out_tokens.append("".join(single_letter_run))
    else:
        out_tokens.extend(single_letter_run)

    return " ".join(out_tokens)


def _normalize_for_detection(text: str) -> str:
    """
    Create a normalized lowercase copy of text for security scanning:
    - Strip zero-width / invisible formatting characters
    - Collapse spaced-out or punctuated letters (obfuscation defense)
    - Collapse whitespace
    """
    no_zw = "".join(ch for ch in text if ch not in ZERO_WIDTH_CHARS)
    deobfuscated = _collapse_spaced_letters(no_zw)
    return " ".join(deobfuscated.split())


def _build_compact_pattern(pattern: str) -> str:
    """
    Build a regex variant capable of matching when spaces between words were
    completely collapsed during single-space letter obfuscation.
    """
    compact = pattern.replace(r"\s+", r"[\s._\-]*").replace(r"\s*", r"[\s._\-]*")
    compact = compact.replace(r"\brole\b", "role").replace(r"\bvai\s+trò\b", "vaitrò")
    return compact


def _has_abnormal_control_chars(text: str) -> bool:
    """
    Check for invisible control characters while permitting standard whitespace
    (\\t, \\n, \\r) needed for multi-line text and code snippets.
    """
    for ch in text:
        if ch in ("\t", "\n", "\r"):
            continue
        code = ord(ch)
        if code < 32 or code == 127 or (0x80 <= code <= 0x9F):
            return True
        if unicodedata.category(ch) == "Cf":
            return True
    return False


def _is_garbage_input(stripped: str) -> bool:
    """
    Detect punctuation-only or meaningless repetitive noise while avoiding
    false positives on valid code identifiers, binary literals, or math formulas.
    """
    if not any(ch.isalnum() for ch in stripped):
        return True

    no_space = "".join(stripped.split()).lower()

    # 8 or more identical alphabetic characters in a row (e.g., "aaaaaaaaaa")
    if re.search(r"([^\W\d_])\1{7,}", no_space):
        return True

    # 10 or more identical non-space characters when no normal words exist
    words = re.findall(r"[^\W\d_]{2,}", stripped)
    if not words and re.search(r"(.)\1{9,}", no_space):
        return True

    # Entire input is just 1-2 unique characters repeated across a single token
    tokens = stripped.split()
    if len(tokens) == 1 and len(no_space) >= 8 and len(set(no_space)) <= 2:
        return True

    return False


def _matches_injection(raw_text: str) -> bool:
    """
    Evaluate text against INJECTION_PATTERNS across normalized, deobfuscated,
    and compact views.
    """
    no_zw = "".join(ch for ch in raw_text if ch not in ZERO_WIDTH_CHARS)
    plain_lower = " ".join(no_zw.lower().split())
    scan_text = _normalize_for_detection(no_zw)
    compact_text = re.sub(
        r"(?<![^\W\d_])([^\W\d_])[\s._\-/~*|\\]+(?=[^\W\d_](?![^\W\d_]))",
        r"\1",
        no_zw.lower(),
    )

    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, plain_lower, re.IGNORECASE):
            return True
        if re.search(pattern, scan_text, re.IGNORECASE):
            return True
        compact_pattern = _build_compact_pattern(pattern)
        if re.search(compact_pattern, compact_text, re.IGNORECASE):
            return True

    return False


def _has_affirmative_forbidden_homework(text: str) -> bool:
    """
    Return True if text matches FORBIDDEN_HOMEWORK_PATTERNS without an immediate
    negation prefix (such as 'đừng ', 'không cần ', 'instead of ').
    """
    for pattern in FORBIDDEN_HOMEWORK_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            prefix = text[max(0, match.start() - 35) : match.start()]
            if not _NEGATED_HOMEWORK_PREFIX_RE.search(prefix):
                return True
    return False


def validate_and_clean(
    text: str,
    max_length: int | None = None,
) -> GuardrailResult:
    """
    Comprehensive 4-layer security guardrail pipeline.
    Returns a GuardrailResult with:
      - allowed: whether the query is safe to pass to Member 1 / AI Engine
      - cleaned_text: normalized query (strictly "" when rejected)
      - reason: human-readable explanation
      - category: violation category for automated testing
    """
    # Layer A1: Type check & empty/whitespace-only check
    if not isinstance(text, str):
        return GuardrailResult(
            allowed=False,
            cleaned_text="",
            reason="Input cannot be empty or non-string.",
            category="empty_input",
        )

    stripped = text.strip()
    if not stripped:
        return GuardrailResult(
            allowed=False,
            cleaned_text="",
            reason="Input cannot be empty.",
            category="empty_input",
        )

    # Layer A2: Maximum length check
    limit = _get_max_input_length(max_length)
    if len(text) > limit:
        return GuardrailResult(
            allowed=False,
            cleaned_text="",
            reason=f"Input exceeds maximum allowed length of {limit} characters.",
            category="excessive_length",
        )

    # Layer A3: Invisible/zero-width characters or abnormal control characters
    has_zero_width = any(ch in ZERO_WIDTH_CHARS for ch in text)
    if has_zero_width or _has_abnormal_control_chars(text):
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
    if _is_garbage_input(stripped):
        return GuardrailResult(
            allowed=False,
            cleaned_text="",
            reason="Input contains invalid repetitive noise or lacks meaningful text.",
            category="garbage_input",
        )

    # Layer B: Prompt Injection & Obfuscation detection
    if _matches_injection(stripped):
        return GuardrailResult(
            allowed=False,
            cleaned_text="",
            reason="Potential prompt injection detected.",
            category="prompt_injection",
        )

    # Layer C: Academic Policy Enforcement
    plain_norm = " ".join(stripped.lower().split())
    scan_text = _normalize_for_detection(stripped)

    # Priority 1: Always block requests demanding direct/raw answers without explanation
    for pattern in DIRECT_ANSWER_PATTERNS:
        if re.search(pattern, plain_norm, re.IGNORECASE) or re.search(
            pattern, scan_text, re.IGNORECASE
        ):
            return GuardrailResult(
                allowed=False,
                cleaned_text="",
                reason=(
                    "Request violates system boundaries "
                    "(e.g., asking to do homework or only providing raw answers)."
                ),
                category="homework_policy_violation",
            )

    # Priority 2 & 3: Evaluate learning intent vs affirmative homework-solving demands.
    # Presence of a learning keyword ("hint", "giải thích") does NOT excuse an explicit,
    # non-negated demand to solve the entire homework or write full code for the user.
    has_learning_intent = any(
        re.search(pat, plain_norm, re.IGNORECASE) for pat in LEARNING_INTENT_PATTERNS
    )

    if _has_affirmative_forbidden_homework(plain_norm) or (
        not has_learning_intent and _has_affirmative_forbidden_homework(scan_text)
    ):
        return GuardrailResult(
            allowed=False,
            cleaned_text="",
            reason=(
                "Request violates system boundaries " "(e.g., asking to do homework)."
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
