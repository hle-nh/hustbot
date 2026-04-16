# app.py — đặt cùng thư mục với hustbot-demo.html và thư mục src/

import os
import sys
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from chain import init_chain

app = Flask(__name__)
CORS(app)

# Thư mục chứa file HTML (cùng thư mục với app.py)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Khởi động RAG pipeline 1 lần khi server start
print("Đang khởi động RAG pipeline...")
chat = init_chain()
print("Sẵn sàng!")


# ── Route: mở trình duyệt vào 127.0.0.1:5000 là thấy giao diện ngay ──
@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "hustbot-demo.html")


# ── Route: nhận câu hỏi, trả về JSON ──
@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Thiếu body JSON"}), 400

    question = data.get("question", "").strip()
    if not question:
        return jsonify({"error": "Câu hỏi trống"}), 400

    try:
        result = chat.chat(question)
        return jsonify({
            "answer":  result["answer"],
            "sources": result["sources"],   # [{file, page, preview}]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Route: kiểm tra server còn sống không ──
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    print("\n📌 Mở trình duyệt vào: http://127.0.0.1:5000\n")
    app.run(host="127.0.0.1", port=5000, debug=False)