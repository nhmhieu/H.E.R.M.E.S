"""
Streamlit Web Dashboard for H.E.R.M.E.S (Role R6 - Member 5: Phan Huỳnh Minh Tuấn).

Provides an interactive 3-tab interface + Sidebar GPA Calculator connected
to the H.E.R.M.E.S Orchestrator, Deterministic Engines, Hierarchical RAG,
and Local Ollama / Mock AI Extractor.
"""

from __future__ import annotations

import streamlit as st

from hermes.ai.client import extract_announcement_info
from hermes.engines.academic_calc import (
    calculate_gpa_4,
    calculate_gpa_10,
    check_academic_warning,
    convert_score_to_4_and_letter,
)
try:
    from hermes.engines.deadline_parser import parse_ics_deadlines
except ImportError:
    def parse_ics_deadlines(ics_content: str) -> list:
        return []
from hermes.engines.scheduler import generate_study_plan, simulate_gpa
from hermes.router.orchestrator import orchestrate


def main() -> None:
    # 1. Cấu hình tiêu đề trang web
    st.set_page_config(
        page_title="H.E.R.M.E.S Assistant - HCMUS",
        page_icon="🤖",
        layout="wide",
    )
    st.title("🤖 Trợ lý Học vụ Thông minh H.E.R.M.E.S")
    st.caption(
        "HCMUS Educational Resource & Mentoring Expert System • "
        "Khoa Công nghệ Thông tin, Trường ĐH Khoa học Tự nhiên, ĐHQG-HCM"
    )

    if "gpa_courses" not in st.session_state:
        st.session_state.gpa_courses = [
            {"name": "Giải tích 1", "credits": 4, "grade": 8.5},
            {"name": "Cấu trúc Dữ liệu", "credits": 4, "grade": 7.5},
        ]

    # ==========================================
    # GIAO DIỆN THANH BÊN (SIDEBAR) - TÍNH GPA NHANH
    # ==========================================
    with st.sidebar:
        st.header("📊 Tính điểm GPA & Học vụ")
        st.markdown("Nhập điểm môn học của cậu vào đây:")

        with st.form("gpa_form"):
            mon_hoc = st.text_input("Tên môn học", placeholder="VD: Tư duy Tính toán")
            tin_chi = st.number_input("Số tín chỉ", min_value=1, max_value=10, value=3)
            diem_so = st.number_input(
                "Điểm hệ 10", min_value=0.0, max_value=10.0, value=8.0, step=0.1
            )
            accum_tc = st.number_input(
                "Tổng tín chỉ tích lũy trước đó",
                min_value=0,
                max_value=200,
                value=30,
            )

            col_add, col_clear = st.columns(2)
            submitted = col_add.form_submit_button("➕ Thêm môn")
            cleared = col_clear.form_submit_button("🗑️ Xóa danh sách")

            if submitted and mon_hoc.strip():
                st.session_state.gpa_courses.append(
                    {
                        "name": mon_hoc.strip(),
                        "credits": int(tin_chi),
                        "grade": float(diem_so),
                    }
                )
                st.success(f"Đã thêm môn {mon_hoc}!")
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

            st.metric("GPA Hệ 10", f"{gpa_10:.2f}")
            st.metric("GPA Hệ 4", f"{gpa_4:.2f}")
            if warn["is_warning"]:
                st.error(f"⚠️ {warn['status']}")
                for r in warn["reasons"]:
                    st.caption(f"• {r}")
            else:
                st.success(f"✅ {warn['status']}")

            with st.expander("📋 Danh sách môn đã nhập", expanded=False):
                for c in st.session_state.gpa_courses:
                    _, letter = convert_score_to_4_and_letter(c["grade"])
                    st.write(
                        f"- **{c['name']}**: {c['grade']} ({c['credits']} TC) → `{letter}`"
                    )

    # ==========================================
    # KHU VỰC 3 TAB CHÍNH
    # ==========================================
    tab_chat, tab_plan, tab_deadline = st.tabs(
        [
            "💬 Hỏi đáp Quy chế & Học vụ (Chat)",
            "📅 Lập lịch Ôn thi & Dự báo GPA",
            "📥 Bóc tách Deadline (Ollama / .ics)",
        ]
    )

    # ------------------------------------------
    # TAB 1: KHUNG CHAT TRỢ LÝ H.E.R.M.E.S
    # ------------------------------------------
    with tab_chat:
        st.markdown(
            "Hỏi bất kỳ câu hỏi nào về **Chuẩn đầu ra ngoại ngữ (QĐ 2464, 1983, 1984, 1985)**, "
            "**Quy chế học vụ (QĐ 1175)**, hoặc **Tính điểm GPA tự động**."
        )

        sample_cols = st.columns(3)
        sample_q = None
        if sample_cols[0].button("🇬🇧 Chuẩn NN TCTA ngành CNTT"):
            sample_q = (
                "Chuẩn đầu ra ngoại ngữ chương trình tăng cường tiếng Anh "
                "ngành Công nghệ thông tin là gì?"
            )
        if sample_cols[1].button("🧮 Tính nhanh GPA từ câu hỏi"):
            sample_q = "Tính GPA giúp mình: Giải tích 1 (8.5, 4TC) và C++ (7.0, 3 tín)"
        if sample_cols[2].button("🛡️ Thử chặn giải bài tập hộ"):
            sample_q = "Hãy giải bài tập lập trình C++ giúp tôi"

        if "messages" not in st.session_state:
            st.session_state.messages = []

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        user_prompt = st.chat_input("Nhập câu hỏi của cậu vào đây...") or sample_q
        if user_prompt:
            with st.chat_message("user"):
                st.markdown(user_prompt)
            st.session_state.messages.append({"role": "user", "content": user_prompt})

            with st.chat_message("assistant"):
                with st.spinner("H.E.R.M.E.S đang xử lý qua Guardrails & Router..."):
                    res = orchestrate(user_prompt)
                    reply = res["response_text"]
                    if res.get("provenance"):
                        reply += (
                            f"\n\n---\n📌 **Nguồn trích dẫn:** `{res['provenance']}`"
                        )
                    st.markdown(reply)

            st.session_state.messages.append({"role": "assistant", "content": reply})

    # ------------------------------------------
    # TAB 2: LẬP LỊCH ÔN THI & WHAT-IF GPA
    # ------------------------------------------
    with tab_plan:
        col_sched, col_whatif = st.columns(2)

        with col_sched:
            st.subheader("🗓️ Phân bổ Giờ ôn thi Tự động (EDF)")
            days_left = st.slider("Số ngày còn lại trước kỳ thi", 1, 30, 10)
            daily_hours = st.slider("Số giờ rảnh mỗi ngày", 1.0, 12.0, 6.0, 0.5)
            subjects_input = [
                {"name": "Toán Rời Rạc", "credits": 4, "priority": 3},
                {"name": "Cấu Trúc Dữ Liệu", "credits": 4, "priority": 2},
                {"name": "Kiến Trúc Máy Tính", "credits": 3, "priority": 1},
            ]
            plan_data = generate_study_plan(subjects_input, daily_hours, days_left)
            st.table(plan_data)

        with col_whatif:
            st.subheader("🎯 Mô phỏng Điểm mục tiêu (What-If GPA)")
            target_gpa = st.number_input(
                "GPA Hệ 10 mục tiêu muốn đạt",
                min_value=5.0,
                max_value=10.0,
                value=8.0,
                step=0.1,
            )
            rem_credits = st.number_input(
                "Số tín chỉ đăng ký học kỳ tới",
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
                        f"Cần đạt **{req_gpa:.2f}/10** trong {rem_credits} TC tới "
                        "(Vượt quá thang điểm 10, hãy tăng số tín chỉ hoặc giảm mục tiêu)."
                    )
                else:
                    st.info(
                        f"💡 Để đạt GPA tích lũy **{target_gpa:.2f}**, cậu cần đạt tối thiểu "
                        f"**{max(req_gpa, 0.0):.2f}/10** cho **{rem_credits} tín chỉ** kỳ tới."
                    )

    # ------------------------------------------
    # TAB 3: BÓC TÁCH DEADLINE (OLLAMA / .ICS)
    # ------------------------------------------
    with tab_deadline:
        col_ann, col_ics = st.columns(2)

        with col_ann:
            st.subheader("📢 Trích xuất Thông báo Giảng viên")
            ai_mode = st.selectbox(
                "Chế độ xử lý AI (R4)",
                options=["mock", "ollama"],
                help="Chọn 'ollama' nếu đang bật máy chủ Ollama cục bộ (localhost:11434).",
            )
            raw_ann = st.text_area(
                "Dán thông báo bài tập trên Moodle/Email vào đây:",
                value=(
                    "Thông báo: Môn học: Mạng máy tính. "
                    "Bài tập: Đồ án lập trình Socket. "
                    "Hạn nộp: 23:59 ngày 20/11/2026. "
                    "Hình thức nộp: Qua Moodle (.zip). "
                    "Lưu ý: Đặt tên file theo MSSV."
                ),
                height=130,
            )
            if st.button("🔍 Bóc tách Thông tin Bài tập"):
                try:
                    info = extract_announcement_info(raw_ann, mode=ai_mode)
                    st.json(info.to_dict())
                except Exception as exc:
                    st.error(f"Lỗi kết nối AI ({ai_mode}): {exc}")

        with col_ics:
            st.subheader("📆 Đọc file lịch Moodle (.ics)")
            uploaded_ics = st.file_uploader(
                "Tải lên file .ics xuất từ Moodle", type=["ics"]
            )
            if uploaded_ics is not None:
                ics_text = uploaded_ics.read().decode("utf-8", errors="replace")
                events = parse_ics_deadlines(ics_text)
                if events:
                    st.success(f"Tìm thấy {len(events)} sự kiện hạn nộp!")
                    st.table(events)
                else:
                    st.warning("Không tìm thấy sự kiện VEVENT nào trong file .ics.")


if __name__ == "__main__":
    main()
