import os


class GeminiClient:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")

    def extract_deadline_and_task(self, text: str) -> dict:
        """
        Extract task and deadline from text.
        If GEMINI_API_KEY is not set, use deterministic offline Mock mode.
        """
        if not self.api_key:
            # Mock mode
            return {"task": "Mocked Task", "deadline": "2024-12-31"}

        # Real API call logic would go here.
        return {"task": "Extracted Task", "deadline": "2025-01-01"}


def generate_response(prompt: str) -> str:
    """
    Placeholder for LLM wrapper with mock/fallback mode (R4).
    """
    return "This is a mocked LLM response."
