FROM python:3.11-slim

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

# Для Render: используем PORT из переменной окружения
ENV PORT=5000

# Используем Gunicorn с eventlet для WebSocket
CMD sh -c "flask db upgrade || (flask db init && flask db migrate -m 'initial' && flask db upgrade) && gunicorn app:app --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT"