from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class Exam:
    name: str
    credits: int
    exam_date: datetime
    study_hours_needed: float
    priority: int = 0

    @classmethod
    # Ham parsing raw data o dang json, frequest api sang doi tuong Exam :
    def from_dict(cls, data: dict):
        exam_date_val = data.get("exam_date")
        if isinstance(exam_date_val, str):
            exam_date_val = datetime.strptime(exam_date_val, "%Y-%m-%d")
        return cls(
            name=data.get("name", "Unknown"),
            credits=data.get("credits", 1),
            exam_date=exam_date_val,
            study_hours_needed=float(data.get("study_hours_needed", 0.0)),
            priority=data.get("priority", 0),
        )


def generate_study_plan(
    subjects: list[dict], available_daily_hours: float, days_left: int
) -> list[dict]:

    if not subjects or available_daily_hours <= 0 or days_left <= 0:
        return []

    total_available_hours = available_daily_hours * days_left

    # Sắp xếp môn theo priority giảm dần, sau đó đến credits giảm dần
    sorted_subjects = sorted(
        subjects,
        key=lambda x: (x.get("priority", 0), x.get("credits", 0)),
        reverse=True,
    )

    plan = []
    remaining_hours = total_available_hours
    total_credits = sum(s.get("credits", 1) for s in sorted_subjects)

    if total_credits == 0:
        return []

    for subject in sorted_subjects:
        if remaining_hours <= 0:
            break

        allocation_ratio = subject.get("credits", 1) / total_credits
        allocated_hours = round(total_available_hours * allocation_ratio, 1)
        allocated_hours = min(allocated_hours, remaining_hours)

        if allocated_hours < 1.0 and remaining_hours >= 1.0:
            allocated_hours = 1.0

        remaining_hours -= allocated_hours

        plan.append(
            {
                "name": subject.get("name", "Unknown"),
                "credits": subject.get("credits", 1),
                "priority": subject.get("priority", 0),
                "study_hours_needed": allocated_hours,
                "allocated_hours": allocated_hours,
                "daily_hours": round(allocated_hours / days_left, 2),
            }
        )

    return plan


def schedule_exams(exams: list[Exam], daily_free_hours: float):

    # Sắp xếp các môn theo ngày thi tăng dần (môn nào thi trước ôn trước)
    sorted_exams = sorted(exams, key=lambda x: x.exam_date)

    schedule = {}

    for exam in sorted_exams:
        hours_left = exam.study_hours_needed
        current_date = exam.exam_date - timedelta(days=1)

        while hours_left > 0:
            date_str = current_date.strftime("%Y-%m-%d")

            if date_str not in schedule:
                schedule[date_str] = {"total_assigned": 0.0, "tasks": []}

            available_slot = daily_free_hours - schedule[date_str]["total_assigned"]

            if available_slot > 0:
                hours_to_allocate = min(hours_left, available_slot)
                schedule[date_str]["tasks"].append(
                    {"subject": exam.name, "hours": hours_to_allocate}
                )
                schedule[date_str]["total_assigned"] += hours_to_allocate
                hours_left -= hours_to_allocate

            current_date -= timedelta(days=1)

            if (exam.exam_date - current_date).days > 60:
                break

    return schedule


def simulate_gpa(current_courses, target_gpa, remaining_credits):
    """
    Mô phỏng điểm số (tính điểm tối thiểu cần đạt).
    """
    total_current_points = sum(c["credits"] * c["grade"] for c in current_courses)
    total_current_credits = sum(c["credits"] for c in current_courses)

    total_target_credits = total_current_credits + remaining_credits
    if total_target_credits <= 0:
        return 0.0

    total_target_points = target_gpa * total_target_credits
    points_needed = total_target_points - total_current_points

    if remaining_credits <= 0:
        return 0.0

    min_required_gpa = points_needed / remaining_credits
    return round(min_required_gpa, 2)
