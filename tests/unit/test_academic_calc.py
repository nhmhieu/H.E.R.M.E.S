from hermes.engines.academic_calc import calculate_gpa, check_academic_warning


def test_calculate_gpa_empty():
    res = calculate_gpa([])
    assert res["gpa_scale_10"] == 0.0
    assert res["gpa_scale_4"] == 0.0
    assert res["total_credits"] == 0


def test_calculate_gpa_normal():
    grades = [
        {"subject": "Math", "grade": 8.0, "credits": 3},
        {"subject": "Physics", "grade": 7.0, "credits": 4},
    ]
    # (8*3 + 7*4) / 7 = 52 / 7 = 7.428... -> 7.43
    res = calculate_gpa(grades)
    assert res["gpa_scale_10"] == 7.43
    assert res["gpa_scale_4"] == 3.0
    assert res["total_credits"] == 7


def test_calculate_gpa_high():
    grades = [
        {"subject": "A", "grade": 9.5, "credits": 3},
        {"subject": "B", "grade": 9.0, "credits": 4},
    ]
    res = calculate_gpa(grades)
    assert res["gpa_scale_10"] > 9.0
    assert res["gpa_scale_4"] == 4.0


def test_check_academic_warning_safe():
    result = check_academic_warning(2.5, 3)
    assert result["is_warning"] is False
    assert result["status"] == "Normal: Good Standing"


def test_check_academic_warning_sem1():
    result = check_academic_warning(0.7, 1)
    assert result["is_warning"] is True
    assert result["warning_level"] == 1
    assert result["status"] == "Warning Level 1"


def test_check_academic_warning_sem3_consecutive():
    result = check_academic_warning(1.0, 3, consecutive_warnings=2)
    assert result["is_warning"] is True
    assert result["warning_level"] == 3
    assert result["status"] == "Warning Level 3: Expulsion Risk"
