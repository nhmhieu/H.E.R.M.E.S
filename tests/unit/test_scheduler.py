import pytest
import random
from datetime import date, timedelta
from src.hermes.engines.scheduler import (
    Exam,
    generate_study_plan,
    schedule_exams,
    simulate_gpa,
)

# ==================== 1. TEST KỊCH BẢN CƠ BẢN & BIÊN ====================


def test_generate_study_plan_normal():
    """Kiểm tra logic phân bổ tổng số giờ ôn theo tỷ lệ tín chỉ và độ ưu tiên bình thường."""
    subjects = [
        {"name": "Toán rời rạc", "credits": 4, "priority": 2},
        {"name": "Lập trình hướng đối tượng", "credits": 3, "priority": 1},
    ]
    available_daily_hours = 4.0
    days_left = 10

    plan = generate_study_plan(subjects, available_daily_hours, days_left)

    assert isinstance(plan, list)
    assert len(plan) == 2
    total_allocated = sum(item["allocated_hours"] for item in plan)
    assert total_allocated <= (available_daily_hours * days_left)


def test_generate_study_plan_empty_subjects():
    """Kiểm tra trường hợp danh sách môn học trống."""
    plan = generate_study_plan([], available_daily_hours=4.0, days_left=10)
    assert isinstance(plan, list)
    assert len(plan) == 0


def test_exam_from_dict_parsing():
    """Kiểm tra phương thức from_dict của class Exam parse đúng định dạng ngày tháng."""
    data = {
        "name": "Mạng máy tính",
        "credits": 3,
        "exam_date": "2026-12-01",
        "study_hours_needed": 10.0,
        "priority": 3,
    }
    exam = Exam.from_dict(data)
    assert exam.name == "Mạng máy tính"
    assert exam.credits == 3
    assert isinstance(exam.exam_date, date)
    assert exam.exam_date.strftime("%Y-%m-%d") == "2026-12-01"


def test_simulate_gpa_normal():
    """Kiểm tra hàm mô phỏng tính điểm GPA tối thiểu cần đạt ở các môn còn lại."""
    current_courses = [{"credits": 4, "grade": 3.5}, {"credits": 3, "grade": 3.0}]
    target_gpa = 3.6
    remaining_credits = 10

    min_gpa = simulate_gpa(current_courses, target_gpa, remaining_credits)

    assert isinstance(min_gpa, float)
    assert min_gpa >= 0.0


# ==================== 2. STRESS TEST TỰ ĐỘNG SINH HÀNG TRĂM TEST CASE ====================


@pytest.mark.parametrize(
    "test_iteration", range(200)
)  # Chạy tự động 200 test case ngẫu nhiên khác nhau
def test_schedule_exams_stress_random(test_iteration):
    """
    Stress test: Tự động sinh ngẫu nhiên từ 1 đến 10 môn học với ngày thi,
    số giờ cần ôn và độ ưu tiên lộn xộn để kiểm tra tính đúng đắn của thuật toán lịch lùi.
    """
    base_date = date(2026, 11, 1)
    num_exams = random.randint(1, 10)

    exams = []
    for i in range(num_exams):
        # Sinh ngày thi ngẫu nhiên trong vòng 1 đến 30 ngày tới
        random_days_offset = random.randint(1, 30)
        exam_date = base_date + timedelta(days=random_days_offset)

        exam_data = {
            "name": f"Môn học số {i}",
            "credits": random.randint(1, 5),
            "exam_date": exam_date.strftime("%Y-%m-%d"),
            "study_hours_needed": float(random.randint(2, 15)),
            "priority": random.randint(1, 3),
        }
        exams.append(Exam.from_dict(exam_data))

    daily_free_hours = float(random.choice([2.0, 3.5, 4.0, 6.0]))

    # Chạy thuật toán lập lịch với dữ liệu ngẫu nhiên
    schedule = schedule_exams(exams, daily_free_hours)

    # --- CÁC BẤT BIẾN (INVARIANTS) CẦN THỎA MÃN TUYỆT ĐỐI ---
    assert isinstance(schedule, dict)

    for date_str, data in schedule.items():
        # 1. Không ngày nào được phân bổ vượt quá số giờ rảnh tối đa cho phép
        assert data["total_assigned"] <= daily_free_hours + 1e-5  # Sai số số thực nhỏ

        # 2. Danh sách task trong ngày phải là list hợp lệ
        assert isinstance(data["tasks"], list)

        for task in data["tasks"]:
            # 3. Số giờ ôn cho mỗi task phải lớn hơn 0
            assert task["hours"] > 0
