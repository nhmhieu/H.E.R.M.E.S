# 🎓 H.E.R.M.E.S — HCMUS Educational Resource & Mentoring Expert System

[![CI Pipeline](https://img.shields.io/badge/CI-passing-brightgreen)](#)
[![Unit Tests](https://img.shields.io/badge/pytest-475%20passed-brightgreen)](#)
[![Benchmark](https://img.shields.io/badge/benchmark-72%2F72%20(100%25)-blue)](#)
[![Code Style](https://img.shields.io/badge/code%20style-black%20%7C%20flake8-000000)](#)

> **Course:** CSC10014 – Computational Thinking (Academic Year 2026)  
> **Institution:** Faculty of Information Technology, VNU-HCM University of Science (HCMUS)  
> **Core Principle:** *"AI is one computational component, not the architecture. Understand $\rightarrow$ Decompose $\rightarrow$ Represent $\rightarrow$ Decide $\rightarrow$ Execute $\rightarrow$ Verify $\rightarrow$ Improve."*

---

## 📋 1. Course Requirements (`R1–R8`) & Submission Package (`Pack 01–07`) Traceability Matrix

Bảng đối chiếu trực tiếp toàn bộ yêu cầu từ tài liệu đề bài môn học (**CSC10014 – Engineering a Smart Virtual Assistant**) với các tệp mã nguồn và hồ sơ kỹ thuật trong kho lưu trữ này:

### 1.1 Minimum System Requirements (`R1 – R8`)

| ID | Yêu cầu hệ thống | Minh chứng thực thi trong H.E.R.M.E.S | Trạng thái |
| :---: | :--- | :--- | :---: |
| **`R1`** | **Problem Boundary** (Target user, pain points, 10 use cases, explicit non-goals, measurable DoD) | [docs/PROJECT_CHARTER.md](docs/PROJECT_CHARTER.md) & [docs/PROPOSAL_DRAFT.md](docs/PROPOSAL_DRAFT.md) | ✅ **100%** |
| **`R2`** | **Deterministic Capability** (Scale-10/4 GPA, Article 16 Warning, EDF Study Scheduler, What-If GPA) | [src/hermes/engines/academic_calc.py](src/hermes/engines/academic_calc.py) & [src/hermes/engines/scheduler.py](src/hermes/engines/scheduler.py) | ✅ **100%** |
| **`R3`** | **Data / Retrieval Capability** (17 official HCMUS legal documents, 2-level tree filter + BM25 + exact provenance) | [data/regulations/hcmus_regulations.json](data/regulations/hcmus_regulations.json) & [src/hermes/rag/retriever.py](src/hermes/rag/retriever.py) | ✅ **100%** |
| **`R4`** | **AI-Enabled Capability** (Local Ollama `qwen2.5:3b` announcement extraction with grounding verification + `.ics` parser) | [src/hermes/ai/client.py](src/hermes/ai/client.py) & [src/hermes/engines/deadline_parser.py](src/hermes/engines/deadline_parser.py) | ✅ **100%** |
| **`R5`** | **Routing & Orchestration** (Two-Tier Intent Router + `SessionManager` multi-turn clarification & fallback paths) | [src/hermes/router/orchestrator.py](src/hermes/router/orchestrator.py) & [src/hermes/router/session.py](src/hermes/router/session.py) | ✅ **100%** |
| **`R6`** | **End-to-End Interface** (Rich CLI + 3-Tab Streamlit Web Dashboard connected to live backend) | [src/hermes/cli.py](src/hermes/cli.py) & [src/hermes/ui/app.py](src/hermes/ui/app.py) | ✅ **100%** |
| **`R7`** | **Reliability & Safeguards** (4-Layer Fail-Closed Guardrails: De-obfuscation, Prompt Injection, Anti-Homework, XSS/SQLi) | [src/hermes/security/guardrails.py](src/hermes/security/guardrails.py) & [tests/unit/test_guardrails.py](tests/unit/test_guardrails.py) | ✅ **100%** |
| **`R8`** | **Repeatable Evaluation** (72-case Benchmark, Iteration 1 `80.56%` $\rightarrow$ Iteration 2 `100.00%`, Error Taxonomy, `0.336ms` latency) | [tests/benchmark/run_evaluation.py](tests/benchmark/run_evaluation.py) & [docs/EVALUATION_AND_RISK_PACK.md](docs/EVALUATION_AND_RISK_PACK.md) | ✅ **100%** |

### 1.2 Submission Package (`Pack 01 – Pack 07`)

| Pack | Tên gói hồ sơ nộp | Tài liệu / Đường dẫn trong Repository |
| :---: | :--- | :--- |
| **`Pack 01`** | **Engineering Report** | [docs/ENGINEERING_REPORT.md](docs/ENGINEERING_REPORT.md) & [docs/PROPOSAL_DRAFT.md](docs/PROPOSAL_DRAFT.md) |
| **`Pack 02`** | **Source Repository / Demo** | [`src/hermes/`](src/hermes/), [`tests/`](tests/), [`pyproject.toml`](pyproject.toml), và hướng dẫn chạy bên dưới |
| **`Pack 03`** | **Architecture & Design Pack** | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (Kèm Pseudocode, Sequence, State Machine, Contracts) + 3 sơ đồ C4: [system_context.md](docs/system_context.md), [container.md](docs/container.md), [component.md](docs/component.md) |
| **`Pack 04`** | **Evaluation Pack** | [docs/EVALUATION_AND_RISK_PACK.md](docs/EVALUATION_AND_RISK_PACK.md) (Phần I: Before/After Cycle & Error Taxonomy) + [`tests/benchmark/`](tests/benchmark/) |
| **`Pack 05`** | **Failure & Risk Pack** | [docs/EVALUATION_AND_RISK_PACK.md](docs/EVALUATION_AND_RISK_PACK.md) (Phần II: Failure Catalogue, Privacy & Red-Team Suite) |
| **`Pack 06`** | **Presentation & Final Demo** | [docs/Proposal H.E.R.M.E.S.pdf](docs/Proposal%20H.E.R.M.E.S.pdf) + Live Streamlit Web UI & Rich CLI Demo |
| **`Pack 07`** | **Team Logbook & AI Evidence** | [docs/LOGBOOK.md](docs/LOGBOOK.md) (Nhật ký 4 tuần, Bảng đóng góp PRs/Commits & Hồ sơ kiểm chứng AI) |

---

## 👥 2. Team Structure & Ownership

| No. | Student ID | Full Name | Role | GitHub Account | Primary Modules |
| :---: | :---: | :--- | :--- | :--- | :--- |
| 1 | `25127331` | **Nguyễn Huỳnh Minh Hiếu** | Team Leader & System Architect (`R1, R5`) | `@nhmhieu` | `router/orchestrator.py`, `router/session.py`, `cli.py` |
| 2 | `25127152` | **Nghiêm Đình Thuận** | Deterministic & Algorithm Lead (`R2`) | `@thuannghiem11` | `engines/academic_calc.py`, `engines/scheduler.py` |
| 3 | `25127552` | **Đào Ngọc Vinh** | Knowledge Base & RAG Lead (`R3`) | `@daongocvinh` | `rag/retriever.py`, `data/regulations/hcmus_regulations.json` |
| 4 | `25127471` | **Đào Nhật Quân** | System Safety & Local AI Lead (`R7, R4`) | `@dnquan14` | `security/guardrails.py`, `ai/client.py` |
| 5 | `25127168` | **Phan Huỳnh Minh Tuấn** | UI/UX & Client Application Lead (`R6`) | `@phmtuan2522-coder` | `ui/app.py`, `ai_cli.py`, `cli.py` |
| 6 | `25127176` | **Hồ Ngọc Như Ý** | QA, Evaluation & Benchmark Lead (`R8, R4`) | `@hnny712` | `engines/deadline_parser.py`, `tests/benchmark/` |

---

## 🚀 3. Reproducible Setup & Quick Start (`Pack 02`)

### 3.1 Cài đặt môi trường
```bash
git clone https://github.com/nhmhieu/H.E.R.M.E.S.git
cd H.E.R.M.E.S
python -m venv .venv

# Kích hoạt môi trường ảo (Windows PowerShell):
.\.venv\Scripts\Activate.ps1

# Cài đặt gói H.E.R.M.E.S và các thư viện phụ thuộc:
pip install -e ".[dev]"
```

### 3.2 Chạy Giao diện Web (3-Tab Streamlit Dashboard)
```bash
streamlit run src/hermes/ui/app.py
```

### 3.3 Chạy Giao diện Dòng lệnh (Rich CLI)
```bash
# 1. Tra cứu quy chế học vụ & chuẩn đầu ra ngoại ngữ (RAG + BM25):
hermes ask "Chuẩn đầu ra ngoại ngữ chương trình tăng cường tiếng Anh ngành Công nghệ thông tin là gì?"

# 2. Tính GPA hệ 10, hệ 4 và kiểm tra cảnh báo học vụ Điều 16:
hermes gpa -c "Giải tích 1:4:8.5" -c "Cấu trúc dữ liệu:4:7.5" -c "Tư duy tính toán:3:9.0"

# 3. Lập lịch ôn thi tự động (Earliest Deadline First - EDF):
hermes plan -e "Toán rời rạc:2026-12-15:4:3" -e "Cấu trúc dữ liệu:2026-12-12:4:2" --hours 6

# 4. Chế độ hội thoại đa lượt (Interactive REPL với SessionManager):
hermes interactive
```

### 3.4 Chạy Kiểm thử Đơn vị (`475 tests`) & Đánh giá Benchmark (`72 cases`)
```bash
# Kiểm tra chuẩn PEP8 (0 lỗi):
flake8 src tests

# Chạy toàn bộ 475 bài kiểm thử đơn vị và tích hợp:
pytest -q

# Chạy kịch bản đánh giá tự động 72 câu hỏi Benchmark:
python tests/benchmark/run_evaluation.py
```
