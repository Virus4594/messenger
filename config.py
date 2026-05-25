import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Секретный ключ
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY не задан! Укажите его в переменных окружения")
    
    # База данных - сначала проверяем Railway, потом локальный Docker
    DATABASE_URL = os.environ.get('DATABASE_URL')
    
    if DATABASE_URL:
        # Railway или другой хостинг
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
        # Если URL начинается с postgres://, меняем на postgresql:// (нужно для SQLAlchemy)
        if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
            SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)
    else:
        # Локальная разработка (Docker)
        SQLALCHEMY_DATABASE_URI = 'postgresql://messenger:messenger321@db:5432/messenger'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Остальные настройки
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
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

    RATELIMIT_ENABLED = False
    RATELIMIT_DEFAULT = None
