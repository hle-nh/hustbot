FROM python:3.12-slim

# Cài đặt công cụ cơ bản
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy thư mục chroma_db và data nếu có (để container có sẵn data)
# Có thể mount từ bên ngoài, nhưng tuỳ nhu cầu.
# Ở đây ta map qua volume cho an toàn.

# Cài requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Chạy server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
