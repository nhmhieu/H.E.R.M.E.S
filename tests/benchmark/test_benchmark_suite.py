import json
import os


def load_benchmark_data() -> list[dict]:
    file_path = os.path.join(os.path.dirname(__file__), "benchmark_cases.json")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def test_baseline_benchmark():
    """
    Verify the benchmark data is valid.
    """
    data = load_benchmark_data()
    assert len(data) >= 50, f"Expected at least 50 test cases, got {len(data)}"

    categories = ["CALC_GPA", "REGULATION_RAG", "SCHEDULING", "CLARIFY", "REJECT"]

    for item in data:
        assert "query" in item
        assert "category" in item
        assert item["category"] in categories
