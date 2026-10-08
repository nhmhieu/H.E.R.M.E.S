def calculate_gpa(grades: list[tuple[float, int]]) -> float:
    """
    Calculate weighted GPA from a list of (grade, credits) tuples.
    """
    if not grades:
        return 0.0

    total_points = 0.0
    total_credits = 0

    for grade, credits in grades:
        total_points += grade * credits
        total_credits += credits

    if total_credits == 0:
        return 0.0

    return round(total_points / total_credits, 2)

def check_academic_warning(gpa: float, accumulated_credits: int) -> dict:
    """
    Check academic warning status based on GPA and accumulated credits.
    Standard HCMUS regulations.
    """
    if gpa < 3.0:
        status = "Warning Level 3: Academic Probation / Dismissal Risk"
        is_warning = True
    elif gpa < 4.0:
        status = "Warning Level 2: Strict Academic Warning"
        is_warning = True
    elif gpa < 5.0:
        status = "Warning Level 1: Academic Warning"
        is_warning = True
    else:
        status = "Normal: Good Standing"
        is_warning = False

    return {
        "is_warning": is_warning,
        "status": status,
        "gpa": gpa,
        "credits": accumulated_credits
    }
