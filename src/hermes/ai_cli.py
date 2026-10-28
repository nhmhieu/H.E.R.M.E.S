import argparse
from rich.console import Console
from rich.table import Table
from rich.theme import Theme

# Cấu hình màu sắc cho rich
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green"
})
console = Console(theme=custom_theme)

def display_gpa_result(data):
    """Vẽ bảng hiển thị điểm GPA"""
    table = Table(title="📊 BẢNG TÍNH ĐIỂM GPA - H.E.R.M.E.S", style="info")
    table.add_column("Môn học", justify="left", style="white")
    table.add_column("Tín chỉ", justify="center", style="cyan")
    table.add_column("Điểm", justify="center", style="warning")

    for row in data:
        table.add_row(row["mon_hoc"], str(row["tin_chi"]), str(row["diem"]))

    console.print(table)
    console.print("\n[success]✅ Tính toán hoàn tất![/success]")

# ==========================================
# PHẦN THIẾT LẬP LỆNH TERMINAL (ARGPARSE)
# ==========================================
def main():
    # 1. Khởi tạo chương trình phân tích lệnh
    parser = argparse.ArgumentParser(
        prog="hermes",
        description="Trợ lý Học vụ H.E.R.M.E.S (Giao diện dòng lệnh)"
    )

    # 2. Tạo sub-parser để quản lý các lệnh phụ (như lệnh 'ask')
    subparsers = parser.add_subparsers(dest="command", help="Các lệnh có sẵn")

    # 3. Định nghĩa lệnh 'ask' và tham số 'question'
    ask_parser = subparsers.add_parser("ask", help="Hỏi trợ lý H.E.R.M.E.S một câu hỏi")
    ask_parser.add_argument(
        "question", 
        type=str, 
        help="Nội dung câu hỏi (Nhớ đặt trong dấu ngoặc kép)"
    )

    # 4. Bắt đầu đọc lệnh người dùng gõ vào Terminal
    args = parser.parse_args()

    # 5. Điều hướng logic dựa trên lệnh
    if args.command == "ask":
        console.print(f"\n[info]Bạn vừa hỏi:[/info] {args.question}")
        console.print("[warning]⏳ Đang chuyển câu hỏi đến Router của Thành viên 1...[/warning]\n")
        
        # TODO: Sau này bạn sẽ import hàm của Thành viên 1 vào đây.
        # Ví dụ: ket_qua = router.process(args.question)
        
        # Tạm thời gọi hàm hiển thị bảng giả lập để demo
        mock_data = [
            {"mon_hoc": "Tư duy Tính toán", "tin_chi": 3, "diem": 9.0},
            {"mon_hoc": "Cấu trúc Dữ liệu", "tin_chi": 4, "diem": 8.5}
        ]
        display_gpa_result(mock_data)
        
    else:
        # Nếu gõ sai lệnh hoặc bỏ trống, in ra hướng dẫn sử dụng
        parser.print_help()

if __name__ == "__main__":
    main()