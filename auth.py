from functools import wraps
from flask import session, redirect, url_for, flash, request
from werkzeug.security import generate_password_hash, check_password_hash
import pyotp
import re

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return {'error': 'Требуется авторизация'}, 401
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def email_verified_required(f):
    """Декоратор для проверки верификации email"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from models import User, db
        if 'user_id' in session:
            user = User.query.get(session['user_id'])
            if user and not user.email_verified:
                flash('Пожалуйста, подтвердите ваш email адрес', 'warning')
                return redirect(url_for('verify_email_page'))
        return f(*args, **kwargs)
    return decorated_function

def validate_password(password):
    if len(password) < 8:
        return "Пароль должен содержать минимум 8 символов"
    
    if not re.search(r"[A-Z]", password):
        return "Пароль должен содержать заглавные буквы"
    
    if not re.search(r"[a-z]", password):
        return "Пароль должен содержать строчные буквы"
    
    if not re.search(r"\d", password):
        return "Пароль должен содержать цифры"
    
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return "Пароль должен содержать специальные символы"
    
    return None

def validate_username(username):
    if not 3 <= len(username) <= 30:
        return "Имя пользователя должно быть от 3 до 30 символов"
    
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return "Имя пользователя может содержать только буквы, цифры и подчеркивания"
    
    return None

def validate_email(email):
    """Проверка email"""
    if not email:
        return "Email обязателен для регистрации"
    
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        return "Введите корректный email адрес"
    
    return None

def hash_password(password):
    return generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)

def verify_password(hashed_password, password):
    return check_password_hash(hashed_password, password)

def generate_otp_secret():
    return pyotp.random_base32()

def verify_otp_token(secret, token):
    totp = pyotp.TOTP(secret)
    return totp.verify(token, valid_window=1)

def get_otp_uri(username, secret, issuer_name="Messenger"):
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=username,
        issuer_name=issuer_name
    )