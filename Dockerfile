FROM python:3.11-slim

WORKDIR /app

# تثبيت المتطلبات الأساسية للنظام (SSL + build tools)
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# تثبيت المتطلبات البايثونية
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ المشروع
COPY . .

# تشغيل التطبيق
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
