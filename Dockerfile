FROM python:3.11-slim

WORKDIR /app

# تثبيت المتطلبات
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ المشروع
COPY . .

# Railway يعطي PORT تلقائي
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
