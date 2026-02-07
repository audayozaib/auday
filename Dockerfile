FROM python:3.11-slim

# مجلد العمل
WORKDIR /app

# مكتبات النظام (ضرورية لـ SSL + tgcrypto)
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# نسخ المتطلبات
COPY requirements.txt .

# تثبيت المكتبات
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir tgcrypto

# نسخ المشروع كامل
COPY . .

# تشغيل البوت
CMD ["python", "main.py"]
