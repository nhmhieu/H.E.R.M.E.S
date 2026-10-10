# H.E.R.M.E.S – System Architecture (Requirement R5 & Pack 03)
> **HCMUS Educational Resource & Mentoring Expert System**
> Component, Orchestration & Data Flow Architecture

---

## 1. Architectural Philosophy
* **"AI is one computational component, not the architecture."**
* **Deterministic where correctness matters:** Xếp lịch ôn thi, tính GPA và kiểm tra cảnh báo học vụ bắt buộc thực thi bằng giải thuật thuần túy (R2), không dùng LLM đoán mò.
* **AI where language understanding matters:** Nhận diện thực thể trong email/thông báo, tóm tắt diễn giải văn bản và phân loại ngữ nghĩa câu hỏi phức tạp (R4).
* **Two-Tier Routing Strategy:** Tầng 1 (Fast-Path) dùng quy tắc từ khóa/Regex tốc độ cao (< 5ms); Tầng 2 (Slow-Path) dùng LLM phân loại khi câu hỏi mơ hồ.

---

## 2. System Context & Component Diagram

```mermaid
flowchart TD
    User([👤 Sinh viên HCMUS]) -->|Truy vấn / File .ics| Interface[🖥️ Interface Layer: CLI / Streamlit UI]
    
    subgraph S1 [Lớp An toàn & Bảo vệ - Guardrails R7]
        Interface --> Guard[🛡️ Guardrails: Sanitizer & Prompt Injection Defense]
        Guard -->|Phát hiện bẫy / Giải bài tập| Reject([⛔ Từ chối an toàn & Giải thích])
    end

    subgraph S2 [Lớp Điều phối & Định tuyến - Orchestrator R5]
        Guard -->|Hợp lệ| Router{🔀 Intent Router}
        Router -->|Câu hỏi mơ hồ| Clarify([❓ Hỏi lại người dùng Clarification])
    end

    subgraph S3 [Lớp Năng lực Xử lý - Capability Layer]
        Router -->|CALC_GPA / WHAT_IF| Engine1[⚙️ Deterministic Academic Engine R2
Tính GPA, Mức cảnh báo, Dự toán điểm]
        Router -->|SCHEDULING| Engine2[📅 Deterministic Scheduler R2
Interval Scheduling, Phân bổ giờ học]
        Router -->|REGULATION_RAG| Engine3[📚 Knowledge Retrieval Engine R3
BM25 Search + Metadata Provenance]
        Router -->|EXTRACT_DEADLINE| Engine4[🤖 AI Entity Extraction R4
Gemini API / Mock Parser]
    end

    subgraph S4 [Lớp Dữ liệu & Công cụ - Data Layer]
        Engine3 --> DataReg[(📄 Sổ tay & Quy chế HCMUS JSON)]
        Engine4 --> ParserICS[🗓️ iCalendar .ics Parser]
    end

    subgraph S5 [Lớp Kiểm chứng & Phản hồi - Verification & Output]
        Engine1 --> Formatter[🔍 Response Formatter & Verifier]
        Engine2 --> Formatter
        Engine3 --> Formatter
        Engine4 --> Formatter
        Formatter -->|Kèm trích dẫn & Bảng dữ liệu| Interface
    end
```

---

## 3. Detailed Data Flow (Sequence Diagram)

```mermaid
sequenceDiagram
    autonumber
    actor SV as Sinh viên
    participant UI as Giao diện CLI / Web
    participant Guard as Guardrails (R7)
    participant Router as Orchestrator (R5)
    participant Engine as Engines (R2 / R3 / R4)
    participant Data as Data Layer (Quy chế / .ics)

    SV->>UI: Gửi câu hỏi hoặc tải file
    UI->>Guard: Kiểm tra an toàn đầu vào
    alt Vi phạm (Prompt injection / Xin giải bài tập)
        Guard-->>UI: Báo vi phạm, từ chối an toàn (REJECT)
        UI-->>SV: Thông báo lý do từ chối
    else An toàn
        Guard->>Router: Gửi truy vấn đã làm sạch
        Router->>Router: Phân tích Intent (Fast-path / Score)
        
        alt Thiếu thông tin (Mơ hồ)
            Router-->>UI: Yêu cầu bổ sung dữ liệu (CLARIFY)
            UI-->>SV: "Bạn đang học năm mấy và điểm thế nào?"
        else Phân luồng thành công
            Router->>Engine: Kích hoạt engine chuyên trách
            opt Tra cứu quy chế (RAG)
                Engine->>Data: Tìm kiếm BM25 trên cây quy chế
                Data-->>Engine: Trả về đoạn văn bản + Điều, Khoản, Trang
            end
            opt Lập lịch / Tính GPA
                Engine->>Engine: Chạy giải thuật tất định (Greedy / GPA Math)
            end
            Engine-->>UI: Trả về kết quả có cấu trúc (Payload + Citations)
            UI-->>SV: Hiển thị bảng điểm / lịch thi / lời giải đáp
        end
    end
```

---

## 4. Interface Contracts (Quy chuẩn dữ liệu bàn giao giữa các module)

### 4.1 Router Decision (`src/hermes/router/orchestrator.py`)
```python
{
    "intent": "CALC_GPA" | "SCHEDULING" | "REGULATION_RAG" | "EXTRACT_DEADLINE" | "CLARIFY" | "REJECT",
    "confidence": float,        # 0.0 -> 1.0
    "target_engine": str,       # Tên module xử lý
    "extracted_params": dict,   # Tham số bóc tách sơ bộ
    "message": str              # Lời nhắn (khi clarify hoặc reject)
}
```

### 4.2 Academic Status Payload (`src/hermes/engines/academic_calc.py`)
```python
{
    "gpa_scale_10": float,
    "gpa_scale_4": float,
    "total_credits": int,
    "warning_level": int,       # 0: Bình thường, 1: Mức 1, 2: Mức 2, 3: Buộc thôi học
    "warning_status": str,
    "advice": str
}
```

### 4.3 RAG Retrieval Payload (`src/hermes/rag/retriever.py`)
```python
{
    "query": str,
    "citations": [
        {
            "document": str,    # "Quy chế đào tạo tín chỉ 2024"
            "chapter": str,     # "Chương III"
            "article": str,     # "Điều 14"
            "clause": str,      # "Khoản 2"
            "page": int,
            "content": str,
            "score": float
        }
    ]
}
```
