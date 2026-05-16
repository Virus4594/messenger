import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Безопасность
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY не задан! Укажите его в .env файле")
    
    WTF_CSRF_ENABLED = True
    WTF_CSRF_SECRET_KEY = SECRET_KEY
    
    # База данных (поддержка PostgreSQL и SQLite)
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL and DATABASE_URL.startswith('postgresql://'):
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        # Если PostgreSQL не указан, используем SQLite (для разработки)
        SQLALCHEMY_DATABASE_URI = DATABASE_URL or 'sqlite:///KDF.db'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Сессия
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = False  # True в продакшене с HTTPS
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Ограничения
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    UPLOAD_FOLDER = 'static/uploads'
    
    # WebSocket
    SOCKETIO_ASYNC_MODE = 'eventlet'
    
    # 2FA
    OTP_SECRET_LENGTH = 32
    
    # Email
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')

    RATELIMIT_ENABLED = False
    RATELIMIT_DEFAULT = None