"""
Giao diện Web H.E.R.M.E.S — Cổng Cố vấn Học vụ & Quản lý Lịch trình Sinh viên HCMUS.
Thiết kế tập trung vào trải nghiệm thực tế của sinh viên (User-Centric Design):
- Trò chuyện cố vấn tự nhiên, gợi ý câu hỏi nối tiếp theo ngữ cảnh
- Bóc tách thông báo bài tập / lịch Moodle (.ics) gắn liền với Bộ đếm ngược & Thông báo nhắc hạn
- Đồng bộ trực tiếp Bảng điểm cá nhân, Dự báo GPA (What-If) và Lập lịch ôn tập (EDF)
"""

from __future__ import annotations

from datetime import datetime, timedelta
import json
import time
from typing import Any, Iterator

import streamlit as st
import streamlit.components.v1 as components

from hermes.ai.client import extract_announcement_info
from hermes.engines.academic_calc import (
    calculate_gpa_4,
    calculate_gpa_10,
    check_academic_warning,
    convert_score_to_4_and_letter,
)
from hermes.engines.deadline_parser import (
    compute_deadline_status,
    export_deadlines_to_ics,
    parse_ics_deadlines,
)
from hermes.engines.scheduler import generate_study_plan, simulate_gpa
from hermes.router.orchestrator import orchestrate


def _build_default_deadlines() -> list[dict[str, Any]]:
    """Khởi tạo danh sách hạn nộp mẫu sát với thời điểm hiện tại để sinh viên thấy ngay bộ đếm ngược."""
    now = datetime.now()
    d_urgent = (now + timedelta(days=1, hours=14)).strftime("%Y-%m-%d 23:59")
    d_upcoming = (now + timedelta(days=4, hours=6)).strftime("%Y-%m-%d 23:59")
    d_next_week = (now + timedelta(days=9)).strftime("%Y-%m-%d 17:00")
    return [
        {
            "id": "dl-1",
            "course": "CSC10014 - Tư duy Tính toán",
            "summary": "Nộp báo cáo hoàn chỉnh & kiểm tra nhánh main GitHub",
            "deadline": d_urgent,
            "submission_format": "Moodle (.pdf & link repo)",
            "description": "Đảm bảo toàn bộ test pass trước khi nộp.",
            "done": False,
        },
        {
            "id": "dl-2",
            "course": "CSC10004 - Cấu trúc dữ liệu & Giải thuật",
            "summary": "Bài thực hành Cây Đỏ Đen (Red-Black Tree)",
            "deadline": d_upcoming,
            "submission_format": "Moodle (.zip mã nguồn C++)",
            "description": "Đặt tên file nén theo cú pháp MSSV_Lab4.zip.",
            "done": False,
        },
        {
            "id": "dl-3",
            "course": "MTH00003 - Giải tích 1",
            "summary": "Bài tập trực tuyến chương Chuỗi số",
            "deadline": d_next_week,
            "submission_format": "Hệ thống Moodle",
            "description": "Hoàn thành tối thiểu 80% câu hỏi trắc nghiệm.",
            "done": False,
        },
    ]


def _build_sample_ics() -> str:
    now = datetime.now()
    dt1 = (now + timedelta(days=2)).strftime("%Y%m%dT165900Z")
    dt2 = (now + timedelta(days=6)).strftime("%Y%m%dT165900Z")
    return f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//HCMUS Moodle//NONSGML v1.0//EN
BEGIN:VEVENT
UID:event-201@moodle.hcmus.edu.vn
DTSTART:{dt1}
DTEND:{dt1}
SUMMARY:[CSC10006] Nộp Đồ án Thiết kế Cơ sở dữ liệu (ERD & SQL)
CATEGORIES:CSC10006 - Cơ sở dữ liệu
DESCRIPTION:Nộp file script .sql và báo cáo thiết kế qua Moodle trước 23:59.
END:VEVENT
BEGIN:VEVENT
UID:event-202@moodle.hcmus.edu.vn
DTSTART:{dt2}
DTEND:{dt2}
SUMMARY:[CSC10008] Bài lab lập trình Socket TCP/UDP
CATEGORIES:CSC10008 - Mạng máy tính
DESCRIPTION:Nộp mã nguồn Python/C++ kèm hướng dẫn chạy thử.
END:VEVENT
END:VCALENDAR"""


WELCOME_MESSAGE = (
    "Chào bạn! Mình là **H.E.R.M.E.S** — cố vấn học vụ và quản lý lịch trình "
    "dành cho sinh viên **ĐH Khoa học Tự nhiên (ĐHQG-HCM)**.\n\n"
    "Bạn có thể hỏi mình bằng ngôn ngữ tự nhiên như khi nhắn hỏi cố vấn học tập:\n"
    "- **Tra cứu quy chế theo đúng khóa & hệ đào tạo:** Chuẩn đầu ra ngoại ngữ "
    "(IELTS, TOEIC, VSTEP), quy định học phần Anh văn, điều kiện cảnh báo học vụ...\n"
    "- **Tính GPA & Chiến lược cải thiện điểm:** Nhập điểm trực tiếp hoặc gửi bảng điểm "
    "từ thanh bên trái để mình phân tích môn nên ưu tiên kéo điểm.\n"
    "- **Bóc tách lịch & Nhắc hạn tự động:** Dán thông báo bài tập của giảng viên vào đây, "
    "mình sẽ rút gọn thành phiếu nhiệm vụ và cài đếm ngược nhắc hạn cho bạn."
)


def _stream_markdown(text: str) -> Iterator[str]:
    """Hiệu ứng hiển thị câu trả lời mượt mà."""
    lines = text.split("\n")
    for idx, line in enumerate(lines):
        yield line + ("\n" if idx < len(lines) - 1 else "")
        time.sleep(0.012)


def _trigger_browser_notification(title: str, body: str) -> None:
    """Kích hoạt thông báo đẩy trên màn hình máy tính (HTML5 Web Notification API)."""
    safe_title = json.dumps(title, ensure_ascii=False)
    safe_body = json.dumps(body, ensure_ascii=False)
    components.html(
        f"""
        <script>
        (function() {{
            const title = {safe_title};
            const body = {safe_body};
            if (!("Notification" in window)) {{
                return;
            }}
            if (Notification.permission === "granted") {{
                new Notification(title, {{ body: body }});
            }} else if (Notification.permission !== "denied") {{
                Notification.requestPermission().then(function(permission) {{
                    if (permission === "granted") {{
                        new Notification(title, {{ body: body }});
                    }}
                }});
            }}
        }})();
        </script>
        """,
        height=0,
    )


def _inject_clean_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.5rem !important;
            padding-bottom: 2.5rem !important;
            max-width: 1220px !important;
        }
        .hermes-topbar {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-left: 5px solid #1e3a8a;
            border-radius: 10px;
            padding: 1.1rem 1.4rem;
            margin-bottom: 1rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
        }
        .hermes-brand-title {
            font-size: 1.35rem;
            font-weight: 700;
            color: #0f172a;
            margin: 0;
            letter-spacing: -0.01em;
        }
        .hermes-brand-sub {
            font-size: 0.88rem;
            color: #475569;
            margin: 0.2rem 0 0 0;
        }
        .hermes-stat-group {
            display: flex;
            gap: 0.75rem;
            flex-wrap: wrap;
        }
        .hermes-stat-pill {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 0.45rem 0.85rem;
            min-width: 135px;
        }
        .hermes-stat-label {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: #64748b;
            font-weight: 600;
        }
        .hermes-stat-value {
            font-size: 0.98rem;
            font-weight: 700;
            color: #0f172a;
            margin-top: 0.1rem;
        }
        .hermes-alert-banner {
            background: #fffbeb;
            border: 1px solid #fde68a;
            border-left: 4px solid #d97706;
            border-radius: 8px;
            padding: 0.75rem 1.1rem;
            margin-bottom: 1rem;
            color: #92400e;
            font-size: 0.9rem;
        }
        .hermes-dl-card {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 0.95rem 1.15rem;
            margin-bottom: 0.65rem;
        }
        .hermes-badge-urgent {
            background: #fef2f2;
            color: #b91c1c;
            border: 1px solid #fecaca;
            padding: 0.15rem 0.55rem;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .hermes-badge-upcoming {
            background: #fffbeb;
            color: #b45309;
            border: 1px solid #fde68a;
            padding: 0.15rem 0.55rem;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .hermes-badge-normal {
            background: #f0fdf4;
            color: #15803d;
            border: 1px solid #bbf7d0;
            padding: 0.15rem 0.55rem;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .hermes-badge-done {
            background: #f1f5f9;
            color: #475569;
            border: 1px solid #cbd5e1;
            padding: 0.15rem 0.55rem;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _add_deadline_item(
    course: str,
    summary: str,
    deadline_str: str,
    submission_format: str = "Moodle",
    description: str = "",
) -> bool:
    """Thêm một hạn nộp mới vào danh sách theo dõi nếu chưa trùng lặp."""
    for existing in st.session_state.deadlines:
        if (
            existing["course"].lower() == course.lower()
            and existing["summary"].lower() == summary.lower()
        ):
            existing["deadline"] = deadline_str
            existing["submission_format"] = submission_format
            existing["description"] = description
            return False

    new_id = f"dl-{int(time.time() * 1000)}-{len(st.session_state.deadlines)}"
    st.session_state.deadlines.insert(
        0,
        {
            "id": new_id,
            "course": course,
            "summary": summary,
            "deadline": deadline_str,
            "submission_format": submission_format,
            "description": description,
            "done": False,
        },
    )
    return True


def main() -> None:
    st.set_page_config(
        page_title="H.E.R.M.E.S — Cố vấn Học vụ & Lịch trình Sinh viên HCMUS",
        page_icon="🎓",
        layout="wide",
    )
    _inject_clean_styles()

    # Khởi tạo trạng thái dữ liệu của sinh viên
    if "gpa_courses" not in st.session_state:
        st.session_state.gpa_courses = [
            {"name": "Giải tích 1", "credits": 4, "grade": 8.5},
            {"name": "Cấu trúc Dữ liệu & Giải thuật", "credits": 4, "grade": 7.5},
            {"name": "Tư duy Tính toán", "credits": 3, "grade": 9.0},
        ]

    if "exam_subjects" not in st.session_state:
        st.session_state.exam_subjects = [
            {"name": "Toán Rời Rạc", "credits": 4, "priority": 3},
            {"name": "Cấu trúc Dữ liệu & Giải thuật", "credits": 4, "priority": 2},
            {"name": "Kiến trúc Máy tính", "credits": 3, "priority": 1},
        ]

    if "deadlines" not in st.session_state:
        st.session_state.deadlines = _build_default_deadlines()

    if "queued_chat_prompt" not in st.session_state:
        st.session_state.queued_chat_prompt = None

    if "last_Extracted_announcement" not in st.session_state:
        st.session_state.last_extracted_announcement = None

    # ==========================================
    # THANH BÊN (SIDEBAR): HỒ SƠ & BẢNG ĐIỂM NHANH
    # ==========================================
    with st.sidebar:
        st.markdown("### Hồ sơ Học tập của bạn")
        student_cohort = st.selectbox(
            "Khóa tuyển sinh",
            options=[
                "Khóa K24 (2024)",
                "Khóa K25 (2025)",
                "Khóa K23 (2023)",
                "Khóa K22 (2022)",
                "Khóa K21 (2021)",
                "Tự động nhận diện",
            ],
            index=0,
            help="H.E.R.M.E.S sẽ tự động đối chiếu quy chế và chuẩn ngoại ngữ theo đúng khóa của bạn.",
        )
        student_program = st.selectbox(
            "Chương trình đào tạo",
            options=[
                "Hệ Chuẩn (Đại trà)",
                "Tăng cường Tiếng Anh (CLC)",
                "Chương trình Tiên tiến (APCS)",
                "Cử nhân Tài năng",
                "Tự động nhận diện",
            ],
            index=0,
        )
        accum_tc = st.number_input(
            "Tín chỉ tích lũy các kỳ trước",
            min_value=0,
            max_value=200,
            value=30,
            step=1,
        )

        st.divider()
        st.markdown("### Bảng điểm Học kỳ hiện tại")

        with st.expander("➕ Thêm môn học vào bảng điểm", expanded=False):
            with st.form("sidebar_add_course", clear_on_submit=True):
                c_name = st.text_input("Tên môn học", placeholder="VD: Hệ điều hành")
                col_c1, col_c2 = st.columns(2)
                c_tc = col_c1.number_input("Số tín chỉ", 1, 10, 4)
                c_grade = col_c2.number_input("Điểm hệ 10", 0.0, 10.0, 8.0, step=0.1)
                if st.form_submit_button(
                    "Thêm vào bảng điểm", use_container_width=True
                ):
                    if c_name.strip():
                        st.session_state.gpa_courses.append(
                            {
                                "name": c_name.strip(),
                                "credits": int(c_tc),
                                "grade": float(c_grade),
                            }
                        )
                        st.rerun()

        # Tính toán GPA thời gian thực
        tuples = [(c["grade"], c["credits"]) for c in st.session_state.gpa_courses]
        gpa_10 = calculate_gpa_10(tuples) if tuples else 0.0
        gpa_4 = calculate_gpa_4(tuples) if tuples else 0.0
        earned_tc = sum(
            c["credits"] for c in st.session_state.gpa_courses if c["grade"] >= 5.0
        )
        total_sem_tc = sum(c["credits"] for c in st.session_state.gpa_courses)
        warn_info = (
            check_academic_warning(
                current_semester_earned_credits=earned_tc,
                accumulated_credits=int(accum_tc) + earned_tc,
                previous_semester_gpa=gpa_10,
                two_previous_semesters_gpa=gpa_10,
            )
            if tuples
            else {"is_warning": False, "status": "Chưa nhập môn", "reasons": []}
        )

        if st.session_state.gpa_courses:
            for idx, c in enumerate(st.session_state.gpa_courses):
                _, letter = convert_score_to_4_and_letter(c["grade"])
                row_c1, row_c2 = st.columns([5, 1])
                row_c1.markdown(
                    f"**{c['name']}**  \n`{c['grade']:.1f}` ({c['credits']} TC) → **{letter}**"
                )
                if row_c2.button("✕", key=f"del_course_{idx}", help="Xóa môn này"):
                    st.session_state.gpa_courses.pop(idx)
                    st.rerun()

            if st.button(
                "Nhờ Cố vấn phân tích bảng điểm này",
                use_container_width=True,
                type="primary",
            ):
                formatted_list = ", ".join(
                    f"{c['name']} ({c['grade']}, {c['credits']}TC)"
                    for c in st.session_state.gpa_courses
                )
                st.session_state.queued_chat_prompt = (
                    "Tính điểm GPA và tư vấn học vụ cho bảng điểm của mình: "
                    f"{formatted_list}"
                )
                st.rerun()
        else:
            st.caption("Chưa có môn học nào. Hãy bấm 'Thêm môn học' ở trên.")

        st.divider()
        show_tech_meta = st.toggle(
            "Hiển thị thông tin định tuyến (khi bảo vệ đồ án)",
            value=False,
            help=(
                "Bật khi thuyết trình để giảng viên thấy rõ Intent Router "
                "và Engine xử lý bên dưới mỗi câu trả lời."
            ),
        )

    # ==========================================
    # TÍNH TOÁN TRẠNG THÁI DEADLINE & THÔNG BÁO
    # ==========================================
    active_deadlines = [d for d in st.session_state.deadlines if not d.get("done")]
    urgent_deadlines = []
    for d in active_deadlines:
        st_info = compute_deadline_status(d["deadline"])
        d["_status"] = st_info
        if st_info["urgency"] in ("urgent", "overdue"):
            urgent_deadlines.append(d)

    cohort_code = (
        student_cohort.split()[1] if student_cohort.startswith("Khóa K") else "Tự động"
    )
    safety_label = (
        "Cần lưu ý (Điều 16)" if warn_info.get("is_warning") else "An toàn học vụ"
    )

    # ==========================================
    # THANH TIÊU ĐỀ TỔNG QUAN (CLEAN TOPBAR)
    # ==========================================
    st.markdown(
        f"""
        <div class="hermes-topbar">
            <div>
                <p class="hermes-brand-title">H.E.R.M.E.S — Cố vấn Học vụ & Lịch trình Sinh viên</p>
                <p class="hermes-brand-sub">
                    Trường Đại học Khoa học Tự nhiên, ĐHQG-HCM •
                    Hồ sơ đang chọn: <strong>{cohort_code} — {student_program}</strong>
                </p>
            </div>
            <div class="hermes-stat-group">
                <div class="hermes-stat-pill">
                    <div class="hermes-stat-label">GPA Học kỳ</div>
                    <div class="hermes-stat-value">{gpa_10:.2f}/10 ({gpa_4:.2f}/4)</div>
                </div>
                <div class="hermes-stat-pill">
                    <div class="hermes-stat-label">Trạng thái Học vụ</div>
                    <div class="hermes-stat-value">{safety_label}</div>
                </div>
                <div class="hermes-stat-pill">
                    <div class="hermes-stat-label">Nhiệm vụ & Hạn nộp</div>
                    <div class="hermes-stat-value">{len(active_deadlines)} đang mở ({len(urgent_deadlines)} gấp)</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Thanh thông báo nhắc hạn tự động nếu có bài tập sắp tới hạn
    if urgent_deadlines:
        nearest = urgent_deadlines[0]
        n_stat = nearest["_status"]
        ban_col1, ban_col2 = st.columns([4.2, 1.2])
        with ban_col1:
            st.markdown(
                f"""
                <div class="hermes-alert-banner">
                    <strong>Nhắc hạn nộp bài sắp tới:</strong> Bạn có
                    <strong>{len(urgent_deadlines)} nhiệm vụ</strong> cần hoàn thành sớm.
                    Gần nhất: <strong>{nearest['course']} — {nearest['summary']}</strong>
                    (Hạn chót: <code>{nearest['deadline']}</code> •
                    <strong>{n_stat['countdown_label']}</strong>).
                </div>
                """,
                unsafe_allow_html=True,
            )
        with ban_col2:
            if st.button(
                "🔔 Bật nhắc việc màn hình",
                use_container_width=True,
                help="Gửi thông báo nhắc hạn trực tiếp lên màn hình máy tính của bạn",
            ):
                _trigger_browser_notification(
                    title=f"Nhắc hạn H.E.R.M.E.S: {nearest['course']}",
                    body=f"{nearest['summary']} — Hạn nộp: {nearest['deadline']} ({n_stat['countdown_label']})",
                )
                st.toast(
                    f"Đã kích hoạt thông báo nhắc hạn: {nearest['summary']} ({n_stat['countdown_label']})",
                    icon="🔔",
                )

    # ==========================================
    # BA KHÔNG GIAN LÀM VIỆC CHÍNH CỦA SINH VIÊN
    # ==========================================
    tab_chat, tab_deadlines, tab_planner = st.tabs(
        [
            "💬 Trò chuyện với Cố vấn Học vụ",
            f"🔔 Quản lý Deadline & Thông báo Nhắc hẹn ({len(active_deadlines)})",
            "📅 Lập lịch Ôn thi (EDF) & Dự báo Điểm Mục tiêu",
        ]
    )

    # ------------------------------------------
    # TAB 1: TRÒ CHUYỆN CỐ VẤN HỌC VỤ
    # ------------------------------------------
    with tab_chat:
        q_cols = st.columns([1.2, 1.2, 1.2, 1.2, 0.8])
        quick_prompt = None
        if q_cols[0].button("Chuẩn ngoại ngữ theo ngành", use_container_width=True):
            quick_prompt = (
                "Chuẩn đầu ra ngoại ngữ chương trình tăng cường tiếng Anh "
                "ngành Công nghệ thông tin là gì?"
            )
        if q_cols[1].button("Quy định vắng học Anh văn", use_container_width=True):
            quick_prompt = "Sinh viên vắng quá 3 buổi học Anh văn sẽ bị xử lý điểm quá trình thế nào?"
        if q_cols[2].button("Bóc tách thông báo bài tập", use_container_width=True):
            quick_prompt = (
                "Thông báo: Môn học: Cơ sở dữ liệu. Bài tập: Đồ án thiết kế CSDL quản lý thư viện. "
                "Hạn nộp: 23:59 ngày 22/11/2026. Hình thức nộp: Qua Moodle (.zip)."
            )
        if q_cols[3].button("Lên kế hoạch ôn thi 7 ngày", use_container_width=True):
            quick_prompt = (
                "Xếp lịch ôn thi trong 7 ngày với 5 giờ mỗi ngày cho môn Giải tích 1, "
                "Cấu trúc dữ liệu và Hệ điều hành"
            )
        if q_cols[4].button("Làm mới cuộc trò chuyện", use_container_width=True):
            st.session_state.messages = [
                {
                    "role": "assistant",
                    "content": WELCOME_MESSAGE,
                    "meta": None,
                    "follow_ups": [
                        "Chuẩn đầu ra ngoại ngữ chương trình đại trà khóa 2024 là gì?",
                        "Tính điểm GPA và tư vấn học vụ giúp mình",
                        "Xếp lịch ôn thi tuần sau cho mình",
                    ],
                    "extracted_deadline_item": None,
                }
            ]
            st.rerun()

        if "messages" not in st.session_state or not st.session_state.messages:
            st.session_state.messages = [
                {
                    "role": "assistant",
                    "content": WELCOME_MESSAGE,
                    "meta": None,
                    "follow_ups": [
                        "Chuẩn đầu ra ngoại ngữ chương trình đại trà khóa 2024 là gì?",
                        "Tính điểm GPA và tư vấn học vụ giúp mình",
                        "Xếp lịch ôn thi tuần sau cho mình",
                    ],
                    "extracted_deadline_item": None,
                }
            ]

        # Hiển thị lịch sử tin nhắn
        for m_idx, message in enumerate(st.session_state.messages):
            avatar_icon = "🎓" if message["role"] == "assistant" else "🧑‍🎓"
            with st.chat_message(message["role"], avatar=avatar_icon):
                st.markdown(message["content"])
                if show_tech_meta and message.get("meta"):
                    st.caption(message["meta"])

                # Nếu tin nhắn vừa bóc tách được 1 deadline từ thông báo giảng viên, cho phép lưu 1-click
                dl_item = message.get("extracted_deadline_item")
                if dl_item and message["role"] == "assistant":
                    if st.button(
                        f"📌 Lưu hạn nộp môn {dl_item['course']} vào Bộ nhắc hạn & Thông báo",
                        key=f"save_dl_from_chat_{m_idx}",
                    ):
                        added = _add_deadline_item(
                            course=dl_item["course"],
                            summary=dl_item["summary"],
                            deadline_str=dl_item["deadline"],
                            submission_format="Theo thông báo",
                            description=dl_item.get("description", ""),
                        )
                        _trigger_browser_notification(
                            title=f"Đã bật nhắc hạn: {dl_item['course']}",
                            body=f"{dl_item['summary']} — Hạn chót: {dl_item['deadline']}",
                        )
                        if added:
                            st.toast(
                                f"Đã thêm '{dl_item['summary']}' vào danh sách nhắc hạn!",
                                icon="🔔",
                            )
                        else:
                            st.toast(
                                f"Đã cập nhật thời hạn cho '{dl_item['summary']}'!",
                                icon="✅",
                            )
                        st.rerun()

        # Hiển thị các câu hỏi gợi ý nối tiếp (Follow-up chips) dưới câu trả lời cuối cùng
        last_msg = st.session_state.messages[-1]
        follow_up_clicked = None
        if last_msg["role"] == "assistant" and last_msg.get("follow_ups"):
            st.caption("Gợi ý câu hỏi tiếp theo:")
            f_ups = last_msg["follow_ups"][:3]
            f_cols = st.columns(len(f_ups))
            for idx_f, f_text in enumerate(f_ups):
                if f_cols[idx_f].button(
                    f"↪ {f_text}",
                    key=f"followup_{len(st.session_state.messages)}_{idx_f}",
                    use_container_width=True,
                ):
                    follow_up_clicked = f_text

        chat_input_val = st.chat_input(
            "Nhập câu hỏi về quy chế, điểm số, lịch ôn thi hoặc dán thông báo của giảng viên..."
        )
        user_prompt = (
            chat_input_val
            or quick_prompt
            or follow_up_clicked
            or st.session_state.queued_chat_prompt
        )
        if st.session_state.queued_chat_prompt:
            st.session_state.queued_chat_prompt = None

        if user_prompt:
            with st.chat_message("user", avatar="🧑‍🎓"):
                st.markdown(user_prompt)
            st.session_state.messages.append(
                {"role": "user", "content": user_prompt, "meta": None}
            )

            # Tự động đính kèm ngữ cảnh Khóa/Hệ nếu người dùng hỏi quy chế mà chưa gõ khóa/hệ
            effective_query = user_prompt
            q_low = user_prompt.lower()
            has_cohort = any(
                k in q_low for k in ["k20", "k21", "k22", "k23", "k24", "k25", "202"]
            )
            has_prog = any(
                p in q_low
                for p in [
                    "tăng cường",
                    "chất lượng cao",
                    "clc",
                    "tiên tiến",
                    "apcs",
                    "đại trà",
                    "hệ chuẩn",
                    "tài năng",
                ]
            )
            if (
                not has_cohort
                and not has_prog
                and student_cohort != "Tự động nhận diện"
                and any(
                    kw in q_low
                    for kw in [
                        "ngoại ngữ",
                        "tiếng anh",
                        "toeic",
                        "ielts",
                        "vstep",
                        "chuẩn đầu ra",
                    ]
                )
            ):
                prog_hint = (
                    "đại trà"
                    if "Đại trà" in student_program
                    else (
                        "tăng cường tiếng Anh"
                        if "Tăng cường" in student_program
                        else (
                            "tiên tiến"
                            if "Tiên tiến" in student_program
                            else "cử nhân tài năng"
                        )
                    )
                )
                effective_query = f"{user_prompt} ({cohort_code} {prog_hint})"

            with st.chat_message("assistant", avatar="🎓"):
                res = orchestrate(effective_query)
                reply = res["response_text"]
                st.write_stream(_stream_markdown(reply))

                engine_label = res.get("target_engine", "orchestrator")
                intent_label = res.get("intent", "GENERAL")
                prov = res.get("provenance")
                meta_parts = [
                    f"Engine: `{engine_label}`",
                    f"Intent: `{intent_label}`",
                ]
                if prov:
                    meta_parts.append(f"Nguồn: {prov}")
                meta_text = " • ".join(meta_parts)
                if show_tech_meta:
                    st.caption(meta_text)

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": reply,
                    "meta": meta_text,
                    "follow_ups": res.get("data", {}).get("follow_ups", []),
                    "extracted_deadline_item": res.get("data", {}).get(
                        "extracted_deadline_item"
                    ),
                }
            )
            st.rerun()

    # ------------------------------------------
    # TAB 2: QUẢN LÝ DEADLINE & THÔNG BÁO NHẮC HẸN
    # ------------------------------------------
    with tab_deadlines:
        col_tracker, col_ingest = st.columns([1.25, 1])

        with col_tracker:
            st.subheader("🔔 Bảng Theo dõi Hạn nộp & Thông báo Nhắc việc")
            st.caption(
                "Tất cả hạn nộp bóc tách từ thông báo giảng viên hoặc lịch Moodle (.ics) "
                "được gom về đây, tự động đếm ngược và phát thông báo trước giờ khóa cổng nộp bài."
            )

            btn_bar1, btn_bar2, btn_bar3 = st.columns(3)
            if btn_bar1.button(
                "🔔 Gửi thông báo nhắc hạn ngay",
                use_container_width=True,
                help="Bắn thông báo đẩy lên màn hình máy tính cho hạn nộp gần nhất",
            ):
                if active_deadlines:
                    top_dl = active_deadlines[0]
                    top_st = compute_deadline_status(top_dl["deadline"])
                    _trigger_browser_notification(
                        title=f"Nhắc hạn: {top_dl['course']}",
                        body=(
                            f"{top_dl['summary']} — Hạn chót: "
                            f"{top_dl['deadline']} ({top_st['countdown_label']})"
                        ),
                    )
                    st.toast(
                        f"Đã gửi thông báo nhắc hạn: {top_dl['summary']} ({top_st['countdown_label']})",
                        icon="🔔",
                    )
                else:
                    st.toast("Bạn đã hoàn thành toàn bộ deadline!", icon="🎉")

            ics_export_str = export_deadlines_to_ics(active_deadlines)
            btn_bar2.download_button(
                label="📲 Tải lịch nhắc hẹn (.ics)",
                data=ics_export_str.encode("utf-8"),
                file_name="hermes_hcmus_deadlines.ics",
                mime="text/calendar",
                use_container_width=True,
                help=(
                    "File lịch chuẩn có sẵn chuông báo trước 24 giờ và 2 giờ "
                    "để mở bằng Google Calendar / Điện thoại"
                ),
            )

            if btn_bar3.button(
                "➡️ Đưa sang Kế hoạch Ôn tập",
                use_container_width=True,
                help="Tự động thêm các môn có bài tập sắp tới hạn vào bảng phân bổ giờ học",
            ):
                existing_names = {
                    s["name"].lower() for s in st.session_state.exam_subjects
                }
                added_count = 0
                for d in active_deadlines:
                    c_title = d["course"].split("-")[-1].strip()
                    if c_title.lower() not in existing_names:
                        st.session_state.exam_subjects.append(
                            {"name": c_title, "credits": 4, "priority": 3}
                        )
                        existing_names.add(c_title.lower())
                        added_count += 1
                st.toast(
                    f"Đã đồng bộ {added_count} môn học từ danh sách Deadline sang Lập lịch Ôn tập!",
                    icon="📅",
                )

            if not st.session_state.deadlines:
                st.info(
                    "Chưa có hạn nộp nào. Hãy dán thông báo của giảng viên "
                    "hoặc tải file .ics từ Moodle ở cột bên phải."
                )
            else:
                for idx_d, d_item in enumerate(st.session_state.deadlines):
                    st_info = compute_deadline_status(d_item["deadline"])
                    is_done = bool(d_item.get("done"))

                    if is_done:
                        badge_html = (
                            '<span class="hermes-badge-done">Đã hoàn thành</span>'
                        )
                    elif st_info["urgency"] in ("urgent", "overdue"):
                        badge_html = f'<span class="hermes-badge-urgent">{st_info["countdown_label"]}</span>'
                    elif st_info["urgency"] == "upcoming":
                        badge_html = f'<span class="hermes-badge-upcoming">{st_info["countdown_label"]}</span>'
                    else:
                        badge_html = f'<span class="hermes-badge-normal">{st_info["countdown_label"]}</span>'

                    dl_fmt = d_item.get("submission_format", "Moodle")
                    dl_desc = d_item.get("description", "")
                    with st.container():
                        st.markdown(
                            f"""
                            <div class="hermes-dl-card">
                                <div style="display:flex; justify-content:space-between; gap:0.5rem;">
                                    <div>
                                        <div style="font-size:0.8rem; font-weight:600; color:#1e3a8a;">
                                            {d_item['course']}
                                        </div>
                                        <div style="font-size:1rem; font-weight:700; color:#0f172a; margin:0.15rem 0;">
                                            {d_item['summary']}
                                        </div>
                                        <div style="font-size:0.84rem; color:#475569;">
                                            Hạn nộp: <code>{d_item['deadline']}</code> • Nơi nộp: {dl_fmt}
                                        </div>
                                        <div style="font-size:0.8rem; color:#64748b; margin-top:0.2rem;">
                                            {dl_desc}
                                        </div>
                                    </div>
                                    <div>{badge_html}</div>
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        act_c1, act_c2, _ = st.columns([1.4, 1.1, 2.5])
                        done_label = "↩ Mở lại" if is_done else "✓ Đánh dấu xong"
                        if act_c1.button(
                            done_label,
                            key=f"toggle_dl_{d_item['id']}_{idx_d}",
                            use_container_width=True,
                        ):
                            st.session_state.deadlines[idx_d]["done"] = not is_done
                            st.rerun()
                        if act_c2.button(
                            "Xóa",
                            key=f"remove_dl_{d_item['id']}_{idx_d}",
                            use_container_width=True,
                        ):
                            st.session_state.deadlines.pop(idx_d)
                            st.rerun()

        with col_ingest:
            st.subheader("📥 Thêm nhanh từ Thông báo hoặc Lịch Moodle")
            ingest_mode = st.radio(
                "Chọn nguồn dữ liệu đầu vào:",
                options=[
                    "Dán thông báo từ Giảng viên (Moodle / Email / Zalo)",
                    "Đồng bộ file lịch chuẩn từ Moodle (.ics)",
                ],
                horizontal=False,
            )

            if ingest_mode.startswith("Dán thông báo"):
                ai_mode = st.selectbox(
                    "Chế độ trích xuất",
                    options=["mock", "ollama"],
                    format_func=lambda m: (
                        "Trích xuất nhanh tức thì (Quy tắc + Kiểm chứng chống ảo giác)"
                        if m == "mock"
                        else "Mô hình ngôn ngữ cục bộ Ollama (qwen2.5:3b @ localhost:11434)"
                    ),
                )
                default_due = (datetime.now() + timedelta(days=2)).strftime("%d/%m/%Y")
                raw_ann = st.text_area(
                    "Nội dung thông báo của giảng viên:",
                    value=(
                        "Thông báo: Môn học: Mạng máy tính. "
                        "Bài tập: Đồ án lập trình Socket Client-Server. "
                        f"Hạn nộp: 23:59 ngày {default_due}. "
                        "Hình thức nộp: Qua Moodle (.zip). "
                        "Lưu ý: Đặt tên file theo MSSV và kèm file README hướng dẫn chạy."
                    ),
                    height=135,
                )
                if st.button(
                    "Bóc tách & Thêm vào Bộ nhắc hạn",
                    type="primary",
                    use_container_width=True,
                ):
                    try:
                        info = extract_announcement_info(raw_ann, mode=ai_mode)
                        dl_stat = compute_deadline_status(info.deadline)
                        normalized_dl = (
                            dl_stat["normalized_dt"]
                            if dl_stat["urgency"] != "unknown"
                            else info.deadline
                        )
                        _add_deadline_item(
                            course=info.course_name,
                            summary=info.assignment_content,
                            deadline_str=normalized_dl,
                            submission_format=info.submission_format,
                            description=info.other_requirements,
                        )
                        _trigger_browser_notification(
                            title=f"Đã lưu hạn nộp mới: {info.course_name}",
                            body=(
                                f"{info.assignment_content} — Hạn nộp: "
                                f"{normalized_dl} ({dl_stat['countdown_label']})"
                            ),
                        )
                        st.session_state.last_extracted_announcement = {
                            "course": info.course_name,
                            "assignment": info.assignment_content,
                            "deadline": normalized_dl,
                            "countdown": dl_stat["countdown_label"],
                            "format": info.submission_format,
                            "notes": info.other_requirements,
                        }
                        st.toast(
                            f"Đã thêm '{info.assignment_content}' vào Bảng nhắc hạn!",
                            icon="🔔",
                        )
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Không thể kết nối chế độ {ai_mode}: {exc}")

                if st.session_state.last_extracted_announcement:
                    ext = st.session_state.last_extracted_announcement
                    st.success(
                        f"Đã bóc tách & bật theo dõi: **{ext['course']}** ({ext['countdown']})"
                    )
                    st.markdown(
                        f"- **Nhiệm vụ:** {ext['assignment']}\n"
                        f"- **Hạn chót:** `{ext['deadline']}`\n"
                        f"- **Hình thức nộp:** {ext['format']}\n"
                        f"- **Lưu ý:** {ext['notes']}"
                    )
            else:
                uploaded_ics = st.file_uploader(
                    "Tải lên file lịch .ics xuất từ Moodle HCMUS", type=["ics"]
                )
                use_sample_ics = st.button(
                    "Nhập thử lịch mẫu từ Moodle HCMUS (2 bài tập sắp tới hạn)",
                    use_container_width=True,
                    type="primary",
                )

                ics_content = None
                if uploaded_ics is not None:
                    ics_content = uploaded_ics.read().decode("utf-8", errors="replace")
                elif use_sample_ics:
                    ics_content = _build_sample_ics()

                if ics_content:
                    events = parse_ics_deadlines(ics_content)
                    if events:
                        for ev in events:
                            _add_deadline_item(
                                course=ev["course"],
                                summary=ev["summary"],
                                deadline_str=ev["deadline"],
                                submission_format="Moodle (.ics)",
                                description=ev.get("description", ""),
                            )
                        _trigger_browser_notification(
                            title="Đồng bộ lịch Moodle thành công",
                            body=f"Đã thêm {len(events)} hạn nộp bài từ Moodle vào bộ nhắc hạn H.E.R.M.E.S.",
                        )
                        st.toast(
                            f"Đã đồng bộ {len(events)} sự kiện từ lịch Moodle vào Bảng nhắc hạn!",
                            icon="📅",
                        )
                        st.rerun()
                    else:
                        st.warning("Không tìm thấy sự kiện VEVENT nào trong file .ics.")

    # ------------------------------------------
    # TAB 3: LẬP LỊCH ÔN THI & DỰ BÁO GPA
    # ------------------------------------------
    with tab_planner:
        col_sched, col_whatif = st.columns([1.25, 1])

        with col_sched:
            st.subheader("🗓️ Phân bổ Quỹ thời gian Ôn thi (Thuật toán EDF)")
            st.caption(
                "Tự động chia nhỏ số giờ học mỗi ngày theo mức độ ưu tiên "
                "(sắp thi / môn khó) và trọng số tín chỉ để bạn không bị dồn bài sát ngày thi."
            )
            s_col1, s_col2 = st.columns(2)
            days_left = s_col1.slider("Số ngày còn lại trước kỳ thi", 1, 30, 10)
            daily_hours = s_col2.slider(
                "Quỹ thời gian tự học mỗi ngày (giờ)", 1.0, 12.0, 6.0, 0.5
            )

            with st.expander(
                "➕ Thêm hoặc chỉnh sửa danh sách môn ôn thi", expanded=False
            ):
                with st.form("add_exam_form", clear_on_submit=True):
                    ex_name = st.text_input(
                        "Tên môn thi", placeholder="VD: Hệ điều hành"
                    )
                    ex_c1, ex_c2 = st.columns(2)
                    ex_tc = ex_c1.number_input("Số tín chỉ", 1, 10, 4)
                    ex_prio = ex_c2.selectbox(
                        "Độ ưu tiên / Độ khó",
                        options=[3, 2, 1],
                        format_func=lambda x: (
                            "Mức 3 — Cao (Sắp thi / Môn khó)"
                            if x == 3
                            else ("Mức 2 — Trung bình" if x == 2 else "Mức 1 — Cơ bản")
                        ),
                    )
                    if st.form_submit_button(
                        "Thêm vào kế hoạch ôn tập", use_container_width=True
                    ):
                        if ex_name.strip():
                            st.session_state.exam_subjects.append(
                                {
                                    "name": ex_name.strip(),
                                    "credits": int(ex_tc),
                                    "priority": int(ex_prio),
                                }
                            )
                            st.rerun()

                if st.session_state.exam_subjects:
                    if st.button("Khôi phục 3 môn mặc định", use_container_width=True):
                        st.session_state.exam_subjects = [
                            {"name": "Toán Rời Rạc", "credits": 4, "priority": 3},
                            {
                                "name": "Cấu trúc Dữ liệu & Giải thuật",
                                "credits": 4,
                                "priority": 2,
                            },
                            {"name": "Kiến trúc Máy tính", "credits": 3, "priority": 1},
                        ]
                        st.rerun()

            plan_data = generate_study_plan(
                st.session_state.exam_subjects, daily_hours, days_left
            )
            if plan_data:
                prio_map = {
                    3: "Cao (Trọng tâm)",
                    2: "Trung bình",
                    1: "Cơ bản",
                }
                display_rows = [
                    {
                        "Học phần": p["name"],
                        "Số tín chỉ": f"{p['credits']} TC",
                        "Mức ưu tiên": prio_map.get(
                            p["priority"], f"Mức {p['priority']}"
                        ),
                        "Tổng giờ ôn tập": f"{p['allocated_hours']:g} giờ",
                        "Số giờ mỗi ngày": p["daily_hours"],
                    }
                    for p in plan_data
                ]
                st.dataframe(
                    display_rows,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Số giờ mỗi ngày": st.column_config.ProgressColumn(
                            "Thời lượng / ngày (giờ)",
                            help="Số giờ cần dành cho môn này mỗi ngày",
                            format="%.2f giờ/ngày",
                            min_value=0.0,
                            max_value=float(daily_hours),
                        )
                    },
                )

                total_tc_exam = sum(
                    s["credits"] for s in st.session_state.exam_subjects
                )
                total_hours_pool = daily_hours * days_left
                if total_hours_pool < total_tc_exam * 3:
                    st.warning(
                        f"**Cảnh báo quỹ thời gian mỏng:** Với {total_tc_exam} tín chỉ ôn thi "
                        f"nhưng chỉ có tổng cộng {total_hours_pool:g} giờ ôn tập, bạn nên tăng "
                        "thêm giờ học mỗi ngày hoặc kéo dài số ngày chuẩn bị."
                    )
                else:
                    st.success(
                        f"**Lộ trình cân đối:** Tổng quỹ thời gian **{total_hours_pool:g} giờ** "
                        f"trong {days_left} ngày hoàn toàn đủ để ôn sâu {len(plan_data)} môn "
                        "theo trọng số tín chỉ."
                    )

        with col_whatif:
            st.subheader("🎯 Dự báo Điểm Mục tiêu & Chiến lược Cải thiện")
            st.caption(
                "Dựa trên bảng điểm hiện tại của bạn ở thanh bên trái, tính mức điểm "
                "trung bình cần đạt ở học kỳ tới để chạm mốc GPA mong muốn."
            )

            w_col1, w_col2 = st.columns(2)
            target_gpa = w_col1.number_input(
                "GPA Hệ 10 mục tiêu",
                min_value=5.0,
                max_value=10.0,
                value=8.5,
                step=0.1,
            )
            rem_credits = w_col2.number_input(
                "Số tín chỉ đăng ký kỳ tới",
                min_value=1,
                max_value=30,
                value=12,
                step=1,
            )

            if st.session_state.gpa_courses:
                req_gpa = simulate_gpa(
                    st.session_state.gpa_courses, target_gpa, int(rem_credits)
                )
                st.markdown(
                    f"- **GPA hiện tại của bạn:** `{gpa_10:.2f}/10` (Tổng `{total_sem_tc} TC` đã nhập)\n"
                    f"- **Mục tiêu hướng tới:** `{target_gpa:.2f}/10` sau khi học thêm `{rem_credits} TC`"
                )

                if req_gpa > 10.0:
                    st.error(
                        f"**Chưa thể đạt ngay trong 1 kỳ:** Bạn cần đạt trung bình **{req_gpa:.2f}/10** "
                        f"trong {rem_credits} tín chỉ tới (vượt mức tối đa 10.0).\n\n"
                        "**Giải pháp thực tế:** Hãy tăng số tín chỉ tích lũy trong 2 học kỳ tới, "
                        "hoặc đăng ký **học cải thiện** các môn điểm thấp hiện có."
                    )
                elif req_gpa <= gpa_10:
                    st.success(
                        f"**Mục tiêu rất khả thi:** Bạn chỉ cần duy trì mức điểm trung bình "
                        f"từ **{max(req_gpa, 5.0):.2f}/10** cho **{rem_credits} tín chỉ** kỳ tới "
                        f"là giữ vững mốc GPA **{target_gpa:.2f}**."
                    )
                else:
                    st.info(
                        f"**Cần bứt phá ở kỳ tới:** Để kéo GPA từ `{gpa_10:.2f}` lên `{target_gpa:.2f}`, "
                        f"các môn trong **{rem_credits} tín chỉ** sắp tới cần đạt trung bình "
                        f"tối thiểu **{req_gpa:.2f}/10**."
                    )

                # Gợi ý môn học cải thiện cụ thể từ bảng điểm của sinh viên
                lowest_course = min(
                    st.session_state.gpa_courses, key=lambda c: c["grade"]
                )
                if lowest_course["grade"] < 8.0 and total_sem_tc > 0:
                    improved_courses = [
                        (
                            8.5 if c is lowest_course else c["grade"],
                            c["credits"],
                        )
                        for c in st.session_state.gpa_courses
                    ]
                    boosted_gpa = calculate_gpa_10(improved_courses)
                    gain = round(boosted_gpa - gpa_10, 2)
                    if gain > 0:
                        st.markdown(
                            "**Gợi ý học cải thiện hiệu quả nhất:** Trong bảng điểm hiện tại "
                            f"của bạn, môn **{lowest_course['name']}** (`{lowest_course['grade']:.1f}` "
                            f"điểm, `{lowest_course['credits']} TC`) đang kéo GPA xuống nhiều nhất. "
                            "Nếu học cải thiện môn này lên **8.5**, GPA hiện tại sẽ tăng ngay từ "
                            f"`{gpa_10:.2f}` lên **`{boosted_gpa:.2f}`** (+`{gain:.2f}` điểm)."
                        )
            else:
                st.info(
                    "Hãy thêm ít nhất 1 môn học ở bảng điểm bên thanh trái để sử dụng bộ mô phỏng GPA."
                )


if __name__ == "__main__":
    main()
