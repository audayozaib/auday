FROM python:3.11-slim

# تثبيت FFmpeg فقط (بدون aria2)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && update-ca-certificates

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# إنشاء مجلد مؤقت
RUN mkdir -p /tmp/yt_bot && chmod 777 /tmp/yt_bot

# مستخدم غير root
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser

CMD ["python", "main.py"]
