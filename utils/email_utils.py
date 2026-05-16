import os
import base64
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from flask import url_for
from itsdangerous import URLSafeTimedSerializer
from config import Config

def init_email(app):
    """Инициализация почтового сервиса (заглушка для совместимости)"""
    pass

def generate_verification_token(email):
    """Генерация токена для верификации email"""
    serializer = URLSafeTimedSerializer(Config.SECRET_KEY)
    return serializer.dumps(email, salt='email-verification')

def verify_verification_token(token, expiration=3600):
    """Проверка токена верификации"""
    serializer = URLSafeTimedSerializer(Config.SECRET_KEY)
    try:
        email = serializer.loads(
            token,
            salt='email-verification',
            max_age=expiration
        )
        return email
    except:
        return None

def send_verification_email(user_email, username):
    """Отправка письма с верификацией - через smtplib напрямую"""
    try:
        token = generate_verification_token(user_email)
        verify_url = url_for('verify_email', token=token, _external=True)
        
        # Создаем письмо
        msg = MIMEMultipart('alternative')
        
        # Тема письма (с поддержкой UTF-8)
        msg['Subject'] = str(Header('Подтверждение регистрации - Messenger', 'utf-8'))
        msg['From'] = Config.MAIL_DEFAULT_SENDER
        msg['To'] = user_email
        
        # HTML версия письма
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body>
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #4a6cf7;">Подтверждение регистрации</h2>
        <p>Здравствуйте, <strong>{username}</strong>!</p>
        <p>Спасибо за регистрацию в Messenger. Для завершения регистрации нажмите на кнопку ниже:</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{verify_url}" style="background-color: #4a6cf7; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px;">Подтвердить email</a>
        </div>
        <p>Или скопируйте ссылку в браузер:</p>
        <p style="background-color: #f0f0f0; padding: 10px; word-break: break-all;">{verify_url}</p>
        <p>Ссылка действительна в течение 1 часа.</p>
        <hr>
        <p style="font-size: 12px; color: #666;">Если вы не регистрировались в Messenger, просто проигнорируйте это письмо.</p>
    </div>
</body>
</html>"""
        
        # Прикрепляем HTML версию
        part = MIMEText(html_content, 'html', 'utf-8')
        msg.attach(part)
        
        # Отправляем письмо через SMTP
        context = ssl.create_default_context()
        
        # Определяем настройки в зависимости от почтового сервера
        if 'gmail.com' in Config.MAIL_SERVER:
            # Gmail
            with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT) as server:
                server.starttls(context=context)
                server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
                server.send_message(msg)
        elif Config.MAIL_USE_SSL:
            # SSL подключение (например, Mail.ru)
            with smtplib.SMTP_SSL(Config.MAIL_SERVER, Config.MAIL_PORT, context=context) as server:
                server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
                server.send_message(msg)
        else:
            # TLS подключение
            with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT) as server:
                server.starttls(context=context)
                server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
                server.send_message(msg)
        
        print(f"✅ Письмо отправлено на {user_email}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка отправки письма: {e}")
        import traceback
        traceback.print_exc()
        return False

def send_password_reset_email(user_email, username):
    """Отправка письма для сброса пароля"""
    try:
        token = generate_verification_token(user_email)
        reset_url = url_for('reset_password', token=token, _external=True)
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = str(Header('Сброс пароля - Messenger', 'utf-8'))
        msg['From'] = Config.MAIL_DEFAULT_SENDER
        msg['To'] = user_email
        
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body>
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #4a6cf7;">Сброс пароля</h2>
        <p>Здравствуйте, <strong>{username}</strong>!</p>
        <p>Вы запросили сброс пароля. Для создания нового пароля нажмите на кнопку ниже:</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{reset_url}" style="background-color: #4a6cf7; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px;">Сбросить пароль</a>
        </div>
        <p>Или скопируйте ссылку в браузер:</p>
        <p style="background-color: #f0f0f0; padding: 10px; word-break: break-all;">{reset_url}</p>
        <p>Ссылка действительна в течение 1 часа.</p>
        <hr>
        <p style="font-size: 12px; color: #666;">Если вы не запрашивали сброс пароля, просто проигнорируйте это письмо.</p>
    </div>
</body>
</html>"""
        
        part = MIMEText(html_content, 'html', 'utf-8')
        msg.attach(part)
        
        context = ssl.create_default_context()
        
        if 'gmail.com' in Config.MAIL_SERVER:
            with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT) as server:
                server.starttls(context=context)
                server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
                server.send_message(msg)
        elif Config.MAIL_USE_SSL:
            with smtplib.SMTP_SSL(Config.MAIL_SERVER, Config.MAIL_PORT, context=context) as server:
                server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
                server.send_message(msg)
        else:
            with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT) as server:
                server.starttls(context=context)
                server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
                server.send_message(msg)
        
        print(f"✅ Письмо для сброса пароля отправлено на {user_email}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка отправки письма: {e}")
        import traceback
        traceback.print_exc()
        return False