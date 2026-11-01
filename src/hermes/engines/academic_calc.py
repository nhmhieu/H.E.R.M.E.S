def convert_score_to_4_and_letter(grade_10: float) -> tuple[float, str]:
    """
    Quy đổi điểm hệ 10 sang điểm hệ 4 và điểm chữ
    theo chuẩn Quy chế đào tạo HCMUS (Điều 11).
    """
    if grade_10 >= 9.0:
        return 4.0, "A+"
    elif grade_10 >= 8.0:
        return 3.5, "A"
    elif grade_10 >= 7.0:
        return 3.0, "B+"
    elif grade_10 >= 6.0:
        return 2.5, "B"
    elif grade_10 >= 5.0:
        return 2.0, "C"
    elif grade_10 >= 4.0:
        return 1.5, "D+"
    elif grade_10 >= 3.0:
        return 1.0, "D"
    else:
        return 0.0, "F"


def calculate_gpa_10(grades: list[tuple[float, int]]) -> float:
    """
    Tính Điểm trung bình (GPA) hệ 10 gia quyền theo số tín chỉ.
    grades: danh sách các tuple (điểm học phần hệ 10, số tín chỉ)
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


# Alias for backward compatibility
calculate_gpa = calculate_gpa_10


def calculate_gpa_4(grades: list[tuple[float, int]]) -> float:
    """
    Tính Điểm trung bình (GPA) hệ 4:
    Quy đổi từng điểm hệ 10 sang hệ 4, sau đó tính trung bình gia quyền theo số tín chỉ.
    grades: danh sách các tuple (điểm học phần hệ 10, số tín chỉ)
    """
    if not grades:
        return 0.0

    total_points = 0.0
    total_credits = 0

    for grade_10, credits in grades:
        grade_4, _ = convert_score_to_4_and_letter(grade_10)
        total_points += grade_4 * credits
        total_credits += credits

    if total_credits == 0:
        return 0.0

    return round(total_points / total_credits, 2)


def check_academic_warning(
    current_semester_earned_credits: int,
    accumulated_credits: int,
    previous_semester_gpa: float | None,
    two_previous_semesters_gpa: float | None,
    consecutive_warnings: int = 0,
) -> dict:
    """
    Xét cảnh cáo học tập theo Điều 16,
    Sổ tay sinh viên HCMUS 2025-2026.

    current_semester_earned_credits:
        Số tín chỉ đạt trong học kỳ đang xét.

    accumulated_credits:
        Tổng tín chỉ tích lũy tại thời điểm xét.

    previous_semester_gpa:
        GPA hệ 10 của học kỳ liền kề trước đó.

    two_previous_semesters_gpa:
        Giá trị GPA dùng để xét điều kiện hai học kỳ liền kề
        trước đó, được tính theo cách chính thức của trường.
        Không tự giả định cách tính trong hàm này.

    consecutive_warnings:
        Số lần cảnh cáo liên tiếp trước học kỳ đang xét.
    """

    if current_semester_earned_credits < 0:
        raise ValueError("Số tín chỉ đạt không được âm.")

    if accumulated_credits < 0:
        raise ValueError("Số tín chỉ tích lũy không được âm.")

    if consecutive_warnings < 0:
        raise ValueError("Số lần cảnh cáo liên tiếp không được âm.")

    if previous_semester_gpa is not None and not (0 <= previous_semester_gpa <= 10):
        raise ValueError("GPA học kỳ trước phải nằm trong [0, 10].")

    if two_previous_semesters_gpa is not None and not (
        0 <= two_previous_semesters_gpa <= 10
    ):
        raise ValueError("GPA hai học kỳ phải nằm trong [0, 10].")

    reasons = []
    missing_checks = []

    # Điều 16.1.a: tín chỉ đạt trong học kỳ < 7,
    # trừ trường hợp đã tích lũy ít nhất 130 tín chỉ.
    if current_semester_earned_credits < 7 and accumulated_credits < 130:
        reasons.append("Số tín chỉ đạt trong học kỳ nhỏ hơn 7")

    # Điều 16.1.b: GPA học kỳ liền kề trước đó < 3.0.
    if previous_semester_gpa is None:
        missing_checks.append("Chưa có GPA của học kỳ liền kề trước đó")
    elif previous_semester_gpa < 3.0:
        reasons.append("GPA học kỳ liền kề trước đó nhỏ hơn 3.0")

    # Điều 16.1.b: GPA của hai học kỳ liền kề trước đó < 4.0.
    if two_previous_semesters_gpa is None:
        missing_checks.append("Chưa có kết quả GPA để xét hai học kỳ liền kề")
    elif two_previous_semesters_gpa < 4.0:
        reasons.append("GPA xét cho hai học kỳ liền kề nhỏ hơn 4.0")

    # Chỉ kết luận không bị cảnh cáo khi đã kiểm tra đủ điều kiện.
    if reasons:
        is_warning = True
    elif missing_checks:
        is_warning = None
    else:
        is_warning = False

    # Chỉ cập nhật lịch sử khi kết quả xét đã xác định.
    if is_warning is True:
        new_consecutive_warnings = consecutive_warnings + 1
    elif is_warning is False:
        new_consecutive_warnings = 0
    else:
        new_consecutive_warnings = consecutive_warnings

    # Điều 16.2.c: cảnh cáo học tập lần thứ ba liên tiếp.
    third_consecutive_warning = is_warning is True and new_consecutive_warnings >= 3

    if third_consecutive_warning:
        status = (
            "Cảnh cáo học tập lần thứ ba liên tiếp; "
            "thuộc trường hợp buộc thôi học theo Điều 16.2.c"
        )
    elif is_warning is True:
        status = "Cảnh cáo học tập"
    elif is_warning is False:
        status = "Không thuộc diện cảnh cáo theo các tiêu chí đã xét"
    else:
        status = "Chưa đủ dữ liệu để kết luận"

    return {
        "is_warning": is_warning,
        "status": status,
        "reasons": reasons,
        "missing_checks": missing_checks,
        "consecutive_warnings": new_consecutive_warnings,
        "third_consecutive_warning": third_consecutive_warning,
    }
