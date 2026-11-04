import streamlit as st
import time
from hermes.router.orchestrator import orchestrate

# 1. Cấu hình tiêu đề trang web
st.set_page_config(page_title="H.E.R.M.E.S Assistant", page_icon="🤖")
st.title("🤖 Trợ lý Học vụ H.E.R.M.E.S")
st.markdown(
    "Xin chào! Mình là trợ lý ảo hỗ trợ sinh viên HCMUS. Cậu cần tính điểm, xếp lịch hay tra quy chế?"
)

# ==========================================
# GIAO DIỆN THANH BÊN (SIDEBAR) ĐẶT Ở ĐÂY
# ==========================================
with st.sidebar:
    st.header("📊 Tính điểm GPA nhanh")
    st.markdown("Nhập điểm môn học mới nhất của cậu vào đây:")

    # Tạo Form nhập liệu
    with st.form("gpa_form"):
        mon_hoc = st.text_input("Tên môn học", placeholder="VD: Cấu trúc Dữ liệu")
        tin_chi = st.number_input("Số tín chỉ", min_value=1, max_value=10, value=3)
        diem_so = st.number_input(
            "Điểm hệ 10", min_value=0.0, max_value=10.0, value=8.0, step=0.5
        )

        # Nút submit form
        submitted = st.form_submit_button("Cập nhật điểm")
        if submitted:
            st.success(
                f"Đã ghi nhận môn {mon_hoc}! (Chờ thuật toán của Thành viên 2 để tính tổng)"
            )

# ==========================================
# KHU VỰC KHUNG CHAT CHÍNH
# ==========================================
# 2. Khởi tạo bộ nhớ (Session State) để lưu lịch sử đoạn chat
if "messages" not in st.session_state:
    st.session_state.messages = []

# 3. Vẽ lại toàn bộ lịch sử tin nhắn mỗi khi trang web tải lại
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 4. Tạo ô nhập liệu cho người dùng ở cuối màn hình
if prompt := st.chat_input("Nhập câu hỏi của cậu vào đây..."):

    # Hiển thị ngay tin nhắn của người dùng lên màn hình
    with st.chat_message("user"):
        st.markdown(prompt)

    # Lưu tin nhắn của user vào bộ nhớ
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 5. Xử lý và hiển thị câu trả lời của AI
    with st.chat_message("assistant"):
        # Hiển thị icon xoay vòng vòng báo hiệu hệ thống đang xử lý
        with st.spinner("H.E.R.M.E.S đang xử lý..."):
            # Gọi hàm thật từ router
            res = orchestrate(prompt)
            reply = res["response_text"]

            # Nếu có nguồn tham khảo thì nối thêm vào câu trả lời
            if res.get("provenance"):
                reply += f"\n\n📌 *Nguồn: {res['provenance']}*"

            st.markdown(reply)

    # Lưu tin trả lời của AI vào bộ nhớ
    st.session_state.messages.append({"role": "assistant", "content": reply})
