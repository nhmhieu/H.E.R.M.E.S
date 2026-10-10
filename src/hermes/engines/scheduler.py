def generate_study_plan(
    subjects: list[dict], available_daily_hours: float, days_left: int
) -> list[dict]:
    """
    Generate a deterministic, conflict-free study plan.
    Subjects format: [{'name': 'Math', 'credits': 4, 'priority': 1}, ...]
    """
    if not subjects or available_daily_hours <= 0 or days_left <= 0:
        return []

    total_available_hours = available_daily_hours * days_left

    # Sort subjects by priority (highest first) then credits (highest first)
    sorted_subjects = sorted(
        subjects,
        key=lambda x: (x.get("priority", 0), x.get("credits", 0)),
        reverse=True,
    )

    plan = []
    remaining_hours = total_available_hours

    # Simple deterministic allocation based on credits
    total_credits = sum(s.get("credits", 1) for s in sorted_subjects)

    if total_credits == 0:
        return []

    for subject in sorted_subjects:
        if remaining_hours <= 0:
            break

        # Allocate hours proportionally to credits, but at least 1 hour if possible
        allocation_ratio = subject.get("credits", 1) / total_credits
        allocated_hours = round(total_available_hours * allocation_ratio, 1)

        # Ensure we don't exceed remaining hours
        allocated_hours = min(allocated_hours, remaining_hours)

        # Give at least 1 hour if we have remaining hours and calculated allocation is very small
        if allocated_hours < 1.0 and remaining_hours >= 1.0:
            allocated_hours = 1.0

        remaining_hours -= allocated_hours

        plan.append(
            {
                "subject": subject.get("name", "Unknown"),
                "allocated_hours": allocated_hours,
                "daily_hours": round(allocated_hours / days_left, 2),
            }
        )

    return plan
