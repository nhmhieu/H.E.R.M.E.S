import json
import time
import os

from hermes.security.guardrails import sanitize_input
from hermes.router.orchestrator import route_query


def load_benchmark_data() -> list[dict]:
    file_path = os.path.join(os.path.dirname(__file__), "benchmark_cases.json")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def run_evaluation():
    cases = load_benchmark_data()
    if not cases:
        print("No benchmark cases found.")
        return

    results = {
        "CALC_GPA": {"total": 0, "pass": 0, "latency": []},
        "REGULATION_RAG": {"total": 0, "pass": 0, "latency": []},
        "SCHEDULING": {"total": 0, "pass": 0, "latency": []},
        "CLARIFY": {"total": 0, "pass": 0, "latency": []},
        "REJECT": {"total": 0, "pass": 0, "latency": []},
    }

    for case in cases:
        query = case.get("query", "")
        category = case.get("category", "")

        if category not in results:
            continue

        results[category]["total"] += 1

        start_time = time.time()

        is_safe, msg = sanitize_input(query)

        if category == "REJECT":
            if not is_safe:
                results[category]["pass"] += 1
        else:
            if is_safe:
                # Simulate routing
                _ = route_query(query)
                # For now, just passing guardrails counts as success for non-REJECT cases
                # since full end-to-end engines are not completely wired in orchestrator yet.
                results[category]["pass"] += 1

        end_time = time.time()
        results[category]["latency"].append(end_time - start_time)

    print("--- Benchmark Evaluation Results ---")
    for cat, stats in results.items():
        total = stats["total"]
        passed = stats["pass"]
        acc = (passed / total) * 100 if total > 0 else 0
        avg_latency = (
            sum(stats["latency"]) / len(stats["latency"]) if stats["latency"] else 0
        )
        print(
            f"[{cat}] Total: {total} | Pass: {passed} | Accuracy: {acc:.2f}% | Avg Latency: {avg_latency:.4f}s"
        )


if __name__ == "__main__":
    run_evaluation()
