"""
Security Guardrails module for H.E.R.M.E.S (Member 4 - AI & System Security).

Provides multi-layer input validation, prompt injection defense,
Non-goals R1 homework policy enforcement, secret/credential redaction,
and deterministic input sanitization before routing to LLM engines.
"""

from __future__ import annotations

import base64
import codecs
from dataclasses import asdict, dataclass
import json
import os
import re
import socket
import threading
import time
from types import SimpleNamespace
from typing import Any, Iterator
import unicodedata
import urllib.error
import urllib.parse

DEFAULT_MAX_INPUT_LENGTH = 1000
REDACTED_SECRET_PLACEHOLDER = "[REDACTED_SECRET]"

# Scan-set flags: which regex family must run on a normalized text unit.
_STD = 1
_DEACC = 2
_COMPACT = 4
_DEACC_COMPACT = 8

# Gate bitmask: which detection layers are worth running for this input.
_MASK_INJECTION = 1
_MASK_POLICY = 2
_MASK_FULL = _MASK_INJECTION | _MASK_POLICY

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
        r"disregard\s+(?:all\s+|any\s+|the\s+)?(?:your\s+)?"
        r"(?:(?:previous|prior|above|earlier|system)\s+)?"
        r"(?:instructions|prompts|commands|rules|directions|constraints)"
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
        r"(?:reveal|show|print|output|dump|leak|expose|display)\s+"
        r"(?:me\s+)?(?:your\s+|the\s+)?"
        r"(?:api\s*key|configuration|config|credentials|secrets?)\b"
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
        r"(?:ignore|disregard|override)\s+(?:the\s+)?"
        r"(?:safety|content|security)\s+(?:policy|policies|rules)\b"
    ),
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
    (
        r"(?:cho\s+phép|mở\s+khóa|bỏ\s+giới\s+hạn)\s+"
        r"(?:nội\s+dung(?:\s+bị\s+cấm)?|đầu\s+ra|ngôn\s+từ)"
    ),
    (r"không\s+giới\s+hạn\s+" r"(?:nội\s+dung|đầu\s+ra|ngôn\s+từ)"),
    # 7. Role spoofing / mode switching (extended)
    (
        r"(?:developer|admin|debug|unrestricted|jailbreak|dan|dev)\s+mode\s+"
        r"(?:enabled|activated|active|is\s+on)"
    ),
    (
        r"(?:pretend|imagine|suppose|assume)\s+"
        r"(?:to\s+be|you\s+are|the\s+role\s+of)\s+(?:an?\s+)?"
        r"(?:admin|root|superuser|developer|unrestricted|dan|system)"
    ),
    (r"(?:from\s+now\s+on|henceforth)\s*,?\s*" r"(?:you\s+are|act\s+as|be)\b"),
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
    r"تجاهل[^\n]{0,70}(?:التعليمات|التوجيهات|النظام|الموجه|البرومبت)",
    r"(?:अनदेखा|उपेक्षा)[^\n]{0,70}(?:निर्देश|प्रॉम्प्ट|सिस्टम)",
    r"\b(?:yoksay|görmezden\s+gel)\b[^\n]{0,70}(?:talimat|istem|sistem|komut)",
    r"\bzignoruj\b[^\n]{0,70}(?:instrukcj|prompt|system)",
]

# Patterns for demanding raw/direct answers without explanation (Always blocked)
DIRECT_ANSWER_PATTERNS = [
    (
        r"chỉ\s+(?:cần\s+)?(?:trả\s+lời\s+|cho\s+|đưa\s+|xin\s+|lấy\s+|nói\s+|đọc\s+|báo\s+)*"
        r"(?:mình\s+|tôi\s+|em\s+)?đáp\s+án(?:.*?)"
        r"(?:không\s+(?:cần\s+)?(?:phải\s+)?|đừng\s+|khỏi\s+|miễn\s+)giải\s+thích"
    ),
    (
        r"(?:đưa|cho|trả|xin|lấy|nói|đọc|báo)\s+(?:mình\s+|tôi\s+|em\s+)?đáp\s+án\s*"
        r"(?:cuối\s+cùng|luôn|trực\s+tiếp|ngay|thôi)\s*"
        r"(?:,\s*|\s+|-\s*)"
        r"(?:không\s+(?:cần\s+)?(?:phải\s+)?|đừng\s+|khỏi\s+|miễn\s+)giải\s+thích"
    ),
    (
        r"(?:không\s+(?:cần\s+)?(?:phải\s+)?|đừng\s+|khỏi\s+|miễn\s+)giải\s+thích"
        r"(?:.*?)(?:chỉ\s+(?:cần\s+)?|đưa\s+|cho\s+|xin\s+|lấy\s+|nói\s+|đọc\s+|báo\s+)đáp\s+án"
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
    r"\bwhat\s+is\s+(?:the\s+)?final\s+answer\b",
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
    r"\blàm\s+sao\s+để\s+(?:làm|giải|hoàn\s+thành)\b",
    r"\bhướng\s+dẫn\s+(?:tôi|mình|em)\s+(?:làm|cách|từng\s+bước)\b",
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
        r"write\s+(?:the\s+|my\s+|a\s+|an\s+)?"
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
    (
        r"\b(?:cho|xin|đưa|lấy|trả)\s+(?:tôi|mình|em)?\s*"
        r"đáp\s+án\s+(?:đề\s+thi|bài\s+thi|bài\s+kiểm\s+tra)"
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
    r"((?:(?<![A-Za-z0-9])"
    r"(?:mật\s*khẩu|mat\s*khau|password|passwd|pwd"
    r"|mã\s*pin|pin|api[_\-\s]*key|access[_\-\s]*token"
    r"|refresh[_\-\s]*token|auth[_\-\s]*token"
    r"|client[_\-\s]*secret|secret[_\-\s]*key|private[_\-\s]*key"
    r"|secret|token)\b)"
    r"(?:\s+(?:của\s+)?(?:tôi|mình|em|user|admin|moodle|db|database|hệ\s+thống))?"
    r"\s*(?:[:=]|\blà\b|\bis\b)\s*)"
    r"(['\"]?[^\s,;'\"]+['\"]?)",
    re.IGNORECASE,
)

# Layer D PII detection (email, Vietnamese phone, payment card, CCCD, address).
_PII_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_PII_PHONE_RE = re.compile(r"\b(?:\+84|0)(?:3|5|7|8|9)\d{8}\b")
_PII_CREDIT_CARD_RE = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")
_PII_CCCD_RE = re.compile(r"\b\d{12}\b")
_PII_ADDRESS_RE = re.compile(
    r"\b\d{1,5}\s+[^\n,;]{3,60}?,\s*"
    r"(?:Quận|Huyện|Phường|Xã|Thị\s+trấn|Thành\s+phố|Tỉnh)\b[^\n,;]{0,40}",
    re.IGNORECASE,
)
_PII_PATTERNS = (
    _PII_EMAIL_RE,
    _PII_PHONE_RE,
    _PII_CREDIT_CARD_RE,
    _PII_CCCD_RE,
    _PII_ADDRESS_RE,
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


# Pre-built lowercase Vietnamese folding table (67 characters). This matches
# ``_strip_diacritics`` exactly for Vietnamese while avoiding a full NFD pass
# on every request; characters outside the table fall back to NFD.
_VI_FOLD_SRC = (
    "àáảãạăằắẳẵặâầấẩẫậ"
    "èéẻẽẹêềếểễệ"
    "ìíỉĩị"
    "òóỏõọôồốổỗộơờớởỡợ"
    "ùúủũụưừứửữự"
    "ỳýỷỹỵ"
    "đ"
)
_VI_FOLD_DST = "a" * 17 + "e" * 11 + "i" * 5 + "o" * 17 + "u" * 11 + "y" * 5 + "d"

if len(_VI_FOLD_SRC) != 67 or len(_VI_FOLD_DST) != 67:  # pragma: no cover
    raise AssertionError("Vietnamese folding table must contain exactly 67 entries.")

_FOLD_TABLE = str.maketrans(_VI_FOLD_SRC, _VI_FOLD_DST)


def _fold_text(text: str) -> str:
    """
    Fast diacritic-insensitive folding equivalent to ``_strip_diacritics``.

    ASCII input is returned unchanged. Vietnamese precomposed characters use a
    pre-built translation table, and any remaining non-ASCII characters fall
    back to NFD decomposition so accents outside Vietnamese (``über``) behave
    exactly like the legacy implementation.
    """
    if text.isascii():
        return text
    folded = text.translate(_FOLD_TABLE).replace("Đ", "D")
    if folded.isascii():
        return folded
    decomposed = unicodedata.normalize("NFD", folded)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


_LEET_TRANSLATION = str.maketrans("431057", "aeiost")

_HOMOGLYPH_TRANSLATION = str.maketrans(
    {
        "а": "a",
        "е": "e",
        "і": "i",
        "о": "o",
        "с": "c",
        "р": "p",
        "х": "x",
        "у": "y",
        "ѕ": "s",
        "ј": "j",
        "ԁ": "d",
        "ӏ": "l",
        "А": "a",
        "Е": "e",
        "І": "i",
        "О": "o",
        "С": "c",
        "Р": "p",
        "Х": "x",
        "У": "y",
        "Ѕ": "s",
        "Ј": "j",
        "Ԁ": "d",
        "Ӏ": "l",
        "α": "a",
        "ε": "e",
        "ι": "i",
        "ο": "o",
        "ρ": "p",
        "χ": "x",
        "υ": "y",
        "Α": "a",
        "Ε": "e",
        "Ι": "i",
        "Ο": "o",
        "Ρ": "p",
        "Χ": "x",
        "Υ": "y",
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
                raw = base64.b64decode(blob + "=" * (-len(blob) % 4), validate=False)
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

    leet: str | None = None
    if re.search(r"[013457]", base):
        leet = _leet_normalize(base)
        variants.add(leet)
        variants.add(_strip_diacritics(leet))

    homoglyph: str | None = None
    if re.search(r"[^\x00-\x7f]", base):
        homoglyph = _homoglyph_normalize(base)
        variants.add(homoglyph)
        variants.add(_strip_diacritics(homoglyph))

    if leet is not None and homoglyph is not None:
        for combined in (
            _leet_normalize(homoglyph),
            _homoglyph_normalize(leet),
        ):
            variants.add(combined)
            variants.add(_strip_diacritics(combined))

    if re.search(r"[\\/|]", base):
        slashed = re.sub(r"[\\/|]+", " ", base)
        variants.add(slashed)
        variants.add(_strip_diacritics(slashed))

    for payload in _decode_payloads(text):
        payload_base = " ".join(
            "".join(
                ch
                for ch in unicodedata.normalize("NFKC", payload)
                if ch not in ZERO_WIDTH_CHARS
            )
            .lower()
            .split()
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
        f"(?:{_build_compact_pattern(_fold_pattern(p))})" for p in INJECTION_PATTERNS
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
_NEGATED_HOMEWORK_PREFIX_DEACC_RE = re.compile(
    _fold_pattern(_NEGATED_HOMEWORK_PREFIX_RE.pattern)
)
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
_ASCII_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_LEET_SIGNAL_RE = re.compile(r"[013457]")
_NON_LATIN_SCRIPT_RE = re.compile(
    r"[\u0370-\u052F\u0590-\u06FF\u0900-\u097F\u0E00-\u0E7F"
    r"\u1100-\u11FF\u3040-\u30FF\u3130-\u318F\u3400-\u4DBF"
    r"\u4E00-\u9FFF\uAC00-\uD7AF\uF900-\uFAFF]"
)
_ENCODING_MARKER_RE = re.compile(r"(?:base64|rot13|hex|%[0-9a-fA-F]{2})")
_REVERSE_MARKER_RE = re.compile(r"(?:backwards|reverse|ngược|đảo\s+ngược)")
_PUNCT_LETTER_PAIR_RE = re.compile(r"[^\W\d_][._\-/~*|\\][^\W\d_]")
_SPACED_PUNCT_SEPARATOR_RE = re.compile(r"[^\W\d_]\s+[._\-/~*|\\]\s+[^\W\d_]")


try:  # Python exposes the regex parser under a private but stable name.
    from re import _constants as _re_constants
    from re import _parser as _re_parser

    _REGEX_PARSER_AVAILABLE = True
except ImportError:  # pragma: no cover - fallback for exotic interpreters.
    _re_constants = None  # type: ignore[assignment]
    _re_parser = None  # type: ignore[assignment]
    _REGEX_PARSER_AVAILABLE = False


def _is_signal_gated_pattern(pattern: str) -> bool:
    """
    Return True for patterns whose only trigger is an obfuscation signal.

    The spaced-letter injection pattern has no mandatory literal run of its
    own; it can only match when letters are separated by punctuation. The gate
    therefore stays conservative: these inputs are always forced onto the slow
    path by ``_has_obfuscation_signal`` instead of being skipped.
    """
    return "[.\\-_/~*|\\\\]" in pattern


def _literal_anchor_tokens(run: str) -> list[str]:
    """Split a mandatory literal run into usable anchor tokens."""
    tokens: list[str] = []
    for token in re.findall(r"[^\W_]+", run):
        if token.isascii() and token.isalnum() and len(token) >= 3:
            tokens.append(token)
        elif not token.isascii() and len(token) >= 2:
            tokens.append(token)
    return tokens


def _anchor_score(anchors: set[str]) -> tuple[int, float, int]:
    """Rank an anchor set by how selective and compact it is."""
    return (
        min(len(anchor) for anchor in anchors),
        sum(len(anchor) for anchor in anchors) / len(anchors),
        -len(anchors),
    )


def _is_whitespace_ops(nodes: object) -> bool:
    """Return True when every op in ``nodes`` only consumes whitespace."""
    if not _REGEX_PARSER_AVAILABLE:  # pragma: no cover
        return False
    for op, av in nodes:  # type: ignore[union-attr]
        if op is _re_constants.CATEGORY:
            if av is not _re_constants.CATEGORY_SPACE:
                return False
            continue
        if op is _re_constants.LITERAL:
            if not chr(av).isspace():
                return False
            continue
        if op is _re_constants.IN:
            for inner_op, inner_av in av:
                if inner_op is _re_constants.NEGATE:
                    return False
                if inner_op is _re_constants.CATEGORY:
                    if inner_av is not _re_constants.CATEGORY_SPACE:
                        return False
                elif inner_op is _re_constants.LITERAL:
                    if not chr(inner_av).isspace():
                        return False
                else:
                    return False
            continue
        return False
    return True


def _phrase_anchors(
    phrase: list[tuple[str, bool]],
) -> set[str]:
    """
    Expand a token phrase into concrete anchor strings.

    ``phrase`` entries are ``(token, space_required_before)``. Required spaces
    always become one space (normalized text collapses whitespace); optional
    spaces produce both a spaced and a concatenated anchor.
    """
    if not phrase:
        return set()
    tokens = [token for token, _ in phrase]
    separators = [required for _, required in phrase[1:]]
    optional_positions = [i for i, required in enumerate(separators) if not required]
    if len(optional_positions) > 4:  # pragma: no cover - defensive cap.
        return {token for token, _ in phrase if len(token) >= 3}

    results: set[str] = set()
    for mask in range(1 << len(optional_positions)):
        pieces = [tokens[0]]
        optional_bit = 0
        for index, required in enumerate(separators, start=1):
            if required:
                pieces.append(" ")
            else:
                if mask & (1 << optional_bit):
                    pieces.append(" ")
                optional_bit += 1
            pieces.append(tokens[index])
        results.add("".join(pieces))
    return results


def _analyze_anchor_node(node: object) -> set[str] | None:
    """
    Derive a hitting set of literals/phrases from a parsed regex node.

    The returned set has the invariant: every string matched by ``node``
    contains at least one member of the set. ``None`` means no such guarantee
    exists (for example, a branch made only of character classes).
    """
    if not _REGEX_PARSER_AVAILABLE:  # pragma: no cover
        return None

    best: set[str] | None = None
    current: list[str] = []
    phrase: list[tuple[str, bool]] = []
    pending_space: bool | None = None

    def consider(candidate: set[str] | None) -> None:
        nonlocal best
        if candidate and (
            best is None or _anchor_score(candidate) > _anchor_score(best)
        ):
            best = candidate

    def append_run(run: str) -> None:
        nonlocal pending_space
        if not run:
            return
        if re.fullmatch(r"[^\W_]+", run):
            token = run
            required = pending_space if phrase else False
            phrase.append((token, bool(required)))
            pending_space = None
            return
        if re.fullmatch(r"[^\W_\s]+(?:\s+[^\W_]+)*", run):
            for index, token in enumerate(re.findall(r"[^\W_]+", run)):
                if index == 0:
                    required = bool(pending_space) if phrase else False
                else:
                    required = True
                phrase.append((token, required))
            pending_space = None
            return
        flush_phrase()
        tokens = _literal_anchor_tokens(run)
        if tokens:
            consider({max(tokens, key=lambda token: (len(token), token))})

    def flush_current() -> None:
        nonlocal current
        if current:
            run = "".join(current)
            current = []
            append_run(run)

    def flush_phrase() -> None:
        nonlocal phrase, pending_space
        flush_current()
        if phrase:
            if len(phrase) == 1:
                token = phrase[0][0]
                too_short = len(token) < 3 if token.isascii() else len(token) < 2
                anchors = set() if too_short else {token}
            else:
                anchors = _phrase_anchors(phrase)
            if anchors:
                consider(anchors)
        phrase = []
        pending_space = None

    for op, av in node:  # type: ignore[union-attr]
        if op is _re_constants.LITERAL:
            current.append(chr(av))
            continue
        if op is _re_constants.AT:
            flush_phrase()
            continue
        if op is _re_constants.SUBPATTERN:
            flush_phrase()
            consider(_analyze_anchor_node(av[3]))
            continue
        if op is _re_constants.BRANCH:
            flush_phrase()
            parts: list[set[str]] = []
            for alternative in av[1]:
                candidate = _analyze_anchor_node(alternative)
                if candidate is None:
                    break
                parts.append(candidate)
            else:
                merged: set[str] = set()
                for part in parts:
                    merged |= part
                consider(merged)
            continue
        if op in (_re_constants.MAX_REPEAT, _re_constants.MIN_REPEAT):
            minimum = av[0]
            if _is_whitespace_ops(av[2]):
                flush_current()
                required = minimum >= 1
                if pending_space is None:
                    pending_space = required
                else:
                    pending_space = pending_space or required
                continue
            flush_phrase()
            candidate = _analyze_anchor_node(av[2])
            if minimum >= 1:
                consider(candidate)
            continue
        if op is _re_constants.IN and _is_whitespace_ops([(op, av)]):
            flush_current()
            if pending_space is None:
                pending_space = True
            else:
                pending_space = True
            continue
        flush_phrase()
    flush_phrase()
    return best


def _derive_family_anchors(
    patterns: list[str],
) -> tuple[set[str], bool]:
    """
    Derive gate anchors for a pattern family.

    Returns ``(anchors, always_slow)``. ``always_slow`` is set only when a
    pattern cannot produce a safe anchor and is not covered by an obfuscation
    signal; in that case the family must run on every input (fail-closed).
    """
    anchors: set[str] = set()
    always_slow = False
    for pattern in patterns:
        folded = _fold_pattern(pattern)
        candidate: set[str] | None = None
        if _REGEX_PARSER_AVAILABLE:
            try:
                candidate = _analyze_anchor_node(_re_parser.parse(folded, 0))
            except (re.error, ValueError):  # pragma: no cover - defensive.
                candidate = None
        if candidate is None:
            if not _is_signal_gated_pattern(pattern):
                always_slow = True
        else:
            anchors |= candidate
    return anchors, always_slow


_INJECTION_ANCHORS, _INJECTION_ALWAYS_SLOW = _derive_family_anchors(INJECTION_PATTERNS)
_POLICY_ANCHORS, _POLICY_ALWAYS_SLOW = _derive_family_anchors(
    list(DIRECT_ANSWER_PATTERNS)
    + list(FORBIDDEN_HOMEWORK_PATTERNS)
    + list(EXTENDED_HOMEWORK_PATTERNS)
)


def _anchor_hit(anchors: set[str], folded: str) -> bool:
    """
    Return True if any derived anchor occurs in ``folded``.

    Plain substring checks are measurably faster than a large compiled
    alternation for this workload (tens of microseconds per 1000 characters).
    """
    return any(anchor in folded for anchor in anchors)


def _has_obfuscation_signal(base: str) -> bool:
    """
    Return True when cheap signals indicate a variant-based attack.

    Any hit forces the full detection path, so the gate can never skip a
    family that might match only after a lossy transformation. The expensive
    spaced-letter regexes only run when the text actually contains at least two
    isolated single-letter tokens.
    """
    if sum(1 for token in base.split() if len(token) == 1 and token.isalpha()) >= 2:
        if _COMPACT_SINGLE_LETTERS_RE.search(
            base
        ) or _PUNCT_SEPARATED_LETTERS_RE.search(base):
            return True
    if _PUNCT_LETTER_PAIR_RE.search(base) or _SPACED_PUNCT_SEPARATOR_RE.search(base):
        return True
    if (
        _LEET_SIGNAL_RE.search(base)
        or _ENCODING_MARKER_RE.search(base)
        or _REVERSE_MARKER_RE.search(base)
        or _NON_LATIN_SCRIPT_RE.search(base)
    ):
        return True
    return False


def _gate_mask(base: str, folded: str) -> int:
    """
    Choose which detection layers must run for ``base``/``folded``.

    The gate never decides that an input is safe; it only selects a scan path.
    A missing anchor family is always forced through the full path.
    """
    mask = 0
    if _INJECTION_ALWAYS_SLOW or _anchor_hit(_INJECTION_ANCHORS, folded):
        mask |= _MASK_INJECTION
    if _POLICY_ALWAYS_SLOW or _anchor_hit(_POLICY_ANCHORS, folded):
        mask |= _MASK_POLICY
    return mask


def _build_scan_units(
    text: str,
    use_fast_fold: bool = True,
    include_compact: bool = True,
) -> dict[str, int]:
    """
    Build the deduplicated ``(text, scan flags)`` view of an input.

    This reproduces exactly the string set produced by
    ``_build_detection_variants`` but stores one entry per unique string and
    records which regex families were already requested for it.

    ``include_compact`` may be disabled when the injection layer will not run:
    the compact/compact-folded flags are only consumed by the injection scanner,
    while the compacted base string itself is already present as a ``_STD`` unit
    for the policy scanner. This avoids redundant work without changing any
    decision.
    """
    fold = _fold_text if use_fast_fold else _strip_diacritics

    compat = unicodedata.normalize("NFKC", text)
    no_zw = "".join(ch for ch in compat if ch not in ZERO_WIDTH_CHARS)
    base = " ".join(no_zw.lower().split())

    texts: set[str] = {base}
    texts.add(_collapse_spaced_letters(base))
    texts.add(_COMPACT_SINGLE_LETTERS_RE.sub(r"\1", base))

    for seed in tuple(texts):
        texts.add(fold(seed))

    leet: str | None = None
    if re.search(r"[013457]", base):
        leet = _leet_normalize(base)
        texts.add(leet)
        texts.add(fold(leet))

    homoglyph: str | None = None
    if re.search(r"[^\x00-\x7f]", base):
        homoglyph = _homoglyph_normalize(base)
        texts.add(homoglyph)
        texts.add(fold(homoglyph))

    if leet is not None and homoglyph is not None:
        for combined in (
            _leet_normalize(homoglyph),
            _homoglyph_normalize(leet),
        ):
            texts.add(combined)
            texts.add(fold(combined))

    if re.search(r"[\\/|]", base):
        slashed = re.sub(r"[\\/|]+", " ", base)
        texts.add(slashed)
        texts.add(fold(slashed))

    for payload in _decode_payloads(text):
        payload_base = " ".join(
            "".join(
                ch
                for ch in unicodedata.normalize("NFKC", payload)
                if ch not in ZERO_WIDTH_CHARS
            )
            .lower()
            .split()
        )
        if not payload_base:
            continue
        collapsed = _collapse_spaced_letters(payload_base)
        texts.add(payload_base)
        texts.add(fold(payload_base))
        texts.add(collapsed)
        texts.add(fold(collapsed))

    if _REVERSE_MARKER_RE.search(base):
        reversed_full = base[::-1]
        texts.add(reversed_full)
        texts.add(fold(reversed_full))

    units: dict[str, int] = {}
    for unit in texts:
        if not unit:
            continue
        units[unit] = units.get(unit, 0) | _STD
        folded = fold(unit)
        if folded:
            units[folded] = units.get(folded, 0) | _DEACC
        if not include_compact:
            continue
        compact = _COMPACT_SINGLE_LETTERS_RE.sub(r"\1", unit)
        if compact != unit:
            units[compact] = units.get(compact, 0) | _COMPACT
            folded_compact = fold(compact)
            if folded_compact:
                units[folded_compact] = units.get(folded_compact, 0) | _DEACC_COMPACT
    return units


def _detect_injection_units(units: dict[str, int]) -> bool:
    """Scan deduplicated units for prompt injection with early exit."""
    for unit, flags in units.items():
        if flags & _STD and _COMBINED_STD_INJECTION_RE.search(unit):
            return True
        if flags & _DEACC and _COMBINED_DEACC_INJECTION_RE.search(unit):
            return True
        if flags & _COMPACT and _COMBINED_COMPACT_INJECTION_RE.search(unit):
            return True
        if flags & _DEACC_COMPACT and _COMBINED_DEACC_COMPACT_INJECTION_RE.search(unit):
            return True
    return False


def _detect_direct_answer_units(units: dict[str, int]) -> bool:
    """Scan deduplicated units for bare-answer requests (STD/DEACC only)."""
    for unit, flags in units.items():
        if flags & _STD and _COMBINED_DIRECT_ANSWER_RE.search(unit):
            return True
        if flags & _DEACC and _COMBINED_DEACC_DIRECT_ANSWER_RE.search(unit):
            return True
    return False


def _detect_homework_units(units: dict[str, int], has_learning_intent: bool) -> bool:
    """Scan deduplicated units for full-homework requests (STD/DEACC only)."""
    for unit, flags in units.items():
        if flags & _STD and _has_affirmative_forbidden_homework(unit):
            return True
        if has_learning_intent:
            continue
        if flags & _DEACC and _has_affirmative_forbidden_homework(
            unit,
            _COMBINED_DEACC_FORBIDDEN_HOMEWORK_RE,
            _NEGATED_HOMEWORK_PREFIX_DEACC_RE,
        ):
            return True
        if flags & _STD and _has_affirmative_forbidden_homework(
            unit,
            _COMBINED_EXTENDED_HOMEWORK_RE,
            _NEGATED_HOMEWORK_PREFIX_RE,
        ):
            return True
        if flags & _DEACC and _has_affirmative_forbidden_homework(
            unit,
            _COMBINED_DEACC_EXTENDED_HOMEWORK_RE,
            _NEGATED_HOMEWORK_PREFIX_DEACC_RE,
        ):
            return True
    return False


_SECRET_MARKERS = (
    # Private keys, bearer tokens and JWTs.
    "-----begin",
    "eyj",
    "bearer",
    # Known token prefixes (character classes expanded to concrete letters).
    "aiza",
    "sk-",
    "ghp_",
    "gho_",
    "ghu_",
    "ghs_",
    "ghr_",
    "github_pat_",
    "xox",
    "akia",
    # Key/value labels, including unaccented Vietnamese variants.
    "password",
    "passwd",
    "pwd",
    "mật",
    "mat",
    "pin",
    "api",
    "access",
    "refresh",
    "auth",
    "client",
    "private",
    "secret",
    "token",
)


def _needs_redaction(text: str) -> bool:
    """
    Cheap prefilter proving that no secret regex can match ``text``.

    Markers are derived from the redaction patterns themselves. URL credentials
    additionally require both ``://`` and ``@`` to be present. PII patterns are
    evaluated directly because they have no cheap single-token marker.
    """
    lowered = text.lower()
    if any(marker in lowered for marker in _SECRET_MARKERS):
        return True
    if "://" in lowered and "@" in lowered:
        return True
    return any(pattern.search(text) for pattern in _PII_PATTERNS)


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


def _env_flag(name: str, default: bool = True) -> bool:
    """Read a boolean environment flag, accepting common false spellings."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off", "disabled"}


def _optimized_enabled() -> bool:
    """Whether the low-latency pipeline is active (rollback: set flag to 0)."""
    return _env_flag("HERMES_GUARDRAIL_OPTIMIZED", True)


def _option_enabled(name: str) -> bool:
    """Return a per-optimization flag; it only applies when optimized mode is on."""
    return _optimized_enabled() and _env_flag(name, True)


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


def _has_hidden_or_control_chars_fast(text: str) -> bool:
    """
    Single-pass equivalent of the zero-width + control-character check.

    ASCII input cannot contain zero-width characters or ``Cf`` codepoints, so a
    compiled control regex is sufficient. Non-ASCII input memoizes
    ``unicodedata.category`` per character within the call, keeping the legacy
    semantics for NBSP, surrogates and private-use characters.
    """
    if text.isascii():
        return _ASCII_CONTROL_RE.search(text) is not None

    categories: dict[str, str] = {}
    for ch in text:
        if ch in ZERO_WIDTH_CHARS:
            return True
        if ch in ("\t", "\n", "\r"):
            continue
        code = ord(ch)
        if code < 32 or code == 127 or (0x80 <= code <= 0x9F):
            return True
        category = categories.get(ch)
        if category is None:
            category = unicodedata.category(ch)
            categories[ch] = category
        if category == "Cf":
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

    if _TWO_PLUS_ALPHA_WORDS_RE.search(stripped) is None and _REPEATED_ANY_RE.search(
        no_space
    ):
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
        normalized_val = stripped_val.lower().strip("?!.,;:")
        if (
            not stripped_val
            or len(stripped_val) < 3
            or normalized_val in _SECRET_CONVERSATIONAL_STOPWORDS
            or stripped_val == REDACTED_SECRET_PLACEHOLDER
        ):
            return match.group(0)
        return f"{prefix}{REDACTED_SECRET_PLACEHOLDER}"

    redacted = _KEY_VALUE_SECRET_RE.sub(_replace_kv_secret, redacted)
    for pii_pattern in _PII_PATTERNS:
        redacted = pii_pattern.sub(REDACTED_SECRET_PLACEHOLDER, redacted)
    return redacted


def _has_meaningful_query_after_redaction(redacted_text: str) -> bool:
    """
    Verify that after redacting secrets, the remaining text still contains a
    meaningful question or statement rather than only secret placeholders/labels.
    """
    without_urls = re.sub(
        r"\b[a-zA-Z][a-zA-Z0-9+.\-]*://[^\s]+",
        " ",
        redacted_text,
    )
    without_placeholders = without_urls.replace(REDACTED_SECRET_PLACEHOLDER, " ")
    word_tokens = [
        tok.lower()
        for tok in re.findall(r"[^\W\d_]+", without_placeholders)
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

    optimized = _optimized_enabled()
    use_micro = optimized and _option_enabled("HERMES_GUARDRAIL_MICRO")
    use_scan_set = optimized and _option_enabled("HERMES_GUARDRAIL_SCAN_SET")
    use_gate = optimized and _option_enabled("HERMES_GUARDRAIL_GATE")
    use_redact_prefilter = optimized and _option_enabled(
        "HERMES_GUARDRAIL_REDACT_PREFILTER"
    )

    # Layer A3: Invisible/zero-width characters or abnormal control characters
    if use_micro:
        has_hidden_chars = _has_hidden_or_control_chars_fast(text)
    else:
        has_hidden_chars = any(ch in ZERO_WIDTH_CHARS for ch in text) or (
            _has_abnormal_control_chars(text)
        )
    if has_hidden_chars:
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

    compat_lower = unicodedata.normalize("NFKC", stripped).lower()
    plain_lower = " ".join(compat_lower.split())

    mask = _MASK_FULL
    folded = ""
    if optimized:
        folded = _fold_text(plain_lower)
        if _has_obfuscation_signal(plain_lower):
            mask = _MASK_FULL
        elif use_gate:
            mask = _gate_mask(plain_lower, folded)

    units: dict[str, int] | None = None
    if optimized and use_scan_set and mask:
        units = _build_scan_units(
            stripped,
            use_fast_fold=use_micro,
            include_compact=bool(mask & _MASK_INJECTION),
        )

    variants: list[str] | None = None
    if (not optimized or not use_scan_set) and (not optimized or mask):
        variants = _build_detection_variants(stripped)

    # Layer B: Prompt Injection & Obfuscation detection
    injection_hit = False
    if mask & _MASK_INJECTION:
        if units is not None:
            injection_hit = _detect_injection_units(units)
        else:
            injection_hit = _detect_injection(variants or [])
    if injection_hit:
        return GuardrailResult(
            allowed=False,
            cleaned_text="",
            reason="Potential prompt injection detected.",
            category="prompt_injection",
        )

    # Layer C: Academic Policy Enforcement (Non-goals R1)
    direct_answer_hit = False
    if mask & _MASK_POLICY:
        if units is not None:
            direct_answer_hit = _detect_direct_answer_units(units)
        else:
            direct_answer_hit = _detect_direct_answer(variants or [])
    if direct_answer_hit:
        return GuardrailResult(
            allowed=False,
            cleaned_text="",
            reason=(
                "Request violates system boundaries "
                "(e.g., asking to do homework or only providing raw answers)."
            ),
            category="homework_policy_violation",
        )

    homework_hit = False
    if mask & _MASK_POLICY:
        has_learning_intent = bool(_COMBINED_LEARNING_INTENT_RE.search(plain_lower))
        if units is not None:
            homework_hit = _detect_homework_units(units, has_learning_intent)
        else:
            homework_hit = _detect_homework(variants or [], has_learning_intent)
    if homework_hit:
        return GuardrailResult(
            allowed=False,
            cleaned_text="",
            reason=(
                "Request violates system boundaries " "(e.g., asking to do homework)."
            ),
            category="homework_policy_violation",
        )

    # Layer D: Secret Redaction & Safe Content Normalization
    if use_redact_prefilter and not _needs_redaction(stripped):
        redacted_raw = stripped
    else:
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


# ==============================================================================
# SAFE AI GATEWAY & FAIL-CLOSED MOCK FALLBACK (ADDITIVE EXTENSION)
# ==============================================================================

SAFE_FALLBACK_TEXT = (
    "[MOCK][SAFE_FALLBACK] Hệ thống tạm thời không kết nối được dịch vụ AI. "
    "Vui lòng thử lại sau. Câu trả lời này không phải nội dung từ Gemini."
)
SAFE_BLOCKED_TEXT = "[BLOCKED] Yêu cầu không hợp lệ hoặc vi phạm chính sách an toàn."
FALLBACK_MODEL_NAME = "mock-safe-fallback-v1"
MAX_AI_OUTPUT_LENGTH = 65_536
MAX_ERROR_REASON_LENGTH = 200

_ERROR_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"AIza[0-9A-Za-z_\-]{12,}"), "[REDACTED_API_KEY]"),
    (
        re.compile(
            r"(?i)\b(api[_-]?key|key|token|secret|password|access_token|sig)"
            r"=([^&\s'\"<>]+)"
        ),
        r"\1=[REDACTED]",
    ),
    (
        re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/]+=*"),
        "Bearer [REDACTED_TOKEN]",
    ),
    (re.compile(r"\bsk-[A-Za-z0-9\-_]{12,}\b"), "[REDACTED_SECRET_KEY]"),
)


class EmptyAIResponseError(ValueError):
    """Raised internally when the AI provider returns an empty response."""


@dataclass(frozen=True)
class SafeAIResult:
    """Immutable, fail-closed result returned by the safe AI gateway."""

    text: str
    allowed: bool
    is_mock: bool
    degraded: bool
    mode: str
    model: str
    error_category: str = ""
    reason: str = ""

    @property
    def ok(self) -> bool:
        """True only when generation succeeded without degradation."""
        return self.allowed and not self.degraded

    def to_dict(self) -> dict[str, Any]:
        """Serialize the result for the orchestrator or CLI."""
        return asdict(self)


class MockClient:
    """
    Deterministic offline fallback client.

    This client never performs network I/O, never reads environment secrets,
    and never echoes the user prompt back to the caller.
    """

    def __init__(self, model: str = FALLBACK_MODEL_NAME) -> None:
        self.model = model or FALLBACK_MODEL_NAME

    def generate(
        self,
        prompt: str = "",
        system_instruction: str | None = None,
    ) -> SimpleNamespace:
        """Return a fixed safe fallback response without using ``prompt``."""
        _ = (prompt, system_instruction)
        return SimpleNamespace(
            text=SAFE_FALLBACK_TEXT,
            mode="mock",
            model=self.model,
            is_mock=True,
        )


def _iter_exception_chain(
    exc: BaseException | None,
) -> Iterator[BaseException]:
    """Traverse ``__cause__``/``__context__`` so wrapped causes are inspected."""
    seen: set[int] = set()
    current = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        next_exc = current.__cause__ or current.__context__
        if next_exc is None:
            for attr in ("original_error", "inner_exception", "error"):
                candidate = getattr(current, attr, None)
                if isinstance(candidate, BaseException):
                    next_exc = candidate
                    break
        current = next_exc


def classify_ai_error(exc: BaseException) -> str:
    """
    Classify direct or wrapped AI exceptions into stable error categories.

    ``HermesAIClient`` wraps network/HTTP/SDK failures in ``AIClientError``, so
    the classification inspects the full causal chain as well as the message.
    """
    chain = list(_iter_exception_chain(exc))
    combined_msg = " | ".join(str(item).lower() for item in chain if str(item))

    for item in chain:
        cls_name = type(item).__name__
        module_name = type(item).__module__.lower()

        if isinstance(item, EmptyAIResponseError) or cls_name in (
            "EmptyAIResponseError",
            "EmptyResponseError",
        ):
            return "empty_response"

        if cls_name == "AIConfigError":
            return "config_error"

        if isinstance(item, ImportError):
            return "dependency_error"

        status_code = getattr(item, "code", None)
        if status_code is None:
            status_code = getattr(item, "status_code", None)

        if isinstance(item, urllib.error.HTTPError) or isinstance(status_code, int):
            if status_code in (401, 403):
                return "auth_error"
            if status_code == 429:
                return "rate_limited"
            if isinstance(status_code, int) and 500 <= status_code <= 599:
                return "server_error"
            if isinstance(status_code, int) and 400 <= status_code <= 499:
                return "invalid_response"

        if isinstance(item, (TimeoutError, socket.timeout)):
            return "timeout"

        if isinstance(item, urllib.error.URLError):
            reason_obj = getattr(item, "reason", None)
            if isinstance(reason_obj, (TimeoutError, socket.timeout)):
                return "timeout"
            item_msg = str(item).lower()
            if "timed out" in item_msg or "timeout" in item_msg:
                return "timeout"
            return "network_error"

        if isinstance(item, (socket.gaierror, ConnectionError, OSError)):
            item_msg = str(item).lower()
            if "timed out" in item_msg or "timeout" in item_msg:
                return "timeout"
            return "network_error"

        if isinstance(item, json.JSONDecodeError):
            return "invalid_response"

        if isinstance(item, ValueError):
            return "invalid_response"

        if "genai" in module_name or "google" in module_name:
            return "sdk_error"

    if any(
        kw in combined_msg
        for kw in (
            "empty response",
            "empty_response",
            "returned an empty",
            "output empty",
            "empty text candidate",
        )
    ):
        return "empty_response"

    if any(
        kw in combined_msg
        for kw in (
            "aiconfigerror",
            "missing api key",
            "api key is required",
            "invalid mode",
            "not configured",
            "gemini_api_key",
            "placeholder",
        )
    ):
        return "config_error"

    if any(
        kw in combined_msg
        for kw in (
            "no module named",
            "importerror",
            "cannot import",
            "dependency",
        )
    ):
        return "dependency_error"

    if any(kw in combined_msg for kw in ("timed out", "timeout", "deadline exceeded")):
        return "timeout"

    if any(
        kw in combined_msg
        for kw in (
            "http 401",
            "http 403",
            "status 401",
            "status 403",
            "unauthorized",
            "forbidden",
            "invalid api key",
            "permission denied",
        )
    ):
        return "auth_error"

    if any(
        kw in combined_msg
        for kw in (
            "http 429",
            "status 429",
            "rate limit",
            "rate_limit",
            "quota",
            "too many requests",
            "resource_exhausted",
            "resource exhausted",
        )
    ):
        return "rate_limited"

    if any(
        kw in combined_msg
        for kw in (
            "http 500",
            "http 502",
            "http 503",
            "http 504",
            "server error",
            "internal server error",
            "bad gateway",
            "service unavailable",
        )
    ):
        return "server_error"

    if any(
        kw in combined_msg
        for kw in (
            "jsondecodeerror",
            "invalid json",
            "malformed json",
            "expecting value",
            "invalid_response",
            "invalid response",
            "decode",
        )
    ):
        return "invalid_response"

    if any(
        kw in combined_msg
        for kw in (
            "urlerror",
            "gaierror",
            "name or service not known",
            "temporary failure in name resolution",
            "connection refused",
            "connection reset",
            "network is unreachable",
            "network error",
            "failed to establish a new connection",
        )
    ):
        return "network_error"

    if re.search(r"\bhttp\s+4\d{2}\b", combined_msg):
        return "invalid_response"

    for item in chain:
        if type(item).__name__ == "AIClientError":
            return "sdk_error"
        if isinstance(item, ValueError):
            return "invalid_response"
        if isinstance(item, RuntimeError):
            return "sdk_error"

    return "unknown_error"


def _redact_ai_error(message: str) -> str:
    """Redact secrets from error text and cap its length safely."""
    if not isinstance(message, str) or not message.strip():
        return "AI service error."

    cleaned = message[:4096]
    try:
        cleaned = redact_sensitive_info(cleaned)
    except Exception:  # pragma: no cover - redaction must never break fallback.
        pass

    for pattern, replacement in _ERROR_SECRET_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)

    cleaned = "".join(
        " " if (ord(ch) < 32 or ord(ch) == 127) else ch
        for ch in cleaned
        if ch not in ZERO_WIDTH_CHARS
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if len(cleaned) > MAX_ERROR_REASON_LENGTH:
        cleaned = cleaned[: MAX_ERROR_REASON_LENGTH - 3].rstrip() + "..."

    return cleaned or "AI service error."


def sanitize_ai_output(text: str) -> str:
    """
    Sanitize untrusted AI output while preserving Markdown formatting.

    Line breaks and tabs are preserved intentionally. The input is bounded
    before running redaction regexes to avoid excessive CPU work on huge output.
    """
    if not isinstance(text, str):
        return ""

    bounded = text[:MAX_AI_OUTPUT_LENGTH]
    filtered_chars: list[str] = []
    for ch in bounded:
        if ch in ZERO_WIDTH_CHARS:
            continue
        code = ord(ch)
        if 0 <= code < 32 and ch not in ("\n", "\r", "\t"):
            continue
        if code == 127 or 0x80 <= code <= 0x9F:
            continue
        filtered_chars.append(ch)

    cleaned = "".join(filtered_chars)
    try:
        cleaned = redact_sensitive_info(cleaned)
    except Exception:  # pragma: no cover - output sanitization must not fail.
        pass

    for pattern, replacement in _ERROR_SECRET_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)

    return cleaned.strip()


class _CircuitBreaker:
    """Small thread-safe circuit breaker guarding against repeated timeouts."""

    def __init__(
        self,
        failure_threshold: int = 3,
        cooldown_seconds: float = 30.0,
    ) -> None:
        self.failure_threshold = max(1, int(failure_threshold))
        self.cooldown_seconds = max(0.1, float(cooldown_seconds))
        self._lock = threading.Lock()
        self._failure_count = 0
        self._opened_until = 0.0
        self._last_category = "circuit_open"
        self._last_reason = "AI circuit breaker is open due to recent failures."

    @staticmethod
    def is_enabled() -> bool:
        """Return whether the breaker is enabled by environment configuration."""
        raw = os.getenv("HERMES_AI_CIRCUIT_BREAKER", "1")
        return raw.strip().lower() not in {"0", "false", "no", "off"}

    def allow_request(self) -> tuple[bool, str, str]:
        """Return ``(allowed, category, reason)`` for the next request."""
        if not self.is_enabled():
            return True, "", ""
        now = time.monotonic()
        with self._lock:
            if self._opened_until > now:
                return False, self._last_category, self._last_reason
            return True, "", ""

    def record_success(self) -> None:
        """Reset failure counters after a successful call."""
        with self._lock:
            self._failure_count = 0
            self._opened_until = 0.0

    def record_failure(self, category: str, reason: str) -> None:
        """Record a failure and open the circuit at the configured threshold."""
        if not self.is_enabled():
            return
        now = time.monotonic()
        with self._lock:
            self._failure_count += 1
            self._last_category = category or "unknown_error"
            self._last_reason = reason or "AI service temporarily unavailable."
            if self._failure_count >= self.failure_threshold:
                self._opened_until = now + self.cooldown_seconds

    def reset(self) -> None:
        """Reset the breaker to its initial closed state."""
        with self._lock:
            self._failure_count = 0
            self._opened_until = 0.0
            self._last_category = "circuit_open"
            self._last_reason = "AI circuit breaker is open due to recent failures."


_GLOBAL_AI_CIRCUIT_BREAKER = _CircuitBreaker()


def reset_ai_circuit_breaker() -> None:
    """Reset the global AI circuit breaker (used by tests)."""
    _GLOBAL_AI_CIRCUIT_BREAKER.reset()


class SafeAIGateway:
    """
    Fail-closed AI gateway wrapping HermesAIClient with MockClient fallback.

    Any operational, network, SDK, configuration, or response-shape failure is
    converted into a safe degraded result; exceptions never reach the caller.
    """

    def __init__(
        self,
        client: Any | None = None,
        fallback_client: Any | None = None,
        *,
        mode: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        use_circuit_breaker: bool | None = None,
    ) -> None:
        self._injected_client = client
        self.fallback_client = (
            fallback_client if fallback_client is not None else MockClient()
        )
        self._mode = mode
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        if use_circuit_breaker is None:
            self._use_circuit_breaker = client is None
        else:
            self._use_circuit_breaker = bool(use_circuit_breaker)

    def _resolve_client(self) -> Any:
        """Resolve an injected client or lazily import HermesAIClient."""
        if self._injected_client is not None:
            return self._injected_client

        from hermes.ai.client import HermesAIClient

        kwargs: dict[str, Any] = {}
        if self._mode is not None:
            kwargs["mode"] = self._mode
        if self._api_key is not None:
            kwargs["api_key"] = self._api_key
        if self._model is not None:
            kwargs["model"] = self._model
        if self._timeout is not None:
            kwargs["timeout"] = self._timeout
        return HermesAIClient(**kwargs)

    @staticmethod
    def _blocked_result(
        reason: str,
        category: str = "input_blocked",
    ) -> SafeAIResult:
        """Build a fail-closed result for rejected input."""
        return SafeAIResult(
            text="",
            allowed=False,
            is_mock=False,
            degraded=False,
            mode="blocked",
            model="guardrails",
            error_category=category or "input_blocked",
            reason=(
                _redact_ai_error(reason)
                if reason
                else "Input blocked by security guardrails."
            ),
        )

    def _fallback(
        self,
        exc: BaseException,
        prompt: str = "",
        *,
        override_category: str | None = None,
        override_reason: str | None = None,
    ) -> SafeAIResult:
        """Convert any failure into a safe degraded MockClient result."""
        _ = prompt  # Prompt is intentionally never echoed by the fallback.
        category = override_category or classify_ai_error(exc)
        reason = override_reason or _redact_ai_error(str(exc))

        if self._use_circuit_breaker and override_category is None:
            _GLOBAL_AI_CIRCUIT_BREAKER.record_failure(category, reason)

        try:
            mock_resp = self.fallback_client.generate("")
            fallback_text = getattr(mock_resp, "text", SAFE_FALLBACK_TEXT)
            if not isinstance(fallback_text, str) or not fallback_text.strip():
                fallback_text = SAFE_FALLBACK_TEXT
            fallback_model = (
                getattr(mock_resp, "model", FALLBACK_MODEL_NAME) or FALLBACK_MODEL_NAME
            )
        except Exception:  # pragma: no cover - MockClient is deterministic.
            fallback_text = SAFE_FALLBACK_TEXT
            fallback_model = FALLBACK_MODEL_NAME

        return SafeAIResult(
            text=fallback_text,
            allowed=False,
            is_mock=True,
            degraded=True,
            mode="mock",
            model=str(fallback_model),
            error_category=category,
            reason=reason,
        )

    def generate(
        self,
        prompt: str,
        system_instruction: str | None = None,
    ) -> SafeAIResult:
        """Generate a response with fail-closed fallback on every failure."""
        try:
            guard = validate_and_clean(prompt)
        except Exception as exc:
            return self._blocked_result(f"Input validation failed: {exc}")

        if not getattr(guard, "allowed", False):
            return self._blocked_result(
                getattr(guard, "reason", "Input blocked by guardrails."),
                getattr(guard, "category", "") or "input_blocked",
            )

        cleaned_prompt = getattr(guard, "cleaned_text", "")
        if not isinstance(cleaned_prompt, str) or not cleaned_prompt.strip():
            return self._blocked_result("Input is empty after sanitization.")

        safe_system_instruction: str | None = None
        if system_instruction is not None:
            if not isinstance(system_instruction, str):
                return self._fallback(
                    ValueError("Invalid system_instruction type."),
                    override_category="config_error",
                    override_reason=(
                        "system_instruction must be a string when provided."
                    ),
                )
            safe_system_instruction = sanitize_ai_output(system_instruction)

        if self._use_circuit_breaker:
            allowed_call, cb_category, cb_reason = (
                _GLOBAL_AI_CIRCUIT_BREAKER.allow_request()
            )
            if not allowed_call:
                return self._fallback(
                    RuntimeError(cb_reason),
                    override_category=cb_category,
                    override_reason=cb_reason,
                )

        try:
            client = self._resolve_client()
        except Exception as exc:
            return self._fallback(exc)

        try:
            if safe_system_instruction is not None:
                response = client.generate(
                    cleaned_prompt,
                    system_instruction=safe_system_instruction,
                )
            else:
                response = client.generate(cleaned_prompt)

            raw_text = getattr(response, "text", "")
            if not isinstance(raw_text, str) or not raw_text.strip():
                raise EmptyAIResponseError("AI service returned an empty response.")

            safe_text = sanitize_ai_output(raw_text)
            if not safe_text:
                raise EmptyAIResponseError(
                    "AI output became empty after output sanitization."
                )

            resp_mode = (
                str(getattr(response, "mode", self._mode or "gemini") or "gemini")
                .strip()
                .lower()
            )
            resp_is_mock = bool(getattr(response, "is_mock", resp_mode == "mock"))
            resp_model = str(
                getattr(response, "model", self._model or "unknown") or "unknown"
            )

            if self._use_circuit_breaker:
                _GLOBAL_AI_CIRCUIT_BREAKER.record_success()

            return SafeAIResult(
                text=safe_text,
                allowed=True,
                is_mock=resp_is_mock,
                degraded=False,
                mode=resp_mode,
                model=resp_model,
                error_category="",
                reason="",
            )
        except Exception as exc:
            return self._fallback(exc)

    def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
    ) -> str:
        """
        Return display-safe text for CLI/UI.

        Automated orchestration should call ``generate()`` and inspect
        ``allowed``/``degraded`` instead of relying on the raw text alone.
        """
        result = self.generate(
            prompt,
            system_instruction=system_instruction,
        )
        if result.mode == "blocked":
            return SAFE_BLOCKED_TEXT
        return result.text


def safe_generate(
    prompt: str,
    *,
    mode: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    timeout: float | None = None,
    system_instruction: str | None = None,
    client: Any | None = None,
    fallback_client: Any | None = None,
    use_circuit_breaker: bool | None = None,
) -> SafeAIResult:
    """Module-level entrypoint for fail-closed generation with fallback."""
    gateway = SafeAIGateway(
        client=client,
        fallback_client=fallback_client,
        mode=mode,
        api_key=api_key,
        model=model,
        timeout=timeout,
        use_circuit_breaker=use_circuit_breaker,
    )
    return gateway.generate(
        prompt,
        system_instruction=system_instruction,
    )


def safe_generate_text(
    prompt: str,
    **kwargs: Any,
) -> str:
    """Return display-safe generated text; blocked input returns a fixed notice."""
    gateway = SafeAIGateway(
        client=kwargs.pop("client", None),
        fallback_client=kwargs.pop("fallback_client", None),
        mode=kwargs.pop("mode", None),
        api_key=kwargs.pop("api_key", None),
        model=kwargs.pop("model", None),
        timeout=kwargs.pop("timeout", None),
        use_circuit_breaker=kwargs.pop("use_circuit_breaker", None),
    )
    return gateway.generate_text(
        prompt,
        system_instruction=kwargs.pop("system_instruction", None),
    )


# Aliases for seamless integration with existing orchestration code.
FailClosedAIGateway = SafeAIGateway
SafeMockClient = MockClient
FallbackMockClient = MockClient
AIFallbackResult = SafeAIResult
generate_with_fallback = safe_generate
call_ai_with_fallback = safe_generate
