# H.E.R.M.E.S – Final Engineering Report (Submission Pack 01)
> **HCMUS Educational Resource & Mentoring Expert System**
> **Course:** CSC10014 – Computational Thinking | **Institution:** FIT, VNU-HCM University of Science (HCMUS)

---

## 1. Executive Summary & Team Ownership

**H.E.R.M.E.S** là hệ thống Trợ lý và Cố vấn Học vụ Thông minh được thiết kế chuyên biệt cho sinh viên đại học chính quy Trường Đại học Khoa học Tự nhiên, ĐHQG-HCM. Thay vì đẩy mọi yêu cầu của người dùng vào một mô hình ngôn ngữ lớn (LLM) duy nhất dễ gây ảo giác số học và sai lệch quy chế, H.E.R.M.E.S hiện thực hóa triết lý của môn học **Tư duy Tính toán (Computational Thinking)**:
> *"Understand $\rightarrow$ Decompose $\rightarrow$ Represent $\rightarrow$ Decide $\rightarrow$ Execute $\rightarrow$ Verify $\rightarrow$ Improve."*

| STT | MSSV | Họ và Tên | Vai trò & Trách nhiệm (R1–R8) | GitHub Username | Module phụ trách chính |
| :---: | :---: | :--- | :--- | :---: | :--- |
| 1 | `25127331` | **Nguyễn Huỳnh Minh Hiếu** | Team Leader & System Architect (`R1`, `R5`) | `nhmhieu` | `router/orchestrator.py`, `router/session.py`, `cli.py` |
| 2 | `25127152` | **Nghiêm Đình Thuận** | Deterministic & Algorithm Lead (`R2`) | `Jake` | `engines/academic_calc.py`, `engines/scheduler.py` |
| 3 | `25127552` | **Đào Ngọc Vinh** | Knowledge Base & RAG Lead (`R3`) | `vinh` | `rag/retriever.py`, `data/regulations/hcmus_regulations.json` |
| 4 | `25127471` | **Đào Nhật Quân** | System Safety & Security Lead (`R7`, `R4`) | `quan` | `security/guardrails.py`, `ai/client.py` |
| 5 | `25127168` | **Phan Huỳnh Minh Tuấn** | UI/UX & Client Application Lead (`R6`) | `phmtuan2522-coder` | `ui/app.py`, `ai_cli.py`, `cli.py` |
| 6 | `25127176` | **Hồ Ngọc Như Ý** | QA, Evaluation & Benchmark Lead (`R8`, `R4`) | `hnny712` | `engines/deadline_parser.py`, `tests/benchmark/` |

---

## 2. Problem Framing & Boundary (Requirement R1)
Chi tiết đầy đủ được trình bày tại [docs/PROJECT_CHARTER.md](PROJECT_CHARTER.md).
- **Đối tượng người dùng mục tiêu:** Sinh viên năm 1–2 khoa CNTT & các khoa thuộc ĐH KHTN, cùng Cố vấn học tập.
- **3 Nỗi đau cốt lõi (Pain Points):**
  1. **Quy chế học vụ phân tán:** 17 văn bản quy chế tín chỉ (QĐ 1175/QĐ-KHTN) và chuẩn đầu ra ngoại ngữ (QĐ 2464, 1983, 1984, 1985) khác biệt theo từng khóa (K20–K25) và chương trình (Chuẩn, Tăng cường Tiếng Anh, Tiên tiến).
  2. **Quá tải lịch thi & Deadline Moodle:** Sinh viên đối mặt với 5–7 môn thi cuối kỳ trong 2 tuần nhưng thiếu công cụ phân bổ giờ học định lượng.
  3. **Rủi ro ảo giác LLM & Vi phạm liêm chính học thuật:** Các chatbot phổ thông tính sai điểm GPA hệ 4, trích dẫn sai điều khoản và sẵn sàng giải bài tập hộ sinh viên.
- **Explicit Non-Goals (Ranh giới từ chối):** Tuyệt đối không giải bài tập/viết code làm đồ án hộ sinh viên; không thu thập mật khẩu Portal/Moodle; không tự động can thiệp hệ thống đăng ký học phần của trường.

---

## 3. Computational Thinking Reasoning (4 Pillars)
1. **Decomposition (Phân rã bài toán):** Tách bài toán cố vấn học vụ thành 5 lớp độc lập:
   - *Lớp Bảo vệ (`R7`):* Chuẩn hóa chuỗi và lọc tấn công 4 lớp.
   - *Lớp Điều phối & Trạng thái (`R5`):* Phân loại ý định 2 tầng và lưu vết hội thoại đa lượt (`SessionManager`).
   - *Lớp Tính toán Tất định (`R2`):* Quy đổi điểm hệ 10/hệ 4, cảnh báo Điều 16 và xếp lịch EDF.
   - *Lớp Truy xuất Tri thức Có nguồn gốc (`R3`):* Lọc cây quy chế 2 tầng + xếp hạng BM25.
   - *Lớp Bóc tách Thực thể AI Cục bộ (`R4`):* Trích xuất thông báo giảng viên qua Ollama `qwen2.5:3b` & đọc lịch `.ics`.
2. **Pattern Recognition (Nhận diện mẫu):**
   - Nhận diện cấu trúc bảng điểm tự nhiên trong câu chat tiếng Việt qua biểu thức chính quy kép: mẫu đầy đủ `Tên môn (Điểm, Số TC)` và mẫu rút gọn `8.5 (4TC)`.
   - Nhận diện chữ ký tấn công Prompt Injection ẩn dưới dạng chèn khoảng trắng (`i g n o r e`), ký tự Zero-Width, Base64 và thẻ hệ thống giả mạo (`system_instruction`).
3. **Abstraction (Trừu tượng hóa dữ liệu):**
   - Mô hình hóa 17 văn bản PDF hành冗 dài hàng trăm trang thành cấu trúc cây JSON 2 cấp (`van_ban` $\rightarrow$ `chunks`) trong [`hcmus_regulations.json`](../data/regulations/hcmus_regulations.json) với các thuộc tính lọc nhanh (`chuong_trinh`, `nganh`, `khoa_ap_dung`, `chung_chi_toi_thieu`).
4. **Algorithm Design (Thiết kế giải thuật):**
   - **Thuật toán EDF có trọng số (`scheduler.py`):** Sử dụng hàng đợi ưu tiên (`heapq`) độ phức tạp $O(n \log n)$ kết hợp trọng số $W_i = \text{Credits}_i \times (1 + 0.25 \times \text{Difficulty}_i)$.
   - **Thuật toán BM25 phân cấp (`retriever.py`):** Cắt tỉa nhánh văn bản không thuộc khóa/ngành của sinh viên trước khi tính điểm BM25 ($k_1 = 1.5, b = 0.75$) kèm thưởng điểm tiêu đề (`+0.6 * idf`).

---

## 4. System Architecture & Orchestration (Requirement R5 & Pack 03)
- **3 Sơ đồ C4 chuẩn Simon Brown:**
  - Level 1 (`C4Context`): [docs/system_context.md](system_context.md)
  - Level 2 (`C4Container`): [docs/container.md](container.md)
  - Level 3 (`C4Component`): [docs/component.md](component.md)
- **Sequence Diagram, State Machine & Pseudocode:** Xem chi tiết tại [docs/ARCHITECTURE.md](ARCHITECTURE.md).

---

## 5. Implementation of Core Capabilities (`R2, R3, R4, R6, R7`)
1. **Deterministic Academic & Scheduling Engine (`R2` – [`academic_calc.py`](../src/hermes/engines/academic_calc.py), [`scheduler.py`](../src/hermes/engines/scheduler.py)):**
   - Quy đổi chính xác tuyệt đối thang điểm 10 sang thang điểm 4 và điểm chữ (`A+, A, B+, B, C+, C, D+, D, F`) theo Quyết định 1175/QĐ-KHTN.
   - Kiểm tra đồng thời 3 điều kiện cảnh báo học vụ Điều 16 (tín chỉ đạt trong kỳ, điểm TB học kỳ, điểm TB 2 học kỳ liên tiếp).
   - Mô phỏng điểm mục tiêu (*What-If GPA Simulator*) và phân bổ lịch ôn thi EDF.
2. **Hierarchical RAG Engine (`R3` – [`retriever.py`](../src/hermes/rag/retriever.py)):**
   - Bao phủ **17 văn bản pháp quy chính thức của ĐH KHTN**, tự động loại bỏ văn bản hết hiệu lực và ưu tiên bảng điểm chứng chỉ ngoại ngữ tối thiểu (`chung_chi_toi_thieu`).
3. **Local AI & iCalendar Extractor (`R4` – [`client.py`](../src/hermes/ai/client.py), [`deadline_parser.py`](../src/hermes/engines/deadline_parser.py)):**
   - Hỗ trợ gọi trực tiếp máy chủ **Ollama Local LLM (`qwen2.5:3b`)** qua `http://localhost:11434/api/generate` (chi phí API = 0đ, bảo mật dữ liệu cục bộ 100%) kèm cơ chế tự động chuyển về `Mock/Regex` khi ngoại tuyến và kiểm chứng chống ảo giác (`_verify_grounding`).
   - Phân tích cú pháp chuẩn RFC 5545 cho file lịch `.ics` xuất từ Moodle HCMUS.
4. **End-to-End Interfaces (`R6` – [`cli.py`](../src/hermes/cli.py), [`ui/app.py`](../src/hermes/ui/app.py)):**
   - Giao diện dòng lệnh `Click + Rich` (4 lệnh: `ask`, `gpa`, `plan`, `interactive`).
   - Giao diện Web `Streamlit` 3-Tab hiện đại có chọn hồ sơ sinh viên (Khóa K21–K25, Hệ đào tạo), hiệu ứng trả lời mượt mà và bảng tính GPA trực tiếp.

---

## 6. Evaluation, Improvement Cycle & Risk Analysis (`R7, R8` & Packs 04, 05)
Báo cáo chi tiết nằm tại [docs/EVALUATION_AND_RISK_PACK.md](EVALUATION_AND_RISK_PACK.md):
- **Unit & Integration Test Suite:** **475 / 475 bài kiểm thử tự động (`pytest`) vượt qua 100%** trong ~3.0 giây.
- **Benchmark Improvement Cycle (72 Test Cases):**
  - *Iteration 1 (Baseline):* Đạt **58/72 (80.56%)**, ghi nhận 14 lỗi thuộc 4 nhóm Error Taxonomy (`ET-01` đến `ET-04`).
  - *Iteration 2 (Sau khi cải tiến Router, Regex, Guardrails & RAG):* Đạt **72/72 (100.00%)** với độ trễ định tuyến trung bình **0.336 ms/câu** (nhanh hơn 60 lần so với mục tiêu DoD $< 20\text{ ms}$).

---

## 7. Limitations & Future Roadmap
- **Hạn chế hiện tại:** Dữ liệu quy chế hiện được cập nhật bán tự động qua file JSON; chưa kết nối trực tiếp OAuth với Portal sinh viên do chính sách bảo mật của nhà trường.
- **Hướng phát triển (Phase 2):**
  1. Tích hợp OCR tự động chuyển đổi văn bản PDF có dấu mộc mới của Phòng Đào tạo sang cấu trúc JSON chuẩn.
  2. Xuất trực tiếp lịch ôn thi EDF từ H.E.R.M.E.S ra file `.ics` để sinh viên nhập ngược vào Google Calendar / Apple Calendar.
