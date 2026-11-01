"""
H.E.R.M.E.S Automated Benchmark Evaluation Script (Role R8 - Member 6: Hồ Ngọc Như Ý).

Evaluates the 72 standardized test cases across all 6 members and outputs
Routing Accuracy (%), Fast-Path Latency (ms), and Error Taxonomy.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time

from hermes.router.orchestrator import INTENT_REJECT, route_query
from hermes.security.guardrails import validate_and_clean

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BENCHMARK_FILE = Path("tests/benchmark/benchmark_cases.json")
REPORT_OUTPUT_FILE = Path("tests/benchmark/baseline_report.json")


def evaluate_single_query(query: str) -> tuple[str, float]:
    """Run Guardrails + Fast-Path Router on a single query and measure latency in ms."""
    start_time = time.perf_counter()

    guard_res = validate_and_clean(query)
    if not guard_res.allowed:
        actual_intent = INTENT_REJECT
    else:
        route_res = route_query(guard_res.cleaned_text)
        actual_intent = route_res["intent"]

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    return actual_intent, round(elapsed_ms, 3)


def run_benchmark() -> dict:
    print("=" * 80)
    print("H.E.R.M.E.S - SCRIPT TỰ ĐỘNG ĐÁNH GIÁ BENCHMARK 72 CÂU HỎI (ROLE R8)")
    print("=" * 80)

    if not BENCHMARK_FILE.exists():
        print(f"Không tìm thấy file dữ liệu test cases tại {BENCHMARK_FILE}")
        return {}

    with open(BENCHMARK_FILE, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    total_cases = len(test_cases)
    correct_count = 0
    total_latency = 0.0
    error_taxonomy = []

    header = (
        f"{'STT':<4} | {'Mã Case':<10} | {'Kỳ Vọng':<18} | "
        f"{'Thực Tế':<18} | {'Kết Quả':<8} | {'Độ Trễ'}"
    )
    print(header)
    print("-" * 80)

    for idx, case in enumerate(test_cases, 1):
        case_id = case.get("id", f"TC_{idx:02d}")
        query = case.get("query", "")
        expected = case.get("expected_intent") or case.get("expected_route", "")

        actual, latency = evaluate_single_query(query)
        total_latency += latency

        is_pass = actual == expected
        if is_pass:
            correct_count += 1
            status_symbol = "PASS ✅"
        else:
            status_symbol = "FAIL ❌"
            error_taxonomy.append(
                {
                    "case_id": case_id,
                    "assigned_member": case.get("assigned_member", "N/A"),
                    "query": query,
                    "expected": expected,
                    "actual": actual,
                    "error_type": "Routing Mismatch",
                }
            )

        print(
            f"{idx:<4} | {case_id:<10} | {expected:<18} | "
            f"{actual:<18} | {status_symbol:<8} | {latency:.3f} ms"
        )

    accuracy_pct = (correct_count / total_cases) * 100.0 if total_cases > 0 else 0.0
    avg_latency = total_latency / total_cases if total_cases > 0 else 0.0

    print("\n" + "=" * 80)
    print("TỔNG HỢP KẾT QUẢ ĐÁNH GIÁ (BENCHMARK REPORT)")
    print("=" * 80)
    print(f"Số câu định tuyến đúng : {correct_count} / {total_cases}")
    print(f"Độ chính xác (Accuracy): {accuracy_pct:.2f}% (Mục tiêu DoD: >= 85.00%)")
    print(f"Độ trễ trung bình      : {avg_latency:.3f} ms (Mục tiêu DoD: < 20.00 ms)")
    print(f"Danh mục lỗi ghi nhận  : {len(error_taxonomy)} câu")

    report_summary = {
        "total_cases": total_cases,
        "correct_routing": correct_count,
        "routing_accuracy_pct": round(accuracy_pct, 2),
        "average_latency_ms": round(avg_latency, 3),
        "error_count": len(error_taxonomy),
        "error_taxonomy": error_taxonomy,
    }

    REPORT_OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(report_summary, f, ensure_ascii=False, indent=2)

    print(f"Báo cáo kết quả đã lưu tại: {REPORT_OUTPUT_FILE}")
    print("=" * 80)
    return report_summary


if __name__ == "__main__":
    run_benchmark()

