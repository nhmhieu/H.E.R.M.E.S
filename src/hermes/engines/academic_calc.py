def calculate_gpa(grades: list[dict]) -> dict:
    """
    Calculate weighted GPA from a list of dictionaries with subject, grade, and credits.
    Maps scale 10 GPA to scale 4 GPA.
    """
    if not grades:
        return {"gpa_scale_10": 0.0, "gpa_scale_4": 0.0, "total_credits": 0}

    total_points = 0.0
    total_credits = 0

    for item in grades:
        grade = item.get("grade", 0.0)
        credits = item.get("credits", 0)
        total_points += grade * credits
        total_credits += credits

    if total_credits == 0:
        return {"gpa_scale_10": 0.0, "gpa_scale_4": 0.0, "total_credits": 0}

    gpa_10 = round(total_points / total_credits, 2)

    # Scale 4 mapping
    if gpa_10 >= 9.0:
        gpa_4 = 4.0
    elif gpa_10 >= 8.5:
        gpa_4 = 3.75
    elif gpa_10 >= 8.0:
        gpa_4 = 3.5
    elif gpa_10 >= 7.0:
        gpa_4 = 3.0
    elif gpa_10 >= 6.5:
        gpa_4 = 2.5
    elif gpa_10 >= 5.5:
        gpa_4 = 2.0
    elif gpa_10 >= 5.0:
        gpa_4 = 1.5
    elif gpa_10 >= 4.0:
        gpa_4 = 1.0
    else:
        gpa_4 = 0.0

    return {
        "gpa_scale_10": gpa_10,
        "gpa_scale_4": gpa_4,
        "total_credits": total_credits,
    }


def check_academic_warning(
    cumulative_gpa: float, semester: int, consecutive_warnings: int = 0
) -> dict:
    """
    Check academic warning status based on cumulative GPA (scale 4 assumed by threshold values) and semester.
    Standard HCMUS regulations.
    """
    is_warning = False
    warning_level = 0
    status = "Normal: Good Standing"
    advice = "Keep up the good work."

    # Check for new warnings this semester
    new_warning = False
    if semester == 1 and cumulative_gpa < 0.80:
        new_warning = True
    elif semester == 2 and cumulative_gpa < 1.00:
        new_warning = True
    elif semester >= 3 and cumulative_gpa < 1.20:
        new_warning = True

    current_consecutive_warnings = consecutive_warnings
    if new_warning:
        current_consecutive_warnings += 1
    else:
        current_consecutive_warnings = 0

    if current_consecutive_warnings >= 3:
        is_warning = True
        warning_level = 3
        status = "Warning Level 3: Expulsion Risk"
        advice = "Immediate consultation with academic advisor is required."
    elif current_consecutive_warnings == 2:
        is_warning = True
        warning_level = 2
        status = "Warning Level 2"
        advice = "You are at high risk. Please improve your GPA next semester."
    elif current_consecutive_warnings == 1:
        is_warning = True
        warning_level = 1
        status = "Warning Level 1"
        advice = (
            "Your GPA is below the threshold for this semester. Focus on your studies."
        )

    return {
        "is_warning": is_warning,
        "warning_level": warning_level,
        "status": status,
        "advice": advice,
    }
