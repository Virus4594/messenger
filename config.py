import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Секретный ключ
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY не задан! Укажите его в переменных окружения")
    
    # База данных - сначала проверяем Render/Railway, потом локальный Docker
    DATABASE_URL = os.environ.get('DATABASE_URL')
    
    if DATABASE_URL:
        # Render, Railway или другой хостинг
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
        # Если URL начинается с postgres://, меняем на postgresql:// (нужно для SQLAlchemy)
        if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
            SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)
    else:
        # Локальная разработка (Docker)
        SQLALCHEMY_DATABASE_URI = 'postgresql://messenger:messenger123@db:5432/messenger'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # ========== НОВОЕ: Redis для Socket.IO (нужно для Render) ==========
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379')
    SOCKETIO_MESSAGE_QUEUE = REDIS_URL  # ← ЭТО ВАЖНО ДЛЯ WEBSOCKET
    
    # Остальные настройки
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False') == 'True'  # В продакшене True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    UPLOAD_FOLDER = 'static/uploads'
    
    SOCKETIO_ASYNC_MODE = 'eventlet'
    
    OTP_SECRET_LENGTH = 32
    
    # Email
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')

    # Rate limiting (отключено для продакшена, можно включить если нужно)
    RATELIMIT_ENABLED = os.environ.get('RATELIMIT_ENABLED', 'False') == 'True'
    RATELIMIT_DEFAULT = os.environ.get('RATELIMIT_DEFAULT')
    
    # ========== НОВОЕ: Настройки безопасности для продакшена ==========
    if os.environ.get('FLASK_ENV') == 'production':
        SESSION_COOKIE_SECURE = True  # HTTPS только
        SESSION_COOKIE_HTTPONLY = True
        SESSION_COOKIE_SAMESITE = 'Strict'