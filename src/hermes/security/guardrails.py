"""
Security Guardrails module for H.E.R.M.E.S (Member 4 - AI & System Security).

Provides multi-layer input validation, prompt injection defense,
Non-goals R1 homework policy enforcement, secret/credential redaction,
and deterministic input sanitization before routing to LLM engines.
"""

from __future__ import annotations

import base64
import codecs
from dataclasses import dataclass
import os
import re
import unicodedata
import urllib.parse

DEFAULT_MAX_INPUT_LENGTH = 1000
REDACTED_SECRET_PLACEHOLDER = "[REDACTED_SECRET]"

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

# Intent-grouped Prompt Injection patterns (VN & EN, lowercase).
# Avoids blocking standalone educational keywords like "system prompt là gì?",
# "jailbreak trong AI nghĩa là gì?", or "bạn là ai?".
INJECTION_PATTERNS = [
    # 1. Instruction override / disregard
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
    (
        r"ghi\s+đè\s+"
        r"(?:chính\s+sách|system\s*prompt|quy\s+tắc|bảo\s+mật|hướng\s+dẫn|chỉ\s+dẫn)"
    ),
    (
        r"override\s+(?:all\s+|your\s+|the\s+)?"
        r"(?:system|security|safety|previous|existing)\s+"
        r"(?:policy|policies|prompt|rules|instructions|constraints)"
    ),
    # 2. Role spoofing & mode switching
    (
        r"(?:enable|activate|enter|switch\s+to|turn\s+on)\s+"
        r"(?:developer|admin|debug|unrestricted|jailbreak|dan)\s*"
        r"(?:mode|prompt|instructions|override)?"
    ),
    (
        r"(?:bật|kích\s+hoạt|vào|chuyển\s+sang)\s+chế\s+độ\s+"
        r"(?:nhà\s+phát\s+triển|phát\s+triển|quản\s+trị|debug"
        r"|không\s+giới\s+hạn|jailbreak|vượt\s+rào)"
    ),
    r"you\s+are\s+now\s+(?:a|an|in\s+developer|unrestricted|free\s+from|dan\b)",
    (
        r"act\s+as\s+(?:an?\s+)?"
        r"(?:unrestricted|unfiltered|jailbroken|developer|system|admin|root|dan\b)"
    ),
    r"bạn\s+bây\s+giờ\s+là\s+(?:một\s+|ai\s+|trợ\s+lý\s+|hệ\s+thống\s+|dan\b|admin\b)",
    r"từ\s+giờ\s+bạn\s+là\s+(?:một\s+|ai\s+|trợ\s+lý\s+|hệ\s+thống\s+|dan\b|admin\b)",
    (
        r"hãy\s+đóng\s+vai\s+(?:một\s+)?"
        r"(?:ai\s+không\s+bị\s+giới\s+hạn|hệ\s+thống\s+quản\s+trị"
        r"|developer|admin|root|dan\b)"
    ),
    r"(?:\brole\b|\bvai\s+trò\b)\s*[:=]\s*(?:system|developer|admin|root|superuser)",
    r"\[\s*(?:system|developer|admin|root|override|inst)\s*\]",
    r"<\s*\|?\s*(?:system|developer|admin|root|im_start)\s*\|?\s*>",
    r"(?:###|---)\s*(?:system|developer|admin|override|new\s+instructions)\b",
    # 3. Policy bypass & jailbreak commands
    (
        r"(?:jailbreak|vượt\s+rào)\s+"
        r"(?:hệ\s+thống|ai|model|mô\s+hình|bộ\s+lọc|guardrail|chính\s+sách|ngay|now)"
    ),
    (r"(?:hãy|please|try\s+to|help\s+me)\s+" r"(?:jailbreak|vượt\s+rào|bypass)"),
    (
        r"bypass\s+(?:the\s+|all\s+|your\s+)?"
        r"(?:filter|filters|guardrail|guardrails|security|restriction"
        r"|restrictions|policy|policies|rule|rules|lọc|bảo\s+mật)"
    ),
    (
        r"(?:vô\s+hiệu\s+hóa|tắt|bỏ)\s+"
        r"(?:bộ\s+lọc|guardrail|guardrails|bảo\s+mật|quy\s+tắc|chính\s+sách)"
    ),
    (
        r"(?:disable|turn\s+off|deactivate)\s+(?:all\s+|the\s+|your\s+)?"
        r"(?:safety|security|guardrails?|filters?|restrictions?|policies|policy)"
    ),
    # 4. System prompt & internal secret exfiltration
    (
        r"(?:reveal|show|print|output|repeat|dump|display|leak|expose|give\s+me)\s+"
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
        r"|xuất\s+ra|lặp\s+lại|đọc\s+ra)\s+(?:toàn\s+bộ\s+|nội\s+dung\s+)?"
        r"(?:system\s*prompt|chỉ\s+dẫn\s+hệ\s+thống|hướng\s+dẫn\s+hệ\s+thống"
        r"|cấu\s+hình\s+bí\s+mật|api\s*key|khóa\s+bí\s+mật)"
    ),
    (
        r"\bi(?:\s*[.\-_/~*|\\]\s*g)(?:\s*[.\-_/~*|\\]\s*n)"
        r"(?:\s*[.\-_/~*|\\]\s*o)(?:\s*[.\-_/~*|\\]\s*r)"
        r"(?:\s*[.\-_/~*|\\]\s*e)\b"
    ),
    # 5. Extended English instruction override
    (
        r"(?:ignore|disregard|override|forget)\s+"
        r"(?:all\s+|any\s+|the\s+)?"
        r"(?:instructions|prompts|rules|directions|constraints|guidelines|context)\b"
    ),
    (
        r"(?:ignore|disregard|override)\s+(?:the\s+)?"
        r"(?:above|prior|preceding|previous|earlier)\s+"
        r"(?:directions|instructions|prompts|rules|context)\b"
    ),
    r"forget\s+everything\s+above",
    (
        r"(?:do\s+not|don'?t)\s+(?:follow|obey)\s+"
        r"(?:any\s+|the\s+)?(?:earlier|previous|prior|above)?\s*"
        r"(?:rules|instructions|directions|prompts|commands)\b"
    ),
    # 6. Extended Vietnamese instruction override
    (
        r"(?:bỏ\s+qua|phớt\s+lờ|quên)\s+"
        r"(?:mọi\s+|tất\s+cả\s+|các\s+|toàn\s+bộ\s+|hết\s+)?"
        r"(?:chỉ\s+dẫn|hướng\s+dẫn|quy\s+tắc|quy\s+định|lệnh|ràng\s+buộc|"
        r"chính\s+sách|yêu\s+cầu)"
    ),
    (
        r"(?:không\s+(?:cần\s+|được\s+)?)?tuân\s+(?:theo|thủ)\s+"
        r"(?:quy\s+tắc|quy\s+định|chính\s+sách|hướng\s+dẫn|chỉ\s+dẫn)"
    ),
    (
        r"đừng\s+(?:làm\s+theo|tuân\s+theo)\s+"
        r"(?:hướng\s+dẫn|quy\s+tắc|quy\s+định|chỉ\s+dẫn|chính\s+sách)"
    ),
    (
        r"(?:vô\s+hiệu\s+hóa|vô\s+hiệu\s+hoá|tắt|bỏ|xóa\s+bỏ|gỡ\s+bỏ)\s+"
        r"(?:mọi\s+|toàn\s+bộ\s+|các\s+)?"
        r"(?:bộ\s+lọc|guardrails?|bảo\s+mật|quy\s+tắc|quy\s+định|"
        r"chính\s+sách|ràng\s+buộc|hướng\s+dẫn|chỉ\s+dẫn)"
    ),
    # 7. Role spoofing / mode switching (extended)
    (
        r"(?:developer|admin|debug|unrestricted|jailbreak|dan|dev)\s+mode\s+"
        r"(?:enabled|activated|active|on|is\s+on)"
    ),
    (
        r"(?:pretend|imagine|suppose|assume)\s+"
        r"(?:to\s+be|you\s+are|the\s+role\s+of)\s+(?:an?\s+)?"
        r"(?:admin|root|superuser|developer|unrestricted|dan|system)"
    ),
    (
        r"(?:from\s+now\s+on|henceforth)\s*,?\s*"
        r"(?:you\s+are|act\s+as|be)\b"
    ),
    (
        r"assume\s+(?:the\s+)?(?:role|identity)\s+of\s+(?:an?\s+)?"
        r"(?:admin|root|superuser|developer|system|dan)"
    ),
    r"system\s+override\s*[:\-]?\s*(?:grant|give|allow|enable|override)",
    (
        r"(?:đóng|nhập|hoá\s+thân\s+thành)\s+vai\s+(?:một\s+|như\s+)?"
        r"(?:quản\s+trị\s+viên|admin|root|superuser|developer|ai\s+không\s+bị\s+"
        r"giới\s+hạn|hệ\s+thống\s+quản\s+trị)"
    ),
    # 8. System prompt / secret exfiltration
    r"(?:your|the)\s+system\s*prompt\b",
    r"(?:your|the)\s+hidden\s+instructions\b",
    r"(?:the|your)\s+internal\s+api\s*key\b",
    r"\ball\s+environment\s+variables\b",
    r"(?:the|your)\s+original\s+developer\s+message\b",
    r"(?:your|the)\s+configuration\s+secrets?\b",
    (
        r"(?:list|show|print|dump|reveal|display|output|read\s+out)\s+"
        r"(?:me\s+)?(?:all\s+)?(?:environment\s+variables|env\s+vars)\b"
    ),
    r"prompt\s+hệ\s+thống",
    r"hướng\s+dẫn\s+nội\s+bộ",
    r"cấu\s+hình\s+bí\s+mật",
    r"khóa\s+bí\s+mật",
    r"(?:khóa|khoá)\s+api\b",
    r"biến\s+môi\s+trường",
    r"văn\s+bản\s+phía\s+trên",
    r"toàn\s+bộ\s+văn\s+bản",
    r"chỉ\s+dẫn\s+hệ\s+thống",
    # 9. Jailbreak / safety bypass (extended)
    (
        r"(?:turn\s+off|disable|remove|bypass)\s+(?:the\s+|all\s+|your\s+)?"
        r"(?:content\s+policy|safety\s+"
        r"(?:polic(?:y|ies)|guardrails?|filters?|rules?)|restrictions?)"
    ),
    (
        r"reveal\s+(?:restricted|forbidden|hidden)\s+"
        r"(?:knowledge|information|content)"
    ),
    r"without\s+(?:any\s+|all\s+)?restrictions?\b",
    (
        r"(?:jailbreak|bypass)\s+(?:the\s+|all\s+)?"
        r"(?:model|ai|filter|filters|guardrails|safety)"
    ),
    r"emergency\s+override\b",
    # 10. Delimiter / context injection
    r"<<\s*sys\s*>>",
    r"<\|?\s*(?:im_start|im_end|endoftext)\s*\|?>",
    (
        r"\b(?:begin|start|end)\s+(?:of\s+)?system\s+"
        r"(?:message|prompt|directive|context|instructions?)\b"
    ),
    r"\{\{[^}\n]{0,80}(?:system[_\s]*prompt|override|jailbreak)[^}\n]{0,80}\}\}",
    # 11. Encoding / decode instructions
    r"(?:base64|rot13|hex|url)\s*[-_]?\s*(?:decode|decoded|encoded?)\b",
    r"\bdecode\s+and\s+(?:follow|execute|obey|apply)\b",
    (
        r"(?:read|interpret)\s+(?:this\s+|the\s+following\s+)?"
        r"(?:backwards|in\s+reverse)\b"
    ),
    r"đọc\s+ngược",
    # 12. Multilingual instruction override / exfiltration
    r"忽略[^\n]{0,40}(?:指令|指示|提示|系统)",
    r"(?:無視|指示)[^\n]{0,40}(?:指示|命令|プロンプト|無視|システム)",
    r"(?:무시|지시)[^\n]{0,40}(?:지시|명령|프롬프트|무시)",
    (
        r"\bignor(?:a|e|ez|iere|i|are|emos|en|ando)\b"
        r"[^\n]{0,70}(?:instruc|anweisung|prompt|sistema|syst[eè]me)"
    ),
    r"\bигнор\w*[^\n]{0,70}(?:инструкц|промпт|систем)",
    r"инструкц\w*[^\n]{0,50}(?:покаж|открой|игнор)",
    r"เพิกเฉย[^\n]{0,70}(?:คำสั่ง|พรอมต์|ระบบ)",
    r"\babaikan\b[^\n]{0,70}(?:instruksi|prompt|sistem)",
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
    # Bare final answer / answer key requests (no explanation wording required)
    r"\bfinal\s+answer\b",
    r"\banswer\s+key\b",
    r"đáp\s+án\s+cuối\s+cùng",
    (
        r"(?:tell|give|send|provide|show|want|need)\s+(?:me\s+)?(?:the\s+)?"
        r"(?:final|exact|correct|direct)\s+(?:answer|solution)"
    ),
]

# Patterns indicating a student is asking for hints, explanations, or debugging
LEARNING_INTENT_PATTERNS = [
    r"\bgợi\s+ý\b",
    r"\bhướng\s+dẫn\s+(?:cách|phương\s+pháp|hướng|từng\s+bước|debug|kiểm\s+thử)\b",
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
    r"\bphân\s+tích\s+(?:lỗi|yêu\s+cầu|đề\s+bài)\b",
    r"\bsai\s+ở\s+đâu\b",
    r"\bsửa\s+giúp\s+(?:em|mình|tôi)\s+code\b",
    r"\bdebug\b",
    r"\bôn\s+tập\b",
    r"\bluyện\s+tập\b",
    r"\bví\s+dụ\s+code\b",
    r"\bhint\b",
    (
        r"(?<!no\s)(?<!without\s)(?<!not\s)(?<!don't\s)(?<!dont\s)"
        r"(?<!need\sto\s)\bexplain\b"
    ),
    r"(?<!no\s)(?<!without\s)(?<!without\sany\s)\bexplanation\b",
    r"\bhow\s+(?:does|do|to\s+understand|to\s+debug|to\s+test)\b",
    r"\bconcept\b",
    r"\bapproach\b",
    r"\bstep\s+by\s+step\s+guide\b",
]

# Strict forbidden patterns for complete homework/lab/exam solving (Non-goals R1).
FORBIDDEN_HOMEWORK_PATTERNS = [
    (
        r"do\s+my\s+(?:entire\s+|whole\s+|full\s+)?"
        r"(?:homework|assignment|lab|exam|test|project)"
    ),
    (
        r"write\s+(?:the\s+|my\s+)?"
        r"(?:full\s+|complete\s+|entire\s+|whole\s+|ready\s+to\s+submit\s+)?"
        r"(?:code|solution|assignment|homework)\s+for\s+me"
    ),
    (
        r"solve\s+(?:this|my)\s+(?:entire\s+|whole\s+|full\s+|complete\s+|current\s+)?"
        r"(?:assignment|homework|problem|exam|lab|test)"
        r"(?:\s+for\s+me|\s+completely|\s+from\s+scratch"
        r"|\s+and\s+give\s+me\s+the\s+answers?)?"
    ),
    (
        r"complete\s+(?:this|my)\s+(?:entire\s+|whole\s+|full\s+)?"
        r"(?:homework|assignment|lab|exam)(?:\s+for\s+me|\s+to\s+submit)?"
    ),
    (
        r"(?:làm|giải|hoàn\s+thành)\s+(?:hộ|thay|giúp|dùm|giùm)\s+"
        r"(?:cho\s+)?(?:tôi\s+|mình\s+|em\s+)?"
        r"(?:toàn\s+bộ\s+|trọn\s+vẹn\s+|hết\s+|nguyên\s+|trọn\s+bộ\s+)?"
        r"(?:bài\s+tập|đề\s+bài|bài\s+thi|bài\s+kiểm\s+tra"
        r"|bài\s+lab|đề\s+thi|assignment)"
    ),
    (
        r"(?:làm|giải)\s+(?:hộ|thay|dùm|giùm)\s+"
        r"(?:cho\s+)?(?:tôi\s+|mình\s+|em\s+)?"
        r"(?:toàn\s+bộ\s+|hết\s+)?bài\s+này"
    ),
    (
        r"(?:làm|giải|hoàn\s+thành)\s+"
        r"(?:toàn\s+bộ|trọn\s+vẹn|hết|trọn\s+bộ"
        r"|chi\s+tiết\s+từng\s+bước\s+ra\s+đáp\s+án)\s+"
        r"(?:bài\s+tập|đề\s+bài|bài\s+toán|đề\s+thi|bài\s+lab|bài\s+thi|lời\s+giải)"
        r"(?:\s+này|\s+đang\s+làm)?(?:\s+cho\s+(?:tôi|mình|em)|\s+để\s+nộp)?"
    ),
    (
        r"(?:hoàn\s+thành|viết|làm|giải)\s+(?:giúp\s+|hộ\s+|thay\s+|cho\s+)?"
        r"(?:tôi\s+|mình\s+|em\s+)?(?:toàn\s+bộ\s+|trọn\s+bộ\s+|hết\s+)?"
        r"(?:bài\s+tập|bài\s+lab|lời\s+giải|code)\s+"
        r"(?:này\s+)?để\s+(?:em\s+|mình\s+|tôi\s+)?nộp"
    ),
    (
        r"giải\s+(?:toàn\s+bộ\s+|hết\s+)?đề\s+thi\s+"
        r"(?:đang\s+làm|cuối\s+kỳ|giữa\s+kỳ|này)"
    ),
    (
        r"viết\s+(?:hộ\s+|thay\s+|giúp\s+|dùm\s+|giùm\s+)?"
        r"(?:cho\s+(?:tôi|mình|em)\s+)?"
        r"(?:toàn\s+bộ\s+|trọn\s+vẹn\s+|trọn\s+bộ\s+|hết\s+|full\s+)"
        r"(?:code|lời\s+giải|chương\s+trình)"
    ),
    (
        r"viết\s+(?:hộ\s+|thay\s+|dùm\s+|giùm\s+)"
        r"(?:toàn\s+bộ\s+|trọn\s+vẹn\s+|hết\s+|full\s+)?code\b"
    ),
    (r"viết\s+(?:toàn\s+bộ\s+|full\s+)?code\s+" r"(?:hộ|thay|dùm|giùm)\b"),
    (r"\bcode\s+(?:hộ|thay|dùm|giùm)\s+(?:tôi|mình|em|bài)\b"),
]

# Extended homework-intent patterns (semantic action + graded work object).
# Applied only when the message has no explicit learning/hint intent, so that
# legitimate tutoring requests such as "đang làm bài tập, xin gợi ý" stay safe.
EXTENDED_HOMEWORK_PATTERNS = [
    # English: action verb + graded work object (word order independent)
    (
        r"\bwrite\s+(?:the\s+|my\s+|a\s+)?"
        r"(?:complete\s+|full\s+|entire\s+|whole\s+)?"
        r"(?:code|program|solution|report|essay)\b[^.\n]{0,40}"
        r"\b(?:assignment|homework|lab|project|exam|test)\b"
    ),
    r"\bwrite\s+(?:my|the)\s+(?:project\s+)?report\s+for\s+me\b",
    (
        r"\bsolve\s+(?:my|this|the|our)\b[^.\n]{0,40}"
        r"\b(?:homework|assignment|lab|exam|test|problem|questions?)\b"
    ),
    (
        r"\bcomplete\s+(?:this|my|the)\b[^.\n]{0,40}"
        r"\b(?:homework|assignment|lab|exam|test|project)\b"
    ),
    (
        r"\bdo\s+(?:my|this|the)\b[^.\n]{0,30}"
        r"\b(?:homework|assignment|lab|exam|test|project|questions?)\b"
    ),
    # Vietnamese: action verb + graded work object (word order independent)
    (
        r"\b(?:giải|làm|hoàn\s+thành|viết|thực\s+hiện)\b[^.\n]{0,40}?"
        r"\b(?:bài\s+tập|bài\s+lab|bài\s+thi|bài\s+kiểm\s+tra|"
        r"đề\s+thi|đề\s+bài)\b"
    ),
    (
        r"\bviết\s+(?:mã\s+)?"
        r"(?:code|chương\s+trình|lời\s+giải|bài\s+giải)\b"
        r"[^.\n]{0,30}?\b(?:hoàn\s+chỉnh|đầy\s+đủ|full|toàn\s+bộ)\b"
    ),
]

# Layer D Privacy & Secret Protection
_SECRET_CONVERSATIONAL_STOPWORDS = {
    "là",
    "gì",
    "như",
    "thế",
    "nào",
    "sao",
    "ở",
    "đâu",
    "khi",
    "trong",
    "và",
    "hoặc",
    "bằng",
    "của",
    "cho",
    "what",
    "how",
    "why",
    "where",
    "when",
    "in",
    "and",
    "or",
    "with",
    "for",
    "to",
    "the",
    "a",
    "an",
}

_PRIVATE_KEY_BLOCK_RE = re.compile(
    r"-----BEGIN\s+(?:RSA\s+|EC\s+|OPENSSH\s+|DSA\s+|PGP\s+)?PRIVATE\s+KEY-----"
    r"[\s\S]*?"
    r"-----END\s+(?:RSA\s+|EC\s+|OPENSSH\s+|DSA\s+|PGP\s+)?PRIVATE\s+KEY-----",
    re.IGNORECASE,
)
_PRIVATE_KEY_HEADER_RE = re.compile(
    r"-----BEGIN\s+(?:RSA\s+|EC\s+|OPENSSH\s+|DSA\s+|PGP\s+)?PRIVATE\s+KEY-----"
    r"[^\n\r]*",
    re.IGNORECASE,
)
_URL_CREDENTIAL_RE = re.compile(
    r"\b([a-zA-Z][a-zA-Z0-9+.\-]*://[^/\s:@]+:)([^@\s/]+)(@[^\s/]+)"
)
_BEARER_TOKEN_RE = re.compile(
    r"(\b(?:Authorization\s*:\s*)?Bearer\s+)" r"([A-Za-z0-9\-._~+/]{8,}=*)",
    re.IGNORECASE,
)
_JWT_TOKEN_RE = re.compile(
    r"\beyJ[A-Za-z0-9_\-]{6,}\.eyJ[A-Za-z0-9_\-]{6,}\.[A-Za-z0-9_\-]{6,}\b"
)
_KNOWN_TOKEN_PREFIX_RE = re.compile(
    r"\b(?:"
    r"AIza[0-9A-Za-z_\-]{12,}"
    r"|sk-(?:proj-|live-|test-)?[A-Za-z0-9_\-]{12,}"
    r"|gh[pousr]_[A-Za-z0-9_]{12,}"
    r"|github_pat_[A-Za-z0-9_]{12,}"
    r"|xox[baprs]-[A-Za-z0-9\-]{10,}"
    r"|AKIA[0-9A-Z]{16}"
    r")\b"
)
_KEY_VALUE_SECRET_RE = re.compile(
    r"((?:\bmật\s*khẩu\b|\bmat\s*khau\b|\bpassword\b|\bpasswd\b|\bpwd\b"
    r"|\bmã\s*pin\b|\bapi[_\-\s]*key\b|\baccess[_\-\s]*token\b"
    r"|\brefresh[_\-\s]*token\b|\bauth[_\-\s]*token\b"
    r"|\bclient[_\-\s]*secret\b|\bsecret[_\-\s]*key\b|\bprivate[_\-\s]*key\b"
    r"|\bsecret\b|\btoken\b)"
    r"(?:\s+(?:của\s+)?(?:tôi|mình|em|user|admin|moodle|db|database|hệ\s+thống))?"
    r"\s*(?:[:=]|\blà\b|\bis\b)\s*)"
    r"(['\"]?[^\s,;'\"]+['\"]?)",
    re.IGNORECASE,
)

_NEGATED_HOMEWORK_PREFIX_RE = re.compile(
    r"(?:không\s+(?:cần|yêu\s+cầu|muốn|nhờ|đòi|bắt|phải)\s+"
    r"|đừng\s+|chứ\s+đừng\s+|thay\s+vì\s+"
    r"|not\s+(?:asking(?:\s+you)?\s+to\s+|to\s+)?"
    r"|don'?t\s+|do\s+not\s+|instead\s+of\s+)\s*$"
)

_PUNCT_SEPARATED_LETTERS_RE = re.compile(
    r"(?<![^\W\d_])[^\W\d_](?:[\s]*[.\-_/~*|\\]+[\s]*[^\W\d_]){2,}(?![^\W\d_])",
    re.UNICODE,
)


def _build_compact_pattern(pattern: str) -> str:
    """
    Build a regex variant capable of matching when spaces between words were
    completely collapsed during single-space letter obfuscation.
    """
    compact = pattern.replace(r"\s+", r"[\s._\-]*").replace(r"\s*", r"[\s._\-]*")
    compact = compact.replace(r"\brole\b", "role").replace(r"\bvai\s+trò\b", "vaitrò")
    return compact


def _strip_diacritics(text: str) -> str:
    """
    Remove Vietnamese/Latin diacritics and combining marks while keeping the
    base letters. Used for detection only so accented attacks cannot bypass
    keyword matching when combining marks are injected.
    """
    normalized = text.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", normalized)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _fold_pattern(pattern: str) -> str:
    """Create a diacritic-insensitive counterpart of a regex pattern."""
    return _strip_diacritics(pattern)


_LEET_TRANSLATION = str.maketrans("431057", "aeiost")

_HOMOGLYPH_TRANSLATION = str.maketrans(
    {
        "а": "a", "е": "e", "і": "i", "о": "o", "с": "c", "р": "p",
        "х": "x", "у": "y", "ѕ": "s", "ј": "j", "ԁ": "d", "ӏ": "l",
        "А": "a", "Е": "e", "І": "i", "О": "o", "С": "c", "Р": "p",
        "Х": "x", "У": "y", "Ѕ": "s", "Ј": "j", "Ԁ": "d", "Ӏ": "l",
        "α": "a", "ε": "e", "ι": "i", "ο": "o", "ρ": "p", "χ": "x",
        "υ": "y", "Α": "a", "Ε": "e", "Ι": "i", "Ο": "o", "Ρ": "p",
        "Χ": "x", "Υ": "y",
    }
)


def _leet_normalize(text: str) -> str:
    """Undo common leetspeak substitutions (4->a, 3->e, 1->i, 0->o, 5->s, 7->t)."""
    return text.translate(_LEET_TRANSLATION)


def _homoglyph_normalize(text: str) -> str:
    """Map common Cyrillic/Greek homoglyphs back to their Latin lookalikes."""
    return text.translate(_HOMOGLYPH_TRANSLATION)


def _decode_payloads(text: str) -> list[str]:
    """
    Attempt bounded decoding of ROT13/Base64/hex/URL-encoded payloads. Any
    decoded result is treated as another text variant to scan, so encoded
    injection cannot hide from the regex layer.
    """
    decoded: list[str] = []
    lower = text.lower()

    if "rot13" in lower:
        payload = text.split(":", 1)[1] if ":" in text else text
        try:
            decoded.append(codecs.decode(payload, "rot13"))
        except (ValueError, UnicodeError):
            pass
        try:
            decoded.append(codecs.decode(text, "rot13"))
        except (ValueError, UnicodeError):
            pass

    if "base64" in lower:
        for match in re.finditer(r"[A-Za-z0-9+/]{8,}={0,2}", text):
            blob = match.group(0)
            try:
                raw = base64.b64decode(
                    blob + "=" * (-len(blob) % 4), validate=False
                )
                candidate = raw.decode("utf-8", errors="ignore")
            except (ValueError, UnicodeError):
                continue
            if candidate.strip():
                decoded.append(candidate)

    if "hex" in lower:
        for match in re.finditer(r"(?:[0-9a-fA-F]{2}\s*){6,}", text):
            try:
                decoded.append(
                    bytes.fromhex(match.group(0).replace(" ", "")).decode(
                        "utf-8", errors="ignore"
                    )
                )
            except (ValueError, UnicodeError):
                continue

    if re.search(r"%[0-9a-fA-F]{2}", text):
        try:
            decoded.append(urllib.parse.unquote(text))
        except (ValueError, UnicodeError):
            pass

    return decoded


def _build_detection_variants(text: str) -> list[str]:
    """
    Build every relevant normalized view of an input for security scanning:
    original case-folded text, spaced-letter collapse, compact letters,
    diacritic-free, leetspeak, homoglyph, slash-separated, decoded, and
    reversed forms. Scanning all views closes common obfuscation bypasses.
    """
    compat = unicodedata.normalize("NFKC", text)
    no_zw = "".join(ch for ch in compat if ch not in ZERO_WIDTH_CHARS)
    base = " ".join(no_zw.lower().split())

    variants: set[str] = {base}
    scan = _collapse_spaced_letters(base)
    variants.add(scan)
    variants.add(_COMPACT_SINGLE_LETTERS_RE.sub(r"\1", base))

    for seed in tuple(variants):
        variants.add(_strip_diacritics(seed))

    if re.search(r"[013457]", base):
        leet = _leet_normalize(base)
        variants.add(leet)
        variants.add(_strip_diacritics(leet))

    if re.search(r"[^\x00-\x7f]", base):
        homoglyph = _homoglyph_normalize(base)
        variants.add(homoglyph)
        variants.add(_strip_diacritics(homoglyph))

    if re.search(r"[\\/|]", base):
        slashed = re.sub(r"[\\/|]+", " ", base)
        variants.add(slashed)
        variants.add(_strip_diacritics(slashed))

    for payload in _decode_payloads(text):
        payload_base = " ".join(
            "".join(
                ch for ch in unicodedata.normalize("NFKC", payload)
                if ch not in ZERO_WIDTH_CHARS
            ).lower().split()
        )
        if not payload_base:
            continue
        variants.add(payload_base)
        variants.add(_strip_diacritics(payload_base))
        variants.add(_collapse_spaced_letters(payload_base))
        variants.add(_strip_diacritics(_collapse_spaced_letters(payload_base)))

    if re.search(r"(?:backwards|reverse|ngược|đảo\s+ngược)", base):
        reversed_full = base[::-1]
        variants.add(reversed_full)
        variants.add(_strip_diacritics(reversed_full))

    return [variant for variant in variants if variant]


# Pre-compiled combined regexes (operating on lowercased text for <1.2 ms speed)
_COMBINED_STD_INJECTION_RE = re.compile(
    "|".join(f"(?:{p})" for p in INJECTION_PATTERNS)
)
_COMBINED_DEACC_INJECTION_RE = re.compile(
    "|".join(f"(?:{_fold_pattern(p)})" for p in INJECTION_PATTERNS)
)
_COMBINED_COMPACT_INJECTION_RE = re.compile(
    "|".join(f"(?:{_build_compact_pattern(p)})" for p in INJECTION_PATTERNS)
)
_COMBINED_DEACC_COMPACT_INJECTION_RE = re.compile(
    "|".join(
        f"(?:{_build_compact_pattern(_fold_pattern(p))})"
        for p in INJECTION_PATTERNS
    )
)
_COMBINED_DIRECT_ANSWER_RE = re.compile(
    "|".join(f"(?:{p})" for p in DIRECT_ANSWER_PATTERNS)
)
_COMBINED_DEACC_DIRECT_ANSWER_RE = re.compile(
    "|".join(f"(?:{_fold_pattern(p)})" for p in DIRECT_ANSWER_PATTERNS)
)
_COMBINED_LEARNING_INTENT_RE = re.compile(
    "|".join(f"(?:{p})" for p in LEARNING_INTENT_PATTERNS)
)
_COMBINED_FORBIDDEN_HOMEWORK_RE = re.compile(
    "|".join(f"(?:{p})" for p in FORBIDDEN_HOMEWORK_PATTERNS)
)
_COMBINED_DEACC_FORBIDDEN_HOMEWORK_RE = re.compile(
    "|".join(f"(?:{_fold_pattern(p)})" for p in FORBIDDEN_HOMEWORK_PATTERNS)
)
_COMBINED_EXTENDED_HOMEWORK_RE = re.compile(
    "|".join(f"(?:{p})" for p in EXTENDED_HOMEWORK_PATTERNS)
)
_COMBINED_DEACC_EXTENDED_HOMEWORK_RE = re.compile(
    "|".join(f"(?:{_fold_pattern(p)})" for p in EXTENDED_HOMEWORK_PATTERNS)
)
_NEGATED_HOMEWORK_PREFIX_DEACC_RE = re.compile(_fold_pattern(
    _NEGATED_HOMEWORK_PREFIX_RE.pattern
))
_MULTI_SPACE_LETTERS_RE = re.compile(r"[^\W\d_]\s{2,}[^\W\d_]")
_SINGLE_SPACE_BETWEEN_LETTERS_RE = re.compile(
    r"(?<![^\W\d_])([^\W\d_])\s(?![\s])(?=[^\W\d_](?![^\W\d_]))"
)
_COMPACT_SINGLE_LETTERS_RE = re.compile(
    r"(?<![^\W\d_])([^\W\d_])[\s._\-/~*|\\]+(?=[^\W\d_](?![^\W\d_]))"
)
_REPEATED_ALPHA_RE = re.compile(r"([^\W\d_])\1{7,}")
_REPEATED_ANY_RE = re.compile(r"(.)\1{9,}")
_TWO_PLUS_ALPHA_WORDS_RE = re.compile(r"[^\W\d_]{2,}")

_CREDENTIAL_LABEL_WORDS = {
    "password",
    "passwd",
    "pwd",
    "pass",
    "mật",
    "khẩu",
    "mat",
    "khau",
    "mã",
    "pin",
    "api",
    "key",
    "apikey",
    "api_key",
    "access",
    "refresh",
    "auth",
    "client",
    "private",
    "secret",
    "token",
    "bearer",
    "authorization",
    "của",
    "tôi",
    "mình",
    "em",
    "là",
    "is",
    "my",
}


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

    def _strip_punct_separators(match: re.Match[str]) -> str:
        return "".join(ch for ch in match.group(0) if ch.isalnum())

    step1 = _PUNCT_SEPARATED_LETTERS_RE.sub(_strip_punct_separators, lowered)

    if _MULTI_SPACE_LETTERS_RE.search(step1):
        step2 = _SINGLE_SPACE_BETWEEN_LETTERS_RE.sub(r"\1", step1)
        return " ".join(step2.split())

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
    - Apply NFKC compatibility normalization for detection only
    - Strip zero-width / invisible formatting characters
    - Collapse spaced-out or punctuated letters (obfuscation defense)
    - Collapse whitespace
    """
    compat = unicodedata.normalize("NFKC", text)
    no_zw = "".join(ch for ch in compat if ch not in ZERO_WIDTH_CHARS)
    deobfuscated = _collapse_spaced_letters(no_zw)
    return " ".join(deobfuscated.split())


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

    if _REPEATED_ALPHA_RE.search(no_space):
        return True

    words = _TWO_PLUS_ALPHA_WORDS_RE.findall(stripped)
    if not words and _REPEATED_ANY_RE.search(no_space):
        return True

    tokens = stripped.split()
    if len(tokens) == 1 and len(no_space) >= 8 and len(set(no_space)) <= 2:
        return True

    return False


def _matches_injection(
    plain_lower: str,
    scan_text: str,
    compact_text: str,
) -> bool:
    """
    Evaluate lowercased text views against combined injection regexes.
    Retained for backwards compatibility with callers/tests.
    """
    if _COMBINED_STD_INJECTION_RE.search(plain_lower):
        return True
    if _COMBINED_DEACC_INJECTION_RE.search(plain_lower):
        return True
    if scan_text != plain_lower and _COMBINED_STD_INJECTION_RE.search(scan_text):
        return True
    if compact_text != plain_lower and _COMBINED_COMPACT_INJECTION_RE.search(
        compact_text
    ):
        return True
    return False


def _detect_injection(variants: list[str]) -> bool:
    """Scan every normalized variant for prompt injection / obfuscation."""
    for variant in variants:
        if _COMBINED_STD_INJECTION_RE.search(variant):
            return True
        if _COMBINED_DEACC_INJECTION_RE.search(variant):
            return True
        compact = _COMPACT_SINGLE_LETTERS_RE.sub(r"\1", variant)
        if compact != variant:
            if _COMBINED_COMPACT_INJECTION_RE.search(compact):
                return True
            if _COMBINED_DEACC_COMPACT_INJECTION_RE.search(compact):
                return True
    return False


def _detect_direct_answer(variants: list[str]) -> bool:
    """Scan every normalized variant for bare-answer/exam-cheating requests."""
    return any(
        _COMBINED_DIRECT_ANSWER_RE.search(variant)
        or _COMBINED_DEACC_DIRECT_ANSWER_RE.search(variant)
        for variant in variants
    )


def _has_affirmative_forbidden_homework(
    text: str,
    combined_re: re.Pattern[str] = _COMBINED_FORBIDDEN_HOMEWORK_RE,
    negation_re: re.Pattern[str] = _NEGATED_HOMEWORK_PREFIX_RE,
) -> bool:
    """
    Return True if text matches FORBIDDEN_HOMEWORK_PATTERNS without an immediate
    negation prefix (such as 'đừng ', 'không cần ', 'instead of ').
    """
    for match in combined_re.finditer(text):
        prefix = text[max(0, match.start() - 35) : match.start()]
        if not negation_re.search(prefix):
            return True
    return False


def _detect_homework(variants: list[str], has_learning_intent: bool) -> bool:
    """Scan every normalized variant for full-homework-solving requests."""
    for variant in variants:
        if _has_affirmative_forbidden_homework(variant):
            return True
        if not has_learning_intent:
            if _has_affirmative_forbidden_homework(
                variant,
                _COMBINED_DEACC_FORBIDDEN_HOMEWORK_RE,
                _NEGATED_HOMEWORK_PREFIX_DEACC_RE,
            ):
                return True
            if _has_affirmative_forbidden_homework(
                variant,
                _COMBINED_EXTENDED_HOMEWORK_RE,
                _NEGATED_HOMEWORK_PREFIX_RE,
            ):
                return True
            if _has_affirmative_forbidden_homework(
                variant,
                _COMBINED_DEACC_EXTENDED_HOMEWORK_RE,
                _NEGATED_HOMEWORK_PREFIX_DEACC_RE,
            ):
                return True
    return False


def redact_sensitive_info(text: str) -> str:
    """
    Redact recognized secrets (passwords, API keys, access/refresh/Bearer tokens,
    JWTs, private keys, and URL credentials) with [REDACTED_SECRET].
    Does not redact normal prose that merely discusses 'password' or 'token'.
    """
    redacted = _PRIVATE_KEY_BLOCK_RE.sub(REDACTED_SECRET_PLACEHOLDER, text)
    redacted = _PRIVATE_KEY_HEADER_RE.sub(REDACTED_SECRET_PLACEHOLDER, redacted)
    redacted = _URL_CREDENTIAL_RE.sub(
        rf"\1{REDACTED_SECRET_PLACEHOLDER}\3",
        redacted,
    )
    redacted = _JWT_TOKEN_RE.sub(REDACTED_SECRET_PLACEHOLDER, redacted)
    redacted = _BEARER_TOKEN_RE.sub(
        rf"\1{REDACTED_SECRET_PLACEHOLDER}",
        redacted,
    )
    redacted = _KNOWN_TOKEN_PREFIX_RE.sub(REDACTED_SECRET_PLACEHOLDER, redacted)

    def _replace_kv_secret(match: re.Match[str]) -> str:
        prefix = match.group(1)
        raw_val = match.group(2)
        stripped_val = raw_val.strip("'\"")
        if (
            not stripped_val
            or len(stripped_val) < 3
            or stripped_val.lower() in _SECRET_CONVERSATIONAL_STOPWORDS
            or stripped_val == REDACTED_SECRET_PLACEHOLDER
        ):
            return match.group(0)
        return f"{prefix}{REDACTED_SECRET_PLACEHOLDER}"

    redacted = _KEY_VALUE_SECRET_RE.sub(_replace_kv_secret, redacted)
    return redacted


def _has_meaningful_query_after_redaction(redacted_text: str) -> bool:
    """
    Verify that after redacting secrets, the remaining text still contains a
    meaningful question or statement rather than only secret placeholders/labels.
    """
    without_placeholders = redacted_text.replace(REDACTED_SECRET_PLACEHOLDER, " ")
    without_urls = re.sub(
        r"\b[a-zA-Z][a-zA-Z0-9+.\-]*://[^\s]+",
        " ",
        without_placeholders,
    )
    word_tokens = [
        tok.lower()
        for tok in re.findall(r"[^\W\d_]+", without_urls)
        if tok.lower() not in _CREDENTIAL_LABEL_WORDS
    ]
    return len(word_tokens) >= 2


def validate_and_clean(
    text: str,
    max_length: int | None = None,
) -> GuardrailResult:
    """
    Comprehensive 4-layer security guardrail pipeline.
    Returns a GuardrailResult with:
      - allowed: whether the query is safe to pass to Member 1 / AI Engine
      - cleaned_text: normalized & secret-redacted query (strictly "" when rejected)
      - reason: human-readable explanation (never echoes raw secrets)
      - category: violation category for automated testing
    """
    # Layer A1: Type check & empty/whitespace-only check (before any Regex)
    if not isinstance(text, str):
        return GuardrailResult(
            allowed=False,
            cleaned_text="",
            reason="Input cannot be empty or non-string.",
            category="empty_input",
        )

    # Layer A2: Maximum length check BEFORE stripping/Regex to prevent ReDoS
    limit = _get_max_input_length(max_length)
    if len(text) > limit:
        return GuardrailResult(
            allowed=False,
            cleaned_text="",
            reason=f"Input exceeds maximum allowed length of {limit} characters.",
            category="excessive_length",
        )

    stripped = text.strip()
    if not stripped:
        return GuardrailResult(
            allowed=False,
            cleaned_text="",
            reason="Input cannot be empty.",
            category="empty_input",
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

    # Compute normalized detection views once (includes deobfuscation variants)
    compat_lower = unicodedata.normalize("NFKC", stripped).lower()
    plain_lower = " ".join(compat_lower.split())
    variants = _build_detection_variants(stripped)

    # Layer B: Prompt Injection & Obfuscation detection
    if _detect_injection(variants):
        return GuardrailResult(
            allowed=False,
            cleaned_text="",
            reason="Potential prompt injection detected.",
            category="prompt_injection",
        )

    # Layer C: Academic Policy Enforcement (Non-goals R1)
    if _detect_direct_answer(variants):
        return GuardrailResult(
            allowed=False,
            cleaned_text="",
            reason=(
                "Request violates system boundaries "
                "(e.g., asking to do homework or only providing raw answers)."
            ),
            category="homework_policy_violation",
        )

    has_learning_intent = bool(_COMBINED_LEARNING_INTENT_RE.search(plain_lower))

    if _detect_homework(variants, has_learning_intent):
        return GuardrailResult(
            allowed=False,
            cleaned_text="",
            reason=(
                "Request violates system boundaries " "(e.g., asking to do homework)."
            ),
            category="homework_policy_violation",
        )

    # Layer D: Secret Redaction & Safe Content Normalization
    redacted_raw = redact_sensitive_info(stripped)
    cleaned_normalized = " ".join(redacted_raw.split())

    if REDACTED_SECRET_PLACEHOLDER in cleaned_normalized:
        if not _has_meaningful_query_after_redaction(cleaned_normalized):
            return GuardrailResult(
                allowed=False,
                cleaned_text="",
                reason=(
                    "Input contains only sensitive credentials without a valid query."
                ),
                category="secret_only_input",
            )

    return GuardrailResult(
        allowed=True,
        cleaned_text=cleaned_normalized,
        reason="Input is safe.",
        category="safe",
    )


def _collapse_spaced_letters_fast(lowered: str) -> str:
    """Fast helper for collapsing spaced/punctuated letters on lowercased text."""
    if _PUNCT_SEPARATED_LETTERS_RE.search(lowered):
        lowered = _PUNCT_SEPARATED_LETTERS_RE.sub(
            lambda m: "".join(ch for ch in m.group(0) if ch.isalnum()),
            lowered,
        )

    tokens = lowered.split()
    if sum(1 for t in tokens if len(t) == 1 and t.isalpha()) < 4:
        return " ".join(tokens)

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


def sanitize_input(text: str) -> tuple[bool, str]:
    """
    Fast (< 2 ms) public guardrail entrypoint adhering to strict output contract:
      - Valid query (with or without redacted secrets): (True, clean_query)
      - Any rejected input (wrong type, empty, >1000 chars, injection,
        homework violation, secret-only, or secret + attack): (False, "")
    """
    result = validate_and_clean(text)
    if result.allowed:
        return True, result.cleaned_text
    return False, ""
