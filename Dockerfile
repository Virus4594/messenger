FROM python:3.11-slim

WORKDIR /app

# Устанавливаем системные зависимости, включая libmagic
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

# Для Render.com: используем PORT из переменной окружения
ENV PORT=5000

CMD ["python", "app.py"]
