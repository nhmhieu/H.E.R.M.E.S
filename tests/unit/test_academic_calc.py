# from hermes.engines.academic_calc import calculate_gpa, check_academic_warning


# def test_calculate_gpa_empty():
#     assert calculate_gpa([]) == 0.0


# def test_calculate_gpa_normal():
#     grades = [(8.0, 3), (7.0, 4)]
#     # (8*3 + 7*4) / 7 = 52 / 7 = 7.428... -> 7.43
#     assert calculate_gpa(grades) == 7.43


# def test_check_academic_warning_safe():
#     result = check_academic_warning(7.5, 30)
#     assert result["is_warning"] is False
#     assert result["status"] == "Normal: Good Standing"


# def test_check_academic_warning_level_1():
#     result = check_academic_warning(4.5, 30)
#     assert result["is_warning"] is True
#     assert result["status"] == "Warning Level 1: Academic Warning"


# def test_check_academic_warning_level_3():
#     result = check_academic_warning(2.5, 30)
#     assert result["is_warning"] is True
#     assert result["status"] == "Warning Level 3: Academic Probation / Dismissal Risk"




import pytest

from hermes.engines.academic_calc import (
    convert_score_to_4_and_letter,
    calculate_gpa_10,
    calculate_gpa_4,
    check_academic_warning,
)


# ==========================================
# 1. Tests for convert_score_to_4_and_letter
# ==========================================

@pytest.mark.parametrize(
    "grade, expected_4, expected_letter",
    [
        (10.0, 4.0, "A+"),
        (9.0, 4.0, "A+"),
        (8.9, 3.5, "A"),
        (8.0, 3.5, "A"),
        (7.9, 3.0, "B+"),
        (7.0, 3.0, "B+"),
        (6.9, 2.5, "B"),
        (6.0, 2.5, "B"),
        (5.9, 2.0, "C"),
        (5.0, 2.0, "C"),
        (4.9, 1.5, "D+"),
        (4.0, 1.5, "D+"),
        (3.9, 1.0, "D"),
        (3.0, 1.0, "D"),
        (2.9, 0.0, "F"),
        (0.0, 0.0, "F"),
    ],
)
def test_convert_score_to_4_and_letter(
    grade, expected_4, expected_letter
):
    assert convert_score_to_4_and_letter(grade) == (
        expected_4,
        expected_letter,
    )


# ======================
# 2. Tests for GPA 10
# ======================

def test_calculate_gpa_10_weighted_average():
    # GPA = (8*3 + 6*2) / (3+2) = 7.2
    assert calculate_gpa_10([(8.0, 3), (6.0, 2)]) == 7.2


def test_calculate_gpa_10_single_course():
    assert calculate_gpa_10([(8.5, 3)]) == 8.5


def test_calculate_gpa_10_empty_list():
    assert calculate_gpa_10([]) == 0.0


def test_calculate_gpa_10_zero_total_credits():
    assert calculate_gpa_10([(8.0, 0), (7.0, 0)]) == 0.0


# ======================
# 3. Tests for GPA 4
# ======================

def test_calculate_gpa_4_converts_each_course_before_averaging():
    # 8.0 -> 3.5; 6.0 -> 2.5
    # GPA 4 = (3.5*3 + 2.5*1) / 4 = 3.25
    assert calculate_gpa_4([(8.0, 3), (6.0, 1)]) == 3.25


def test_calculate_gpa_4_empty_list():
    assert calculate_gpa_4([]) == 0.0


# ===========================
# 4. Tests for academic warning
# ===========================

def test_warning_when_earned_credits_below_7():
    result = check_academic_warning(
        current_semester_earned_credits=6,
        accumulated_credits=50,
        previous_semester_gpa=5.0,
        two_previous_semesters_gpa=5.0,
        consecutive_warnings=0,
    )

    assert result["is_warning"] is True
    assert result["consecutive_warnings"] == 1
    assert any("tín chỉ" in reason for reason in result["reasons"])


def test_no_credit_warning_when_accumulated_credits_at_least_130():
    result = check_academic_warning(
        current_semester_earned_credits=6,
        accumulated_credits=130,
        previous_semester_gpa=5.0,
        two_previous_semesters_gpa=5.0,
        consecutive_warnings=0,
    )

    assert not any("tín chỉ" in reason for reason in result["reasons"])


def test_warning_when_previous_semester_gpa_below_3():
    result = check_academic_warning(
        current_semester_earned_credits=10,
        accumulated_credits=50,
        previous_semester_gpa=2.9,
        two_previous_semesters_gpa=5.0,
        consecutive_warnings=0,
    )

    assert result["is_warning"] is True
    assert any("3.0" in reason for reason in result["reasons"])


def test_warning_when_two_semester_gpa_below_4():
    result = check_academic_warning(
        current_semester_earned_credits=10,
        accumulated_credits=50,
        previous_semester_gpa=5.0,
        two_previous_semesters_gpa=3.9,
        consecutive_warnings=0,
    )

    assert result["is_warning"] is True
    assert any("4.0" in reason for reason in result["reasons"])


def test_no_warning_when_all_conditions_are_satisfied():
    result = check_academic_warning(
        current_semester_earned_credits=10,
        accumulated_credits=50,
        previous_semester_gpa=5.0,
        two_previous_semesters_gpa=5.0,
        consecutive_warnings=0,
    )

    assert result["is_warning"] is False
    assert result["consecutive_warnings"] == 0


def test_third_consecutive_warning_is_flagged():
    result = check_academic_warning(
        current_semester_earned_credits=6,
        accumulated_credits=50,
        previous_semester_gpa=5.0,
        two_previous_semesters_gpa=5.0,
        consecutive_warnings=2,
    )

    assert result["is_warning"] is True
    assert result["consecutive_warnings"] == 3
    assert result["third_consecutive_warning"] is True


def test_missing_gpa_data_does_not_claim_no_warning():
    result = check_academic_warning(
        current_semester_earned_credits=10,
        accumulated_credits=50,
        previous_semester_gpa=None,
        two_previous_semesters_gpa=None,
        consecutive_warnings=0,
    )

    assert result["is_warning"] is None
    assert result["missing_checks"]


# ==========================
# 5. Tests for invalid inputs
# ==========================

@pytest.mark.parametrize(
    "current_credits, accumulated_credits, consecutive_warnings",
    [
        (-1, 50, 0),
        (10, -1, 0),
        (10, 50, -1),
    ],
)
def test_warning_rejects_negative_counts(
    current_credits, accumulated_credits, consecutive_warnings
):
    with pytest.raises(ValueError):
        check_academic_warning(
            current_semester_earned_credits=current_credits,
            accumulated_credits=accumulated_credits,
            previous_semester_gpa=5.0,
            two_previous_semesters_gpa=5.0,
            consecutive_warnings=consecutive_warnings,
        )


def test_warning_rejects_gpa_out_of_range():
    with pytest.raises(ValueError):
        check_academic_warning(
            current_semester_earned_credits=10,
            accumulated_credits=50,
            previous_semester_gpa=11.0,
            two_previous_semesters_gpa=5.0,
            consecutive_warnings=0,
        )
