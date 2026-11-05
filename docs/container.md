# C4 Model – Level 2: Container Diagram (`C4Container`)

```mermaid
C4Container
    title Container Diagram for H.E.R.M.E.S System (Level 2)

    Person(student, "HCMUS Student", "Undergraduate student")

    System_Boundary(hermes_sys, "H.E.R.M.E.S System") {
        Container(cli_app, "CLI Application", "Python, Click, Rich", "Terminal interface")
        Container(orchestrator, "Orchestrator & Safety Core", "Python", "4-layer guardrails & two-tier router")
        Container(web_ui, "Web Dashboard", "Python, Streamlit", "3-tab browser dashboard")

        Container(calc_engine, "Deterministic Engine", "Python", "GPA 10/4, Warning & EDF Scheduler")
        Container(rag_engine, "Hierarchical RAG Engine", "Python, BM25", "Cohort tree filter & BM25 search")
        Container(ai_engine, "AI & .ics Extractor", "Python, urllib", "HermesAIClient & .ics parser")
    }

    Boundary(runtime_tier, "Local Data Store & AI Runtime") {
        ContainerDb(reg_db, "hcmus_regulations.json", "JSON Tree", "17 HCMUS legal documents")
        System_Ext(ollama, "Local Ollama Server", "qwen2.5:3b (localhost:11434)")
    }

    Rel(student, cli_app, "Uses", "CLI")
    Rel(student, web_ui, "Uses", "HTTP")

    Rel(cli_app, orchestrator, "Calls", "orchestrate()")
    Rel(web_ui, orchestrator, "Calls", "orchestrate()")

    Rel(orchestrator, calc_engine, "1. Routes GPA & Schedule")
    Rel(orchestrator, rag_engine, "2. Routes Regulation RAG")
    Rel(orchestrator, ai_engine, "3. Routes Deadlines")

    Rel(rag_engine, reg_db, "Reads JSON tree")
    Rel(ai_engine, ollama, "POST /api/generate")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

---

## Giải thích kiến trúc Level 2 (Container Diagram)

**Mục đích:** Phóng to vào bên trong khối `H.E.R.M.E.S System` để thấy các **khối chức năng cấp cao (Containers)** và luồng dữ liệu đi từ giao diện người dùng xuống tầng xử lý và tầng lưu trữ.

### 1. Tầng Giao diện & Điều phối trung tâm (Hàng 1)
- **`CLI Application` (`src/hermes/cli.py`):** Giao diện dòng lệnh viết bằng `Click` và `Rich`, hỗ trợ các lệnh `ask`, `gpa`, `plan`, `interactive`.
- **`Web Dashboard` (`src/hermes/ui/app.py`):** Giao diện trình duyệt 3 tab viết bằng `Streamlit` dành cho sinh viên phổ thông.
- **`Orchestrator & Safety Core` (`src/hermes/router/orchestrator.py`):** Đặt ở trung tâm vì cả CLI lẫn Web UI đều gọi chung hàm `orchestrate()`. Khối này thực hiện lọc bảo mật 4 lớp và phân loại ý định (Intent Routing) để điều phối xuống 3 Engine chuyên biệt.

### 2. Tầng 3 Engine chuyên biệt (Hàng 2)
- **`Deterministic Engine`:** Xử lý 100% bằng công thức toán học và thuật toán tất định (tính GPA hệ 10/hệ 4, kiểm tra cảnh báo học vụ Điều 16, lập lịch ôn thi EDF). Không gọi AI để loại bỏ hoàn toàn hiện tượng ảo giác số học.
- **`Hierarchical RAG Engine`:** Xử lý tra cứu quy chế học vụ bằng cách lọc cây JSON phân cấp theo khóa/hệ đào tạo và xếp hạng bằng thuật toán BM25.
- **`AI & .ics Extractor`:** Bóc tách thông báo học vụ tự do (qua Ollama) hoặc phân tích file lịch `.ics` xuất từ Moodle.

### 3. Tầng Dữ liệu & AI Runtime (`Local Data Store & AI Runtime`)
- **`hcmus_regulations.json` (`data/regulations/hcmus_regulations.json`):** Kho tri thức JSON cấu trúc cây gồm 17 văn bản pháp quy chính thức của Trường ĐH KHTN.
- **`Local Ollama Server`:** Nhận request `POST /api/generate` từ khối `AI & .ics Extractor`.