# 🤖 H.E.R.M.E.S – HCMUS Educational Resource & Mentoring Expert System

![CI Status](https://img.shields.io/badge/CI-passing-brightgreen)
![Tests](https://img.shields.io/badge/tests-458%20passed-brightgreen)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Local AI](https://img.shields.io/badge/Local%20LLM-Ollama%20(qwen2.5%3A3b)-orange)

## 1. Project Overview
**H.E.R.M.E.S** is an intelligent academic assistant and automated study planning system developed for undergraduate students at **VNUHCM – University of Science (HCMUS)** in course **CSC10014 – Computational Thinking**.

It combines **100% deterministic academic computation** (GPA Scale 10/4, Article 16 academic warning detection, What-If GPA simulation, Earliest Deadline First exam scheduling), **verifiable hierarchical legal document RAG** (17 official HCMUS regulations, 4,739 lines with exact Article/Clause/Page citations), **4-layer fail-closed security guardrails**, and **privacy-preserving local LLM extraction via Ollama (`qwen2.5:3b`)**.

---

## 2. Team Roster (6 Members)

| No. | Student ID | Full Name | Primary Role | GitHub |
| :---: | :---: | :--- | :--- | :--- |
| 1 | `25127331` | **Nguyễn Huỳnh Minh Hiếu** | Team Leader & System Architect (R1, R5) | `@nhmhieu` |
| 2 | `25127152` | **Nghiêm Đình Thuận** | Deterministic & Algorithm Lead (R2) | `@thuannghiem11` |
| 3 | `25127552` | **Đào Ngọc Vinh** | Knowledge Base & RAG Lead (R3) | `@daongocvinh` |
| 4 | `25127471` | **Đào Nhật Quân** | System Safety & Local AI Lead (R7, R4) | `@dnquan14` |
| 5 | `25127168` | **Phan Huỳnh Minh Tuấn** | UI/UX & Client Application Lead (R6) | `@phmtuan2522-coder` |
| 6 | `25127176` | **Hồ Ngọc Như Ý** | QA, Evaluation & Benchmark Lead (R8, R4) | `@hnny712` |

---

## 3. Quickstart Guide

### 3.1 Environment Setup
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
```

### 3.2 Run Terminal CLI (`hermes`)
```powershell
# Ask any regulation, GPA, or deadline question
python -m hermes.cli ask "Chuẩn đầu ra ngoại ngữ chương trình tăng cường tiếng Anh ngành Công nghệ thông tin là gì?"
python -m hermes.cli ask "Tính GPA giúp mình: Giải tích 1 (8.5, 4TC) và C++ (7.0, 3 tín)"

# Direct GPA & Article 16 Warning check
python -m hermes.cli gpa -g 8.5 4 -g 7.0 3 -t 28

# Automated Study Plan table
python -m hermes.cli plan -s "Toan_Roi_Rac" 4 3 -s "Cau_Truc_Du_Lieu" 4 2 -h 6 -d 10
```

### 3.3 Run Interactive Streamlit Web Dashboard
```powershell
streamlit run src/hermes/ui/app.py
```

### 3.4 Optional: Enable Local Ollama LLM (`qwen2.5:3b`)
```powershell
ollama pull qwen2.5:3b
$env:HERMES_AI_MODE="ollama"
$env:OLLAMA_MODEL="qwen2.5:3b"
```

### 3.5 Run Automated Tests & Quality Gates
```powershell
flake8 src tests
black --check src tests
pytest
```
