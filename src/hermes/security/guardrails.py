import re


def sanitize_input(text: str) -> tuple[bool, str]:
    """
    Check for prompt injection patterns, forbidden keywords, and excessive length.
    Returns a tuple of (is_safe, message).
    """
    if not text:
        return False, "Input cannot be empty."

    if len(text) > 1000:
        return False, "Input exceeds maximum allowed length of 1000 characters."

    # Very basic prompt injection patterns (for demonstration)
    injection_patterns = [
        r"ignore all previous instructions",
        r"system prompt",
        r"bypass",
        r"you are now",
        r"jailbreak",
    ]

    text_lower = text.lower()

    for pattern in injection_patterns:
        if re.search(pattern, text_lower):
            return False, "Potential prompt injection detected."

    # Forbidden keywords (e.g., related to non-goals like doing homework)
    forbidden_keywords = [
        "do my homework",
        "write code for me",
        "solve this assignment",
    ]

    for keyword in forbidden_keywords:
        if keyword in text_lower:
            return (
                False,
                "Request violates system boundaries (e.g., asking to do homework).",
            )

    return True, "Input is safe."
