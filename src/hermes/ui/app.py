"""
Giao diện Web H.E.R.M.E.S — Cổng Cố vấn Học vụ & Quản lý Lịch trình Sinh viên HCMUS.
Thiết kế hiện đại, phân tách màu sắc theo từng khu vực chức năng (Color-Coded Zones),
giúp sinh viên nhìn vào biết ngay cần bấm ở đâu mà không bị rối mắt.
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
    """Khởi tạo danh sách hạn nộp mẫu sát thời điểm hiện tại để hiển thị đếm ngược."""
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
    "Chào bạn! Mình là **H.E.R.M.E.S** — trợ lý cố vấn học tập dành riêng cho "
    "sinh viên **ĐH Khoa học Tự nhiên (ĐHQG-HCM)**.\n\n"
    "Bạn đang thắc mắc về **chuẩn ngoại ngữ**, **quy chế đào tạo**, **cách tính GPA** "
    "hay muốn **tách lịch bài tập**? Hãy chọn nhanh một thẻ gợi ý bên dưới hoặc "
    "nhập câu hỏi vào ô chat nhé!"
)


def _stream_markdown(text: str) -> Iterator[str]:
    """Hiệu ứng gõ chữ mượt mà cho câu trả lời."""
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


def _inject_modern_styles() -> None:
    st.markdown(
        """
        <style>
        /* Tổng thể khoảng cách thoáng đãng, dễ thở */
        .block-container {
            padding-top: 1.4rem !important;
            padding-bottom: 2.5rem !important;
            max-width: 1180px !important;
        }

        /* Banner đầu mỗi khu vực có màu sắc nhận diện riêng */
        .zone-banner {
            border-radius: 14px;
            padding: 1.25rem 1.5rem;
            margin-bottom: 1.2rem;
            color: #ffffff;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
            box-shadow: 0 8px 20px -4px rgba(15, 23, 42, 0.12);
        }
        .zone-blue {
            background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%);
        }
        .zone-orange {
            background: linear-gradient(135deg, #9a3412 0%, #ea580c 100%);
        }
        .zone-green {
            background: linear-gradient(135deg, #065f46 0%, #059669 100%);
        }
        .zone-purple {
            background: linear-gradient(135deg, #4c1d95 0%, #7c3aed 100%);
        }
        .zone-title {
            font-size: 1.35rem;
            font-weight: 700;
            margin: 0;
            color: #ffffff !important;
        }
        .zone-desc {
            font-size: 0.9rem;
            margin: 0.25rem 0 0 0;
            color: rgba(255, 255, 255, 0.9) !important;
        }
        .zone-pill {
            background: rgba(255, 255, 255, 0.18);
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 999px;
            padding: 0.35rem 0.9rem;
            font-size: 0.82rem;
            font-weight: 600;
            color: #ffffff;
        }

        /* Thẻ chỉ số màu sắc hiện đại */
        .stat-card {
            border-radius: 12px;
            padding: 1rem 1.2rem;
            margin-bottom: 0.8rem;
            border: 1px solid transparent;
        }
        .stat-blue {
            background: #eff6ff;
            border-color: #bfdbfe;
            color: #1e3a8a;
        }
        .stat-green {
            background: #ecfdf5;
            border-color: #a7f3d0;
            color: #065f46;
        }
        .stat-amber {
            background: #fffbeb;
            border-color: #fde68a;
            color: #92400e;
        }
        .stat-purple {
            background: #f5f3ff;
            border-color: #ddd6fe;
            color: #4c1d95;
        }
        .stat-label {
            font-size: 0.76rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            opacity: 0.85;
        }
        .stat-val {
            font-size: 1.4rem;
            font-weight: 800;
            margin-top: 0.15rem;
        }
        .stat-sub {
            font-size: 0.8rem;
            margin-top: 0.15rem;
            opacity: 0.9;
        }

        /* Thẻ hướng dẫn bước (Step guide) giúp người dùng biết ấn ở đâu */
        .step-box {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 0.75rem 1rem;
            margin-bottom: 1rem;
            font-size: 0.88rem;
            color: #334155;
        }
        .step-num {
            display: inline-block;
            background: #2563eb;
            color: #ffffff;
            font-weight: 700;
            font-size: 0.75rem;
            padding: 0.1rem 0.5rem;
            border-radius: 999px;
            margin-right: 0.35rem;
        }

        /* Thẻ Deadline có vạch màu bên trái theo độ khẩn cấp */
        .dl-item-urgent {
            background: #fff5f5;
            border: 1px solid #fecaca;
            border-left: 5px solid #ef4444;
            border-radius: 10px;
            padding: 0.9rem 1.1rem;
            margin-bottom: 0.5rem;
        }
        .dl-item-upcoming {
            background: #fffbeb;
            border: 1px solid #fde68a;
            border-left: 5px solid #f59e0b;
            border-radius: 10px;
            padding: 0.9rem 1.1rem;
            margin-bottom: 0.5rem;
        }
        .dl-item-normal {
            background: #f0fdf4;
            border: 1px solid #bbf7d0;
            border-left: 5px solid #10b981;
            border-radius: 10px;
            padding: 0.9rem 1.1rem;
            margin-bottom: 0.5rem;
        }
        .dl-item-done {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-left: 5px solid #94a3b8;
            border-radius: 10px;
            padding: 0.9rem 1.1rem;
            margin-bottom: 0.5rem;
            opacity: 0.75;
        }
        .dl-tag {
            display: inline-block;
            padding: 0.18rem 0.65rem;
            border-radius: 999px;
            font-size: 0.76rem;
            font-weight: 700;
        }
        .dl-tag-urgent { background: #fee2e2; color: #b91c1c; }
        .dl-tag-upcoming { background: #fef3c7; color: #b45309; }
        .dl-tag-normal { background: #dcfce7; color: #15803d; }
        .dl-tag-done { background: #e2e8f0; color: #475569; }
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
    """Thêm hoặc cập nhật một hạn nộp vào danh sách theo dõi."""
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
    _inject_modern_styles()

    # Khởi tạo dữ liệu phiên làm việc
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

    if "last_extracted_announcement" not in st.session_state:
        st.session_state.last_extracted_announcement = None

    if "accum_tc" not in st.session_state:
        st.session_state.accum_tc = 30

    # Tính toán các chỉ số tổng quan
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
            accumulated_credits=int(st.session_state.accum_tc) + earned_tc,
            previous_semester_gpa=gpa_10,
            two_previous_semesters_gpa=gpa_10,
        )
        if tuples
        else {"is_warning": False, "status": "Chưa nhập môn", "reasons": []}
    )

    active_deadlines = [d for d in st.session_state.deadlines if not d.get("done")]
    urgent_deadlines = []
    for d in active_deadlines:
        st_info = compute_deadline_status(d["deadline"])
        d["_status"] = st_info
        if st_info["urgency"] in ("urgent", "overdue"):
            urgent_deadlines.append(d)

    # ==========================================
    # THANH BÊN (SIDEBAR): GỌN GÀNG, CHỈ GIỮ HỒ SƠ & NHẮC VIỆC KHẨN
    # ==========================================
    with st.sidebar:
        st.markdown(
            """
            <div style="background:linear-gradient(135deg,#1e3a8a,#2563eb);
                        padding:1rem 1.1rem;border-radius:12px;color:#fff;margin-bottom:1rem;">
                <div style="font-size:1.15rem;font-weight:800;letter-spacing:0.02em;">🎓 H.E.R.M.E.S</div>
                <div style="font-size:0.8rem;opacity:0.9;margin-top:0.15rem;">Cố vấn Học vụ & Lịch trình HCMUS</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("##### 1. Hồ sơ Sinh viên đang áp dụng")
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

        st.divider()
        st.markdown("##### 2. Tóm tắt Nhắc hạn & Học lực")
        st.markdown(
            f"""
            <div class="stat-card stat-blue" style="padding:0.75rem 0.95rem;">
                <div class="stat-label">Điểm GPA Hiện tại</div>
                <div class="stat-val" style="font-size:1.2rem;">{gpa_10:.2f}/10 • {gpa_4:.2f}/4.0</div>
                <div class="stat-sub">{total_sem_tc} tín chỉ trong học kỳ</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if urgent_deadlines:
            nearest = urgent_deadlines[0]
            n_stat = nearest["_status"]
            st.markdown(
                f"""
                <div class="stat-card stat-amber" style="padding:0.75rem 0.95rem;">
                    <div class="stat-label">🔔 Sắp hết hạn nộp ({len(urgent_deadlines)} bài)</div>
                    <div style="font-weight:700;font-size:0.9rem;margin-top:0.2rem;">{nearest['course']}</div>
                    <div class="stat-sub">{nearest['summary']}</div>
                    <div style="font-weight:700;font-size:0.82rem;margin-top:0.25rem;color:#b91c1c;">
                        ⏰ {n_stat['countdown_label']}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(
                "🔔 Bắn thông báo lên màn hình",
                use_container_width=True,
                type="primary",
            ):
                _trigger_browser_notification(
                    title=f"Nhắc hạn H.E.R.M.E.S: {nearest['course']}",
                    body=(
                        f"{nearest['summary']} — Hạn nộp: "
                        f"{nearest['deadline']} ({n_stat['countdown_label']})"
                    ),
                )
                st.toast(
                    f"Đã gửi thông báo: {nearest['summary']} ({n_stat['countdown_label']})",
                    icon="🔔",
                )

        st.divider()
        show_tech_meta = st.toggle(
            "Chế độ Thuyết trình (Hiện Router/Engine)",
            value=False,
            help="Bật khi vấn đáp để hiển thị tên Intent và Engine bên dưới câu trả lời.",
        )

    cohort_code = (
        student_cohort.split()[1] if student_cohort.startswith("Khóa K") else "Tự động"
    )

    # ==========================================
    # 4 TAB CHỨC NĂNG RÕ RÀNG, MỖI MÀN HÌNH TẬP TRUNG 1 VIỆC
    # ==========================================
    tab_chat, tab_deadlines, tab_gpa, tab_planner = st.tabs(
        [
            "🟦 1. Hỏi Cố vấn & Quy chế (Chat)",
            f"🟧 2. Bóc tách Lịch & Nhắc hạn ({len(active_deadlines)})",
            f"🟩 3. Bảng điểm & Dự báo GPA ({gpa_10:.2f})",
            "🟪 4. Lập lịch Ôn thi Tự động (EDF)",
        ]
    )

    # =========================================================================
    # KHU VỰC 1 (MÀU XANH DƯƠNG): HỎI CỐ VẤN HỌC VỤ & TRA CỨU QUY CHẾ
    # =========================================================================
    with tab_chat:
        st.markdown(
            f"""
            <div class="zone-banner zone-blue">
                <div>
                    <p class="zone-title">💬 Trò chuyện với Cố vấn Học vụ H.E.R.M.E.S</p>
                    <p class="zone-desc">
                        Giải đáp trực tiếp Quy chế đào tạo, Chuẩn ngoại ngữ (K21–K25),
                        tính GPA và bóc tách thông báo bài tập.
                    </p>
                </div>
                <div class="zone-pill">Hồ sơ: {cohort_code} • {student_program}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Thanh bấm nhanh gọn gàng: hướng dẫn rõ ấn vào đâu để làm gì
        st.markdown(
            """
            <div class="step-box">
                <span class="step-num">Cách dùng nhanh</span>
                Bấm vào <strong>1 trong 4 nút tình huống mẫu</strong> bên dưới để thử ngay,
                hoặc gõ trực tiếp câu hỏi của bạn vào khung nhập tin nhắn ở cuối trang.
            </div>
            """,
            unsafe_allow_html=True,
        )

        q_cols = st.columns([1.2, 1.2, 1.2, 1.2, 0.7])
        quick_prompt = None
        if q_cols[0].button("🇬🇧 Hỏi Chuẩn Ngoại ngữ", use_container_width=True):
            quick_prompt = (
                "Chuẩn đầu ra ngoại ngữ chương trình tăng cường tiếng Anh "
                "ngành Công nghệ thông tin là gì?"
            )
        if q_cols[1].button("📘 Quy định Vắng học Anh văn", use_container_width=True):
            quick_prompt = "Sinh viên vắng quá 3 buổi học Anh văn sẽ bị xử lý điểm quá trình thế nào?"
        if q_cols[2].button("🧮 Phân tích Điểm của mình", use_container_width=True):
            formatted_list = ", ".join(
                f"{c['name']} ({c['grade']}, {c['credits']}TC)"
                for c in st.session_state.gpa_courses
            )
            quick_prompt = (
                f"Tính điểm GPA giúp mình: {formatted_list}"
                if formatted_list
                else "Tính GPA giúp mình: Giải tích 1 (8.5, 4TC), Cấu trúc dữ liệu (7.5, 4TC)"
            )
        if q_cols[3].button("📥 Thử Bóc tách Thông báo", use_container_width=True):
            quick_prompt = (
                "Thông báo: Môn học: Cơ sở dữ liệu. Bài tập: Đồ án thiết kế CSDL quản lý thư viện. "
                "Hạn nộp: 23:59 ngày 22/11/2026. Hình thức nộp: Qua Moodle (.zip)."
            )
        if q_cols[4].button("🔄 Xóa chat", use_container_width=True):
            st.session_state.messages = [
                {
                    "role": "assistant",
                    "content": WELCOME_MESSAGE,
                    "meta": None,
                    "follow_ups": [
                        "Chuẩn đầu ra ngoại ngữ chương trình đại trà khóa 2024 là gì?",
                        "Sinh viên vắng quá mấy buổi học Anh văn thì bị mất điểm quá trình?",
                        "Xếp lịch ôn thi trong 7 ngày với 5 giờ mỗi ngày cho môn Giải tích và CTDL",
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
                        "Sinh viên vắng quá mấy buổi học Anh văn thì bị mất điểm quá trình?",
                        "Xếp lịch ôn thi trong 7 ngày với 5 giờ mỗi ngày cho môn Giải tích và CTDL",
                    ],
                    "extracted_deadline_item": None,
                }
            ]

        # Hiển thị các tin nhắn hội thoại
        for m_idx, message in enumerate(st.session_state.messages):
            avatar_icon = "🎓" if message["role"] == "assistant" else "🧑‍🎓"
            with st.chat_message(message["role"], avatar=avatar_icon):
                st.markdown(message["content"])
                if show_tech_meta and message.get("meta"):
                    st.caption(message["meta"])

                dl_item = message.get("extracted_deadline_item")
                if dl_item and message["role"] == "assistant":
                    if st.button(
                        f"📌 Bấm vào đây để lưu hạn nộp '{dl_item['course']}' vào Bộ Nhắc Hạn",
                        key=f"save_dl_from_chat_{m_idx}",
                        type="primary",
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
                        msg_toast = (
                            f"Đã thêm '{dl_item['summary']}' vào Tab 2 (Bóc tách Lịch & Nhắc hạn)!"
                            if added
                            else f"Đã cập nhật thời hạn cho '{dl_item['summary']}'!"
                        )
                        st.toast(msg_toast, icon="🔔")
                        st.rerun()

        # Gợi ý câu hỏi nối tiếp dưới tin nhắn cuối
        last_msg = st.session_state.messages[-1]
        follow_up_clicked = None
        if last_msg["role"] == "assistant" and last_msg.get("follow_ups"):
            st.caption("💡 Bấm chọn nhanh câu hỏi liên quan tiếp theo:")
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
            "Gõ câu hỏi tại đây (VD: TOEIC ngành CNTT cần bao nhiêu điểm? Hoặc dán thông báo bài tập)..."
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

    # =========================================================================
    # KHU VỰC 2 (MÀU CAM): BÓC TÁCH LỊCH & TRUNG TÂM THÔNG BÁO DEADLINE
    # =========================================================================
    with tab_deadlines:
        st.markdown(
            f"""
            <div class="zone-banner zone-orange">
                <div>
                    <p class="zone-title">🔔 Bóc tách Lịch trình & Thông báo Nhắc hạn Deadline</p>
                    <p class="zone-desc">
                        Biến thông báo bài tập trên Moodle/Zalo/Email thành bộ đếm ngược tự động,
                        bắn thông báo lên màn hình và xuất file lịch có chuông báo.
                    </p>
                </div>
                <div class="zone-pill">
                    {len(active_deadlines)} hạn nộp đang theo dõi ({len(urgent_deadlines)} gấp)
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="step-box">
                <span class="step-num" style="background:#ea580c;">Bước 1 (Cột Trái)</span>
                Dán thông báo của giảng viên hoặc tải file <code>.ics</code> từ Moodle rồi ấn nút màu đỏ.
                &nbsp;&nbsp;➔&nbsp;&nbsp;
                <span class="step-num" style="background:#ea580c;">Bước 2 (Cột Phải)</span>
                Xem đếm ngược, ấn <strong>Bắn thông báo màn hình</strong> hoặc
                <strong>Tải lịch có chuông (.ics)</strong>.
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_ingest, col_tracker = st.columns([1, 1.25], gap="large")

        with col_ingest:
            st.markdown("#### 📥 Bước 1: Nhập Thông báo hoặc Lịch Moodle")
            ingest_mode = st.radio(
                "Chọn cách thêm lịch nộp bài:",
                options=[
                    "📝 Dán chữ từ thông báo của Giảng viên (Moodle / Zalo / Email)",
                    "📆 Tải file lịch chuẩn (.ics) xuất từ Moodle HCMUS",
                ],
                horizontal=False,
            )

            if ingest_mode.startswith("📝"):
                ai_mode = st.selectbox(
                    "Bộ xử lý trích xuất:",
                    options=["mock", "ollama"],
                    format_func=lambda m: (
                        "⚡ Bóc tách tức thì (Rule-based + Chống ảo giác)"
                        if m == "mock"
                        else "🤖 Mô hình AI Cục bộ Ollama (qwen2.5:3b)"
                    ),
                )
                default_due = (datetime.now() + timedelta(days=2)).strftime("%d/%m/%Y")
                raw_ann = st.text_area(
                    "Dán nội dung thông báo bài tập vào ô dưới đây:",
                    value=(
                        "Thông báo: Môn học: Mạng máy tính. "
                        "Bài tập: Đồ án lập trình Socket Client-Server. "
                        f"Hạn nộp: 23:59 ngày {default_due}. "
                        "Hình thức nộp: Qua Moodle (.zip). "
                        "Lưu ý: Đặt tên file theo MSSV và kèm file README."
                    ),
                    height=140,
                )
                if st.button(
                    "🔍 Bóc tách & Bật thông báo nhắc hạn ngay",
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
                            f"Đã thêm '{info.assignment_content}' vào danh sách đếm ngược bên phải!",
                            icon="🔔",
                        )
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Không thể kết nối bộ trích xuất ({ai_mode}): {exc}")

                if st.session_state.last_extracted_announcement:
                    ext = st.session_state.last_extracted_announcement
                    st.success(
                        f"✅ Đã bóc tách thành công môn **{ext['course']}** ({ext['countdown']})"
                    )
                    st.markdown(
                        f"- **Nhiệm vụ:** {ext['assignment']}\n"
                        f"- **Hạn chót:** `{ext['deadline']}`\n"
                        f"- **Nơi nộp:** {ext['format']}\n"
                        f"- **Lưu ý:** {ext['notes']}"
                    )
            else:
                uploaded_ics = st.file_uploader(
                    "Chọn file .ics từ máy tính của bạn:", type=["ics"]
                )
                use_sample_ics = st.button(
                    "📂 Bấm vào đây để nạp thử file .ics mẫu từ Moodle HCMUS",
                    type="primary",
                    use_container_width=True,
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
                            body=f"Đã thêm {len(events)} hạn nộp bài vào bộ nhắc hạn H.E.R.M.E.S.",
                        )
                        st.toast(
                            f"Đã đồng bộ {len(events)} bài tập từ Moodle sang cột bên phải!",
                            icon="📅",
                        )
                        st.rerun()
                    else:
                        st.warning("Không tìm thấy sự kiện VEVENT nào trong file .ics.")

        with col_tracker:
            st.markdown("#### 🔔 Bước 2: Danh sách Đếm ngược & Cài đặt Chuông báo")

            btn_bar1, btn_bar2, btn_bar3 = st.columns(3)
            if btn_bar1.button(
                "🔔 Bắn thông báo đẩy",
                use_container_width=True,
                help="Hiển thị thông báo nhắc việc trên góc màn hình máy tính",
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
                        f"Đã bắn thông báo: {top_dl['summary']} ({top_st['countdown_label']})",
                        icon="🔔",
                    )
                else:
                    st.toast("Bạn đã hoàn thành toàn bộ deadline!", icon="🎉")

            ics_export_str = export_deadlines_to_ics(active_deadlines)
            btn_bar2.download_button(
                label="📲 Tải lịch (.ics) có chuông",
                data=ics_export_str.encode("utf-8"),
                file_name="hermes_hcmus_deadlines.ics",
                mime="text/calendar",
                use_container_width=True,
                help="Mở file này trên Điện thoại hoặc Google Calendar để tự động kêu chuông trước 24h và 2h",
            )

            if btn_bar3.button(
                "➡️ Đưa sang Lịch Ôn tập",
                use_container_width=True,
                help="Chuyển các môn có deadline này sang Tab 4 để chia giờ học",
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
                    f"Đã chuyển {added_count} môn sang Tab 4 (Lập lịch Ôn thi EDF)!",
                    icon="🟪",
                )

            for idx_d, d_item in enumerate(st.session_state.deadlines):
                st_info = compute_deadline_status(d_item["deadline"])
                is_done = bool(d_item.get("done"))

                if is_done:
                    card_cls = "dl-item-done"
                    tag_html = '<span class="dl-tag dl-tag-done">✓ Đã hoàn thành</span>'
                elif st_info["urgency"] in ("urgent", "overdue"):
                    card_cls = "dl-item-urgent"
                    tag_html = (
                        f'<span class="dl-tag dl-tag-urgent">'
                        f'🔥 {st_info["countdown_label"]}</span>'
                    )
                elif st_info["urgency"] == "upcoming":
                    card_cls = "dl-item-upcoming"
                    tag_html = (
                        f'<span class="dl-tag dl-tag-upcoming">'
                        f'⏳ {st_info["countdown_label"]}</span>'
                    )
                else:
                    card_cls = "dl-item-normal"
                    tag_html = (
                        f'<span class="dl-tag dl-tag-normal">'
                        f'📅 {st_info["countdown_label"]}</span>'
                    )

                dl_fmt = d_item.get("submission_format", "Moodle")
                dl_desc = d_item.get("description", "")
                st.markdown(
                    f"""
                    <div class="{card_cls}">
                        <div style="display:flex; justify-content:space-between; gap:0.5rem;">
                            <div>
                                <div style="font-size:0.78rem; font-weight:700; color:#475569;">
                                    {d_item['course']}
                                </div>
                                <div style="font-size:1rem; font-weight:700; color:#0f172a; margin:0.15rem 0;">
                                    {d_item['summary']}
                                </div>
                                <div style="font-size:0.84rem; color:#334155;">
                                    ⏰ Hạn chót: <strong>{d_item['deadline']}</strong> • 📤 Nơi nộp: {dl_fmt}
                                </div>
                                <div style="font-size:0.8rem; color:#64748b; margin-top:0.15rem;">
                                    {dl_desc}
                                </div>
                            </div>
                            <div>{tag_html}</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                act_c1, act_c2, _ = st.columns([1.3, 0.9, 2.8])
                done_label = "↩ Mở lại" if is_done else "✓ Đánh dấu xong"
                if act_c1.button(
                    done_label,
                    key=f"toggle_dl_{d_item['id']}_{idx_d}",
                    use_container_width=True,
                ):
                    st.session_state.deadlines[idx_d]["done"] = not is_done
                    st.rerun()
                if act_c2.button(
                    "🗑️ Xóa",
                    key=f"remove_dl_{d_item['id']}_{idx_d}",
                    use_container_width=True,
                ):
                    st.session_state.deadlines.pop(idx_d)
                    st.rerun()

    # =========================================================================
    # KHU VỰC 3 (MÀU XANH NGỌC): BẢNG ĐIỂM CÁ NHÂN & DỰ BÁO GPA MỤC TIÊU
    # =========================================================================
    with tab_gpa:
        st.markdown(
            f"""
            <div class="zone-banner zone-green">
                <div>
                    <p class="zone-title">📊 Bảng điểm Học kỳ, Kiểm tra Cảnh báo & Dự báo GPA (What-If)</p>
                    <p class="zone-desc">
                        Quy đổi chính xác thang điểm 10 sang thang 4 theo Quyết định 1175/QĐ-KHTN,
                        kiểm tra an toàn Điều 16 và gợi ý môn nên học cải thiện.
                    </p>
                </div>
                <div class="zone-pill">GPA Hiện tại: {gpa_10:.2f}/10 ({gpa_4:.2f}/4.0)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # 3 thẻ màu sắc nổi bật ở đầu khu vực GPA
        safety_text = (
            "Nguy cơ Cảnh báo (Điều 16)"
            if warn_info.get("is_warning")
            else "An toàn Học vụ (Bình thường)"
        )
        m1, m2, m3 = st.columns(3)
        with m1:
            st.markdown(
                f"""
                <div class="stat-card stat-blue">
                    <div class="stat-label">Điểm Trung bình Hệ 10</div>
                    <div class="stat-val">{gpa_10:.2f} / 10.0</div>
                    <div class="stat-sub">
                        Tổng cộng {len(st.session_state.gpa_courses)} môn ({total_sem_tc} tín chỉ)
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with m2:
            st.markdown(
                f"""
                <div class="stat-card stat-purple">
                    <div class="stat-label">Điểm Trung bình Hệ 4 (Chuẩn QĐ 1175)</div>
                    <div class="stat-val">{gpa_4:.2f} / 4.0</div>
                    <div class="stat-sub">Tín chỉ tích lũy đạt trong kỳ: {earned_tc}/{total_sem_tc} TC</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with m3:
            card_color_cls = (
                "stat-amber" if warn_info.get("is_warning") else "stat-green"
            )
            total_acc_tc = int(st.session_state.accum_tc) + earned_tc
            st.markdown(
                f"""
                <div class="stat-card {card_color_cls}">
                    <div class="stat-label">Trạng thái Học vụ (Điều 16)</div>
                    <div class="stat-val" style="font-size:1.2rem;">{safety_text}</div>
                    <div class="stat-sub">Tổng tích lũy toàn khóa: {total_acc_tc} TC</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        col_courses, col_whatif = st.columns([1.15, 1], gap="large")

        with col_courses:
            st.markdown("#### 📋 Bước 1: Danh sách Môn học & Điểm của bạn")
            with st.form("add_course_main_form", clear_on_submit=True):
                f_c1, f_c2, f_c3, f_c4 = st.columns([2.2, 1, 1.1, 1.1])
                c_name = f_c1.text_input("Tên môn học", placeholder="VD: Hệ điều hành")
                c_tc = f_c2.number_input("Số TC", 1, 10, 4)
                c_grade = f_c3.number_input("Điểm hệ 10", 0.0, 10.0, 8.0, step=0.1)
                f_c4.markdown(
                    "<div style='height:1.72rem;'></div>", unsafe_allow_html=True
                )
                if f_c4.form_submit_button("➕ Thêm môn", use_container_width=True):
                    if c_name.strip():
                        st.session_state.gpa_courses.append(
                            {
                                "name": c_name.strip(),
                                "credits": int(c_tc),
                                "grade": float(c_grade),
                            }
                        )
                        st.rerun()

            if st.session_state.gpa_courses:
                course_table = []
                for c in st.session_state.gpa_courses:
                    s4, letter = convert_score_to_4_and_letter(c["grade"])
                    course_table.append(
                        {
                            "Môn học": c["name"],
                            "Số tín chỉ": f"{c['credits']} TC",
                            "Điểm Hệ 10": f"{c['grade']:.1f}",
                            "Điểm Hệ 4": f"{s4:.1f}",
                            "Điểm Chữ": letter,
                            "Kết quả": "Đạt" if c["grade"] >= 5.0 else "Học lại (F)",
                        }
                    )
                st.dataframe(course_table, use_container_width=True, hide_index=True)

                b_del1, b_del2 = st.columns(2)
                if b_del1.button(
                    "🗑️ Xóa môn cuối cùng vừa thêm", use_container_width=True
                ):
                    st.session_state.gpa_courses.pop()
                    st.rerun()
                if b_del2.button(
                    "🔄 Khôi phục bảng điểm mẫu", use_container_width=True
                ):
                    st.session_state.gpa_courses = [
                        {"name": "Giải tích 1", "credits": 4, "grade": 8.5},
                        {
                            "name": "Cấu trúc Dữ liệu & Giải thuật",
                            "credits": 4,
                            "grade": 7.5,
                        },
                        {"name": "Tư duy Tính toán", "credits": 3, "grade": 9.0},
                    ]
                    st.rerun()

        with col_whatif:
            st.markdown("#### 🎯 Bước 2: Dự báo Điểm Mục tiêu & Gợi ý Cải thiện")
            w_col1, w_col2 = st.columns(2)
            target_gpa = w_col1.number_input(
                "GPA Hệ 10 bạn muốn đạt:",
                min_value=5.0,
                max_value=10.0,
                value=8.5,
                step=0.1,
            )
            rem_credits = w_col2.number_input(
                "Số tín chỉ đăng ký kỳ tới:",
                min_value=1,
                max_value=30,
                value=12,
                step=1,
            )

            if st.session_state.gpa_courses:
                req_gpa = simulate_gpa(
                    st.session_state.gpa_courses, target_gpa, int(rem_credits)
                )
                if req_gpa > 10.0:
                    st.error(
                        f"**Cần lộ trình dài hơn 1 học kỳ:** Để nhảy từ `{gpa_10:.2f}` lên `{target_gpa:.2f}` "
                        f"chỉ trong {rem_credits} tín chỉ tới, bạn cần đạt trung bình "
                        f"**{req_gpa:.2f}/10** (vượt mức tối đa 10.0).\n\n"
                        "👉 **Cách giải quyết:** Hãy tăng số tín chỉ đăng ký hoặc học cải thiện môn điểm thấp dưới đây!"
                    )
                elif req_gpa <= gpa_10:
                    st.success(
                        f"**Rất khả thi:** Bạn chỉ cần đạt trung bình từ **{max(req_gpa, 5.0):.2f}/10** "
                        f"cho **{rem_credits} tín chỉ** kỳ tới là giữ vững mục tiêu GPA **{target_gpa:.2f}**."
                    )
                else:
                    st.info(
                        f"**Mục tiêu kỳ tới:** Để kéo GPA từ `{gpa_10:.2f}` lên `{target_gpa:.2f}`, "
                        f"bạn cần đạt trung bình tối thiểu **{req_gpa:.2f}/10** "
                        f"trong **{rem_credits} tín chỉ** sắp tới."
                    )

                lowest_course = min(
                    st.session_state.gpa_courses, key=lambda c: c["grade"]
                )
                if lowest_course["grade"] < 8.5 and total_sem_tc > 0:
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
                        low_name = lowest_course["name"]
                        low_gr = lowest_course["grade"]
                        low_tc = lowest_course["credits"]
                        st.markdown(
                            f"""
                            <div class="stat-card stat-green" style="margin-top:0.8rem;">
                                <div class="stat-label">💡 Gợi ý Học cải thiện hiệu quả nhất</div>
                                <div style="font-size:0.92rem;margin-top:0.3rem;">
                                    Môn <strong>{low_name}</strong> (<code>{low_gr:.1f}</code> điểm,
                                    <code>{low_tc} TC</code>) đang kéo GPA của bạn xuống nhiều nhất.
                                    Nếu cải thiện môn này lên <strong>8.5</strong>, GPA sẽ tăng ngay từ
                                    <strong>{gpa_10:.2f}</strong> lên <strong>{boosted_gpa:.2f}</strong>
                                    (+{gain:.2f} điểm).
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

    # =========================================================================
    # KHU VỰC 4 (MÀU TÍM): LẬP LỊCH ÔN THI TỰ ĐỘNG (EDF SCHEDULER)
    # =========================================================================
    with tab_planner:
        st.markdown(
            """
            <div class="zone-banner zone-purple">
                <div>
                    <p class="zone-title">🗓️ Lập lịch Ôn thi Tự động theo Trọng số & Độ ưu tiên (Thuật toán EDF)</p>
                    <p class="zone-desc">
                        Chỉ cần kéo thanh trượt chọn số ngày còn lại và số giờ rảnh mỗi ngày,
                        hệ thống sẽ chia sẵn thời lượng ôn tập tối ưu cho từng môn.
                    </p>
                </div>
                <div class="zone-pill">Thuật toán Tất định EDF</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_ctrl, col_table = st.columns([1, 1.35], gap="large")

        with col_ctrl:
            st.markdown("#### ⚙️ Bước 1: Chọn Quỹ thời gian & Môn thi")
            days_left = st.slider("Số ngày còn lại trước kỳ thi:", 1, 30, 10)
            daily_hours = st.slider(
                "Số giờ tự học mỗi ngày của bạn:", 1.0, 12.0, 6.0, 0.5
            )

            with st.form("add_exam_form", clear_on_submit=True):
                ex_name = st.text_input(
                    "Thêm môn thi mới:", placeholder="VD: Mạng máy tính"
                )
                ex_c1, ex_c2 = st.columns(2)
                ex_tc = ex_c1.number_input("Số tín chỉ", 1, 10, 4)
                ex_prio = ex_c2.selectbox(
                    "Độ ưu tiên / Độ khó",
                    options=[3, 2, 1],
                    format_func=lambda x: (
                        "Mức 3 — Cao (Sắp thi / Khó)"
                        if x == 3
                        else ("Mức 2 — Trung bình" if x == 2 else "Mức 1 — Cơ bản")
                    ),
                )
                if st.form_submit_button(
                    "➕ Thêm vào danh sách môn thi", use_container_width=True
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

            if st.button("🔄 Khôi phục 3 môn thi mặc định", use_container_width=True):
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

        with col_table:
            st.markdown("#### 📅 Bước 2: Bảng Phân bổ Giờ học Hàng ngày dành cho bạn")
            plan_data = generate_study_plan(
                st.session_state.exam_subjects, daily_hours, days_left
            )
            if plan_data:
                prio_map = {
                    3: "🔥 Cao (Ôn buổi sáng)",
                    2: "⚡ Trung bình (Ôn chiều)",
                    1: "📘 Cơ bản (Ôn tối)",
                }
                display_rows = [
                    {
                        "Môn thi": p["name"],
                        "Tín chỉ": f"{p['credits']} TC",
                        "Thứ tự ưu tiên": prio_map.get(
                            p["priority"], f"Mức {p['priority']}"
                        ),
                        "Tổng giờ ôn": f"{p['allocated_hours']:g} giờ",
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
                            "Thời lượng học mỗi ngày",
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
                        f"**Cảnh báo quỹ thời gian mỏng:** Tổng cộng {total_hours_pool:g} giờ "
                        f"cho {total_tc_exam} tín chỉ là hơi gấp. Bạn nên kéo thanh trượt "
                        "bên trái để tăng số giờ học mỗi ngày nhé!"
                    )
                else:
                    st.success(
                        f"**Kế hoạch tối ưu:** Tổng quỹ thời gian **{total_hours_pool:g} giờ** "
                        f"trong **{days_left} ngày** đã được phân bổ cân đối cho "
                        f"**{len(plan_data)} môn thi**."
                    )


if __name__ == "__main__":
    main()
