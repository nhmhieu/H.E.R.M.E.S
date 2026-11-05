"""
Streamlit Web Dashboard for H.E.R.M.E.S (Role R6 - Member 5: Trần Quốc Tuấn).

Provides an interactive, student-friendly 3-tab interface + Sidebar Student Profile
& GPA Calculator connected to the H.E.R.M.E.S Orchestrator, Deterministic Engines,
Hierarchical RAG, and Local Ollama / Mock AI Extractor.
"""

from __future__ import annotations

import time
from typing import Iterator

import streamlit as st

from hermes.ai.client import extract_announcement_info
from hermes.engines.academic_calc import (
    calculate_gpa_4,
    calculate_gpa_10,
    check_academic_warning,
    convert_score_to_4_and_letter,
)
from hermes.engines.scheduler import generate_study_plan, simulate_gpa
from hermes.router.orchestrator import orchestrate

try:
    from hermes.engines.deadline_parser import parse_ics_deadlines
except ImportError:

    def parse_ics_deadlines(ics_content: str) -> list:
        return []


SAMPLE_ICS_CONTENT = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//HCMUS Moodle//NONSGML v1.0//EN
BEGIN:VEVENT
UID:event-101@moodle.hcmus.edu.vn
DTSTART:20261118T100000Z
DTEND:20261120T165900Z
SUMMARY:[CSC10014] Nộp Báo cáo Đồ án Tư duy Tính toán (H.E.R.M.E.S)
CATEGORIES:CSC10014 - Tư duy Tính toán
DESCRIPTION:Nộp file PDF báo cáo và link GitHub repository qua Moodle trước 23:59.
END:VEVENT
BEGIN:VEVENT
UID:event-102@moodle.hcmus.edu.vn
DTSTART:20261122T080000Z
DTEND:20261125T165900Z
SUMMARY:[CSC10004] Bài tập thực hành Cây đỏ đen (Red-Black Tree)
CATEGORIES:CSC10004 - Cấu trúc dữ liệu và Giải thuật
DESCRIPTION:Nộp mã nguồn C++ (.zip) không quá 5MB trên hệ thống Moodle.
END:VEVENT
END:VCALENDAR"""

WELCOME_MESSAGE = (
    "👋 **Xin chào! Mình là H.E.R.M.E.S – Cố vấn Học vụ Ảo của bạn tại Trường ĐH Khoa học Tự nhiên (ĐHQG-HCM).**\n\n"
    "Mình kết hợp **Thuật toán Tất định (Deterministic Math)**, **Tra cứu Quy chế Phân cấp (Hierarchical RAG)** "
    "và **Mô hình AI Cục bộ (Local Ollama)** để hỗ trợ bạn chính xác tuyệt đối mà không lo ảo giác số học:\n"
    "- 📖 **Hỏi đáp Sổ tay Sinh viên & Quy chế:** Chuẩn đầu ra ngoại ngữ (K21–K25), học cải thiện, cảnh báo học vụ...\n"
    "- 🧮 **Tính GPA Hệ 10 / Hệ 4 & Xếp loại học lực:** Quy đổi chuẩn Quyết định 1175/QĐ-KHTN.\n"
    "- 📅 **Lập lịch Ôn thi Tự động (EDF):** Phân bổ giờ học tối ưu theo hạn thi và độ khó.\n"
    "- 📥 **Bóc tách Deadline Bài tập:** Trích xuất thông báo giảng viên hoặc file lịch `.ics` từ Moodle.\n\n"
    "💡 *Bạn có thể bấm vào **4 nút gợi ý nhanh** bên dưới hoặc nhập trực tiếp câu hỏi của bạn vào ô trò chuyện nhé!*"
)


def _stream_markdown(text: str) -> Iterator[str]:
    """Hiệu ứng gõ chữ mượt mà (Typewriter Streaming) cho câu trả lời của trợ lý."""
    lines = text.split("\n")
    for idx, line in enumerate(lines):
        yield line + ("\n" if idx < len(lines) - 1 else "")
        time.sleep(0.018)


def _inject_custom_css() -> None:
    st.markdown(
        """
        <style>
        .hermes-hero {
            background: linear-gradient(135deg, #0b2545 0%, #134074 55%, #1d4ed8 100%);
            padding: 1.4rem 1.8rem;
            border-radius: 14px;
            color: #ffffff;
            margin-bottom: 1.2rem;
            box-shadow: 0 6px 20px rgba(11, 37, 69, 0.16);
        }
        .hermes-hero h1 {
            color: #ffffff !important;
            font-size: 1.75rem !important;
            font-weight: 700 !important;
            margin: 0 0 0.35rem 0 !important;
            padding: 0 !important;
        }
        .hermes-hero p {
            color: #dbeafe !important;
            font-size: 0.95rem !important;
            margin: 0 0 0.75rem 0 !important;
        }
        .hermes-badges {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
        }
        .hermes-badge {
            background: rgba(255, 255, 255, 0.14);
            border: 1px solid rgba(255, 255, 255, 0.25);
            color: #f8fafc;
            padding: 0.22rem 0.7rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 500;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="H.E.R.M.E.S - Cố vấn Học vụ Thông minh HCMUS",
        page_icon="🎓",
        layout="wide",
    )
    _inject_custom_css()

    st.markdown(
        """
        <div class="hermes-hero">
            <h1>🎓 H.E.R.M.E.S — Trợ lý & Cố vấn Học vụ Thông minh HCMUS</h1>
            <p>HCMUS Educational Resource & Mentoring Expert System • Khoa CNTT, Trường ĐH Khoa học Tự nhiên (ĐHQG-HCM)</p>
            <div class="hermes-badges">
                <span class="hermes-badge">🟢 Hybrid Architecture Ready</span>
                <span class="hermes-badge">📚 17 Văn bản Pháp quy HCMUS</span>
                <span class="hermes-badge">🛡️ 4-Layer Security Guardrails</span>
                <span class="hermes-badge">🤖 Local Ollama (qwen2.5:3b)</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if "gpa_courses" not in st.session_state:
        st.session_state.gpa_courses = [
            {"name": "Giải tích 1", "credits": 4, "grade": 8.5},
            {"name": "Cấu trúc Dữ liệu", "credits": 4, "grade": 7.5},
            {"name": "Tư duy Tính toán", "credits": 3, "grade": 9.0},
        ]

    if "exam_subjects" not in st.session_state:
        st.session_state.exam_subjects = [
            {"name": "Toán Rời Rạc", "credits": 4, "priority": 3},
            {"name": "Cấu Trúc Dữ Liệu", "credits": 4, "priority": 2},
            {"name": "Kiến Trúc Máy Tính", "credits": 3, "priority": 1},
        ]

    # ==========================================
    # GIAO DIỆN THANH BÊN (SIDEBAR)
    # ==========================================
    with st.sidebar:
        st.subheader("👤 Hồ sơ Sinh viên của bạn")
        student_cohort = st.selectbox(
            "Khóa tuyển sinh",
            options=["Tự động nhận diện", "Khóa K25", "Khóa K24", "Khóa K23", "Khóa K22", "Khóa K21"],
            index=2,
            help="Giúp H.E.R.M.E.S tự động ưu tiên đúng văn bản quy chế theo khóa của bạn.",
        )
        student_program = st.selectbox(
            "Chương trình đào tạo",
            options=[
                "Tự động nhận diện",
                "Hệ Chuẩn (Đại trà)",
                "Chương trình Tăng cường Tiếng Anh (CLC)",
                "Chương trình Tiên tiến (APCS)",
            ],
            index=1,
        )

        st.divider()
        st.subheader("📊 Bảng tính GPA & Cảnh báo Học vụ")
        st.caption("Quy đổi chuẩn Quyết định 1175/QĐ-KHTN & kiểm tra Điều 16:")

        with st.form("gpa_form"):
            mon_hoc = st.text_input("Tên môn học", placeholder="VD: Hệ điều hành")
            col_tc, col_diem = st.columns(2)
            tin_chi = col_tc.number_input("Số tín chỉ", min_value=1, max_value=10, value=3)
            diem_so = col_diem.number_input(
                "Điểm hệ 10", min_value=0.0, max_value=10.0, value=8.0, step=0.1
            )
            accum_tc = st.number_input(
                "Tín chỉ tích lũy các kỳ trước",
                min_value=0,
                max_value=200,
                value=30,
            )

            col_add, col_clear = st.columns(2)
            submitted = col_add.form_submit_button("➕ Thêm môn")
            cleared = col_clear.form_submit_button("🗑️ Làm mới")

            if submitted and mon_hoc.strip():
                st.session_state.gpa_courses.append(
                    {
                        "name": mon_hoc.strip(),
                        "credits": int(tin_chi),
                        "grade": float(diem_so),
                    }
                )
                st.toast(f"Đã thêm môn {mon_hoc} vào bảng điểm!", icon="✅")
            elif cleared:
                st.session_state.gpa_courses = []

        if st.session_state.gpa_courses:
            tuples = [(c["grade"], c["credits"]) for c in st.session_state.gpa_courses]
            gpa_10 = calculate_gpa_10(tuples)
            gpa_4 = calculate_gpa_4(tuples)
            earned_tc = sum(
                c["credits"] for c in st.session_state.gpa_courses if c["grade"] >= 5.0
            )
            warn = check_academic_warning(
                current_semester_earned_credits=earned_tc,
                accumulated_credits=accum_tc + earned_tc,
                previous_semester_gpa=gpa_10,
                two_previous_semesters_gpa=gpa_10,
            )

            m_col1, m_col2 = st.columns(2)
            m_col1.metric("GPA Hệ 10", f"{gpa_10:.2f}")
            m_col2.metric("GPA Hệ 4", f"{gpa_4:.2f}")

            if warn["is_warning"]:
                st.error(f"⚠️ **{warn['status']}**")
                for r in warn["reasons"]:
                    st.caption(f"• {r}")
            else:
                st.success(f"✅ **Trạng thái: {warn['status']}**")

            with st.expander(
                f"📋 Danh sách {len(st.session_state.gpa_courses)} môn đã nhập",
                expanded=True,
            ):
                for c in st.session_state.gpa_courses:
                    _, letter = convert_score_to_4_and_letter(c["grade"])
                    st.write(
                        f"• **{c['name']}**: `{c['grade']}` ({c['credits']} TC) → **{letter}**"
                    )

    # ==========================================
    # KHU VỰC 3 TAB CHÍNH
    # ==========================================
    tab_chat, tab_plan, tab_deadline = st.tabs(
        [
            "💬 Cố vấn Học vụ & Tra cứu Quy chế (Chat)",
            "📅 Lập lịch Ôn thi (EDF) & Dự báo GPA",
            "📥 Bóc tách Deadline (Ollama / Moodle .ics)",
        ]
    )

    # ------------------------------------------
    # TAB 1: KHUNG CHAT TRỢ LÝ H.E.R.M.E.S
    # ------------------------------------------
    with tab_chat:
        st.markdown(
            "💡 **Bấm chọn nhanh tình huống mẫu bên dưới** hoặc đặt câu hỏi trực tiếp bằng ngôn ngữ tự nhiên:"
        )

        q_cols = st.columns(5)
        sample_q = None
        if q_cols[0].button("🇬🇧 Chuẩn Ngoại ngữ CNTT", use_container_width=True):
            sample_q = (
                "Chuẩn đầu ra ngoại ngữ chương trình tăng cường tiếng Anh "
                "ngành Công nghệ thông tin là gì?"
            )
        if q_cols[1].button("🧮 Phân tích GPA & Học lực", use_container_width=True):
            sample_q = (
                "Tính GPA giúp mình: Giải tích 1 (8.5, 4TC), "
                "Cấu trúc dữ liệu (7.5, 4 tín), Pháp luật (9.0, 2TC)"
            )
        if q_cols[2].button("🗓️ Gợi ý Lịch ôn thi EDF", use_container_width=True):
            sample_q = "Lập lịch ôn thi học kỳ này giúp mình với"
        if q_cols[3].button("🛡️ Thử Chặn giải bài tập hộ", use_container_width=True):
            sample_q = "Hãy giải bài tập lập trình C++ giúp tôi"
        if q_cols[4].button("🧹 Xóa đoạn chat", use_container_width=True):
            st.session_state.messages = [
                {"role": "assistant", "content": WELCOME_MESSAGE, "meta": None}
            ]
            st.rerun()

        if "messages" not in st.session_state or not st.session_state.messages:
            st.session_state.messages = [
                {"role": "assistant", "content": WELCOME_MESSAGE, "meta": None}
            ]

        for message in st.session_state.messages:
            avatar_icon = "🎓" if message["role"] == "assistant" else "🧑‍💻"
            with st.chat_message(message["role"], avatar=avatar_icon):
                st.markdown(message["content"])
                if message.get("meta"):
                    st.caption(message["meta"])

        user_prompt = st.chat_input(
            "Hỏi H.E.R.M.E.S về quy chế HCMUS, chuẩn ngoại ngữ, tính GPA hoặc lịch ôn thi..."
        ) or sample_q

        if user_prompt:
            with st.chat_message("user", avatar="🧑‍💻"):
                st.markdown(user_prompt)
            st.session_state.messages.append(
                {"role": "user", "content": user_prompt, "meta": None}
            )

            # Bổ sung ngữ cảnh hồ sơ sinh viên nếu câu hỏi chưa nêu rõ khóa/hệ
            effective_query = user_prompt
            q_low = user_prompt.lower()
            has_cohort = any(k in q_low for k in ["k20", "k21", "k22", "k23", "k24", "k25"])
            if not has_cohort and student_cohort != "Tự động nhận diện":
                # Chỉ nối ngữ cảnh nếu là câu hỏi quy chế
                if any(
                    kw in q_low
                    for kw in ["ngoại ngữ", "tiếng anh", "toeic", "ielts", "chuẩn đầu ra"]
                ) and "ngành công nghệ thông tin" not in q_low:
                    effective_query = f"{user_prompt} ({student_cohort}, {student_program})"

            with st.chat_message("assistant", avatar="🎓"):
                res = orchestrate(effective_query)
                reply = res["response_text"]
                st.write_stream(_stream_markdown(reply))

                engine_label = res.get("target_engine", "orchestrator")
                intent_label = res.get("intent", "GENERAL")
                prov = res.get("provenance")
                meta_parts = [f"⚙️ **Engine:** `{engine_label}`", f"🎯 **Intent:** `{intent_label}`"]
                if prov:
                    meta_parts.append(f"📌 **Nguồn trích dẫn:** *{prov}*")
                meta_text = " • ".join(meta_parts)
                st.caption(meta_text)

            st.session_state.messages.append(
                {"role": "assistant", "content": reply, "meta": meta_text}
            )

    # ------------------------------------------
    # TAB 2: LẬP LỊCH ÔN THI & WHAT-IF GPA
    # ------------------------------------------
    with tab_plan:
        col_sched, col_whatif = st.columns([1.25, 1])

        with col_sched:
            st.subheader("🗓️ Phân bổ Giờ ôn thi Tự động (Thuật toán EDF)")
            st.caption(
                "Tự động phân bổ quỹ thời gian dựa trên **Số tín chỉ** và **Độ ưu tiên/Độ khó** của từng môn thi."
            )
            s_col1, s_col2 = st.columns(2)
            days_left = s_col1.slider("Số ngày còn lại trước kỳ thi", 1, 30, 10)
            daily_hours = s_col2.slider("Số giờ ôn tập mỗi ngày", 1.0, 12.0, 6.0, 0.5)

            with st.expander("➕ Thêm môn thi vào kế hoạch ôn tập", expanded=False):
                with st.form("add_exam_form"):
                    ex_name = st.text_input("Tên môn thi", placeholder="VD: Mạng Máy Tính")
                    ex_c1, ex_c2 = st.columns(2)
                    ex_tc = ex_c1.number_input("Số tín chỉ", 1, 10, 4)
                    ex_prio = ex_c2.selectbox(
                        "Mức độ ưu tiên / Độ khó",
                        options=[3, 2, 1],
                        format_func=lambda x: (
                            "3 - Cao (Khó / Sắp thi)"
                            if x == 3
                            else ("2 - Trung bình" if x == 2 else "1 - Cơ bản")
                        ),
                    )
                    if st.form_submit_button("Thêm vào lịch ôn thi") and ex_name.strip():
                        st.session_state.exam_subjects.append(
                            {
                                "name": ex_name.strip(),
                                "credits": int(ex_tc),
                                "priority": int(ex_prio),
                            }
                        )
                        st.rerun()

            plan_data = generate_study_plan(
                st.session_state.exam_subjects, daily_hours, days_left
            )
            st.dataframe(plan_data, use_container_width=True, hide_index=True)

        with col_whatif:
            st.subheader("🎯 Mô phỏng Điểm mục tiêu (What-If GPA Simulator)")
            st.caption(
                "Tính toán mức điểm tối thiểu bạn cần đạt trong học kỳ tới để chạm mốc GPA mong muốn."
            )
            target_gpa = st.number_input(
                "GPA Hệ 10 mục tiêu muốn đạt",
                min_value=5.0,
                max_value=10.0,
                value=8.0,
                step=0.1,
            )
            rem_credits = st.number_input(
                "Số tín chỉ dự kiến đăng ký học kỳ tới",
                min_value=1,
                max_value=30,
                value=12,
            )
            if st.session_state.gpa_courses:
                req_gpa = simulate_gpa(
                    st.session_state.gpa_courses, target_gpa, int(rem_credits)
                )
                if req_gpa > 10.0:
                    st.warning(
                        f"⚠️ **Thử thách cao:** Bạn cần đạt **{req_gpa:.2f}/10** trong {rem_credits} TC tới "
                        "(Vượt thang điểm 10). Hãy cân nhắc đăng ký thêm tín chỉ hoặc học cải thiện môn điểm thấp!"
                    )
                elif req_gpa <= 5.0:
                    st.success(
                        f"🎉 **Rất khả thi:** Bạn chỉ cần đạt trung bình **{max(req_gpa, 5.0):.2f}/10** "
                        f"cho **{rem_credits} tín chỉ** kỳ tới là giữ vững mục tiêu GPA **{target_gpa:.2f}**!"
                    )
                else:
                    st.info(
                        f"💡 **Mục tiêu rõ ràng:** Để đạt GPA tích lũy **{target_gpa:.2f}**, bạn cần đạt trung bình "
                        f"**{req_gpa:.2f}/10** cho **{rem_credits} tín chỉ** trong học kỳ tới."
                    )

    # ------------------------------------------
    # TAB 3: BÓC TÁCH DEADLINE (OLLAMA / .ICS)
    # ------------------------------------------
    with tab_deadline:
        col_ann, col_ics = st.columns(2)

        with col_ann:
            st.subheader("📢 Bóc tách Thông báo Giảng viên (AI Extractor)")
            ai_mode = st.selectbox(
                "Chế độ xử lý AI (R4)",
                options=["mock", "ollama"],
                format_func=lambda m: (
                    "⚡ Chế độ Tất định Nhanh (Offline Mock / Regex)"
                    if m == "mock"
                    else "🤖 Mô hình Ollama Cục bộ (qwen2.5:3b @ localhost:11434)"
                ),
            )
            raw_ann = st.text_area(
                "Dán nội dung thông báo bài tập trên Moodle/Email vào đây:",
                value=(
                    "Thông báo: Môn học: Mạng máy tính. "
                    "Bài tập: Đồ án lập trình Socket. "
                    "Hạn nộp: 23:59 ngày 20/11/2026. "
                    "Hình thức nộp: Qua Moodle (.zip). "
                    "Lưu ý: Đặt tên file theo MSSV."
                ),
                height=135,
            )
            if st.button("🔍 Bóc tách Thông tin Bài tập", type="primary"):
                try:
                    info = extract_announcement_info(raw_ann, mode=ai_mode)
                    st.success("Đã bóc tách và kiểm chứng chống ảo giác (Grounding Verified)!")
                    st.markdown(
                        f"""
                        | Trường thông tin | Kết quả trích xuất |
                        | :--- | :--- |
                        | **📚 Môn học** | **{info.course_name}** |
                        | **📝 Bài tập / Nhiệm vụ** | {info.assignment_content} |
                        | **⏰ Hạn nộp (Deadline)** | `{info.deadline}` |
                        | **📤 Hình thức nộp** | {info.submission_format} |
                        | **⚠️ Lưu ý thêm** | {info.other_requirements} |
                        """
                    )
                except Exception as exc:
                    st.error(f"Lỗi kết nối AI ({ai_mode}): {exc}")

        with col_ics:
            st.subheader("📆 Đọc file lịch Moodle (.ics Parser)")
            uploaded_ics = st.file_uploader(
                "Tải lên file .ics xuất từ Moodle HCMUS", type=["ics"]
            )
            use_sample_ics = st.button("📂 Dùng thử file .ics mẫu từ Moodle HCMUS")

            ics_text_to_parse = None
            if uploaded_ics is not None:
                ics_text_to_parse = uploaded_ics.read().decode("utf-8", errors="replace")
            elif use_sample_ics:
                ics_text_to_parse = SAMPLE_ICS_CONTENT

            if ics_text_to_parse:
                events = parse_ics_deadlines(ics_text_to_parse)
                if events:
                    st.success(f"🎉 Đã trích xuất thành công {len(events)} hạn nộp bài từ lịch Moodle!")
                    st.dataframe(events, use_container_width=True, hide_index=True)
                else:
                    st.warning("Không tìm thấy sự kiện VEVENT nào trong dữ liệu .ics.")


if __name__ == "__main__":
    main()
