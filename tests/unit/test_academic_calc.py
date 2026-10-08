from hermes.engines.academic_calc import calculate_gpa, check_academic_warning


def test_calculate_gpa_empty():
    assert calculate_gpa([]) == 0.0


def test_calculate_gpa_normal():
    grades = [(8.0, 3), (7.0, 4)]
    # (8*3 + 7*4) / 7 = 52 / 7 = 7.428... -> 7.43
    assert calculate_gpa(grades) == 7.43


def test_check_academic_warning_safe():
    result = check_academic_warning(7.5, 30)
    assert result["is_warning"] is False
    assert result["status"] == "Normal: Good Standing"


def test_check_academic_warning_level_1():
    result = check_academic_warning(4.5, 30)
    assert result["is_warning"] is True
    assert result["status"] == "Warning Level 1: Academic Warning"


def test_check_academic_warning_level_3():
    result = check_academic_warning(2.5, 30)
    assert result["is_warning"] is True
    assert result["status"] == "Warning Level 3: Academic Probation / Dismissal Risk"
