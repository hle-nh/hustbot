# main.py

import os
import sys
import time
from dotenv import load_dotenv

from src.chain import init_chain

load_dotenv()

# ==============================================
# HIỂN THỊ
# ==============================================

BANNER = """
╔══════════════════════════════════════════════╗
║       HUST RAG — Trợ lý Tư vấn Học vụ        ║
║         Đại học Bách khoa Hà Nội             ║
╚══════════════════════════════════════════════╝
"""

HELP_TEXT = """
📌 Các lệnh đặc biệt:
  /help     — hiển thị trợ giúp này
  /clear    — xóa lịch sử hội thoại
  /history  — xem lại các câu hỏi đã hỏi
  /quit     — thoát chương trình
"""

def print_banner():
    print(BANNER)
    print("💡 Bạn có thể hỏi về: đăng ký tín chỉ, học bổng,")
    print("   xét tốt nghiệp, cảnh báo học vụ, đề cương môn học...")
    print("   Gõ /help để xem thêm lệnh.\n")


def print_thinking():
    """Hiển thị animation chờ trong khi RAG đang xử lý."""
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    for _ in range(15):
        for frame in frames:
            sys.stdout.write(f"\r{frame} Đang tìm kiếm tài liệu...")
            sys.stdout.flush()
            time.sleep(0.08)
    sys.stdout.write("\r" + " " * 40 + "\r")
    sys.stdout.flush()


def print_answer(result: dict):
    """In câu trả lời và nguồn trích dẫn."""

    print("\n" + "─" * 50)
    print("💬 Trả lời:\n")
    print(result["answer"])

    # In nguồn tài liệu
    if result.get("sources"):
        print("\n📚 Tài liệu tham khảo:")
        seen = set()
        for src in result["sources"]:
            key = f"{src['file']}_{src['page']}"
            if key not in seen:
                seen.add(key)
                print(f"   • {src['file']} — trang {src['page']}")

    print("─" * 50 + "\n")


def print_history(history: list):
    """In lại toàn bộ lịch sử hội thoại."""
    if not history:
        print("\n📭 Chưa có câu hỏi nào.\n")
        return

    print(f"\n📜 Lịch sử hội thoại ({len(history)} câu):\n")
    for i, item in enumerate(history, 1):
        print(f"  {i}. {item['question']}")
    print()


# ==============================================
# XỬ LÝ LỆNH ĐẶC BIỆT
# ==============================================

def handle_command(cmd: str, chat) -> bool:
    """
    Xử lý các lệnh bắt đầu bằng /.
    Trả về True nếu nên thoát vòng lặp.
    """
    cmd = cmd.strip().lower()

    if cmd == "/help":
        print(HELP_TEXT)

    elif cmd == "/clear":
        chat.clear_history()
        print("✅ Đã xóa lịch sử hội thoại.\n")

    elif cmd == "/history":
        print_history(chat.history)

    elif cmd in ("/quit", "/exit", "/q"):
        print("\n👋 Tạm biệt! Chúc bạn học tốt.\n")
        return True

    else:
        print(f"❓ Lệnh không hợp lệ: {cmd}")
        print("   Gõ /help để xem danh sách lệnh.\n")

    return False


# ==============================================
# VÒNG LẶP HỎI ĐÁP CHÍNH
# ==============================================

def chat_loop(chat):
    """Vòng lặp chính — đọc input, xử lý, in kết quả."""

    while True:
        try:
            # Đọc input từ user
            user_input = input("❓ Câu hỏi: ").strip()

            # Bỏ qua input rỗng
            if not user_input:
                continue

            # Xử lý lệnh đặc biệt
            if user_input.startswith("/"):
                should_exit = handle_command(user_input, chat)
                if should_exit:
                    break
                continue

            # Hiển thị animation chờ
            print()
            start_time = time.time()

            # Gọi RAG pipeline
            result = chat.chat(user_input)

            elapsed = time.time() - start_time

            # In kết quả
            print_answer(result)
            print(f"⏱  Thời gian xử lý: {elapsed:.1f}s\n")

        except KeyboardInterrupt:
            # Ctrl+C
            print("\n\n👋 Tạm biệt! Chúc bạn học tốt.\n")
            break

        except Exception as e:
            print(f"\n⚠️  Lỗi: {e}")
            print("   Vui lòng thử lại.\n")


# ==============================================
# MAIN
# ==============================================

def main():
    print_banner()

    # Kiểm tra ChromaDB đã được tạo chưa
    chroma_dir = os.getenv("CHROMA_DIR", "./chroma_db")
    if not os.path.exists(chroma_dir):
        print("❌ Chưa có vector database!")
        print(f"   Hãy chạy lệnh sau trước:\n")
        print(f"   python src/ingest.py\n")
        sys.exit(1)

    # Khởi động pipeline
    print("⏳ Đang khởi động hệ thống...\n")
    chat = init_chain()

    # Bắt đầu vòng lặp hỏi đáp
    chat_loop(chat)


if __name__ == "__main__":
    main()