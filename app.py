from operator import or_, and_
import os
import magic
import json
import secrets
from PIL import Image
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, g
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf import CSRFProtect
from models import Reaction, db, User, Post, Comment, Message, Notification, Friendship, ChatGroup, GroupMember, GroupMessage, Reaction
from flask_migrate import Migrate
import qrcode
from io import BytesIO
import base64
from functools import wraps

from config import Config
from auth import (
    login_required, email_verified_required, validate_password, validate_username, validate_email,
    hash_password, verify_password, generate_otp_secret,
    verify_otp_token, get_otp_uri
)
from utils.email_utils import init_email, send_verification_email, send_password_reset_email, verify_verification_token
from utils.encryption import E2EEncryption
from admin import admin_bp

# Инициализация приложения
app = Flask(__name__)
app.config.from_object(Config)
app.register_blueprint(admin_bp)
os.environ['FLASK_ENV'] = 'development'
# Расширения
csrf = CSRFProtect(app)
#csrf.exempt(admin_bp)
db.init_app(app)
migrate = Migrate(app, db)
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)
limiter = Limiter(app=app, key_func=get_remote_address)

# Инициализация почты
init_email(app)

# ========== ГЛОБАЛЬНАЯ ЗАЩИТА ВСЕХ МАРШРУТОВ ==========

# Публичные маршруты (не требуют авторизации)
PUBLIC_ENDPOINTS = [
    'index', 'login', 'register', 'static', 
    'verify_email', 'verify_email_page', 'resend_verification',
    'reset_password', 'forgot_password', 'verify_2fa_login'
]

@app.before_request
def global_auth_check():
    """Глобальная проверка авторизации для всех маршрутов"""
    # Пропускаем статические файлы
    if request.endpoint and request.endpoint.startswith('static'):
        return None
    
    # Проверяем, требуется ли авторизация для этого маршрута
    if request.endpoint not in PUBLIC_ENDPOINTS:
        if 'user_id' not in session:
            # Для API запросов возвращаем JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.path.startswith('/api/'):
                return jsonify({'error': 'Требуется авторизация'}), 401
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('login'))
        
        # Проверяем, не забанен ли пользователь
        user = db.session.get(User, session['user_id'])
        if user and user.is_banned:
            session.clear()
            flash('Ваш аккаунт заблокирован. Обратитесь к администратору.', 'error')
            return redirect(url_for('login'))
        
        # Сохраняем пользователя в g для быстрого доступа
        g.current_user = user

@app.before_request
def update_last_seen():
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        if user:
            user.last_seen = datetime.now(timezone.utc)
            db.session.commit()


# ========== WEBSOCKET ЗАЩИТА ==========

def socket_authenticated():
    """Проверка авторизации для WebSocket"""
    return 'user_id' in session

def get_socket_user():
    """Получение пользователя из сессии WebSocket"""
    if 'user_id' in session:
        return db.session.get(User, session['user_id'])
    return None

def save_avatar(user_id, file):
    """Сохраняет аватарку с проверкой MIME-типа"""
    if not file or file.filename == '':
        return None
    
    # Разрешённые MIME-типы
    ALLOWED_MIME = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
    
    # Читаем первые 1024 байта для определения типа
    file_content = file.read(1024)
    mime = magic.from_buffer(file_content, mime=True)
    file.seek(0)  # возвращаем указатель в начало
    
    if mime not in ALLOWED_MIME:
        flash('Недопустимый формат изображения. Разрешены: JPEG, PNG, GIF, WebP', 'error')
        return None
    
    # Проверка расширения (дополнительная защита)
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_EXTENSIONS:
        flash('Недопустимое расширение файла', 'error')
        return None
    
    # Генерируем имя файла
    filename = f'user_{user_id}_{int(datetime.now(timezone.utc).timestamp())}.{ext}'
    
    # Пути сохранения
    avatar_path = os.path.join('static/uploads/avatars', filename)
    thumb_path = os.path.join('static/uploads/avatars/thumb', f'thumb_{filename}')
    
    # Сохраняем оригинал
    file.save(avatar_path)
    
    # Создаём миниатюру (200x200)
    try:
        img = Image.open(avatar_path)
        # Дополнительно проверяем, что PIL может открыть изображение
        img.verify()  # проверка целостности
        img = Image.open(avatar_path)  # переоткрываем после verify
        img.thumbnail((200, 200), Image.Resampling.LANCZOS)
        img.save(thumb_path, optimize=True, quality=85)
    except Exception as e:
        print(f"Ошибка создания миниатюры: {e}")
        # Если не удалось создать миниатюру, использовать оригинал
        thumb_path = avatar_path
    
    return filename

# ========================
# Роуты аутентификации
# ========================

@app.route('/')
def index():
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        if user and not user.email_verified:
            return redirect(url_for('verify_email_page'))
        return redirect(url_for('feed'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def register():
    if request.method == 'GET':
        return render_template('auth/register.html')
    
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')
    
    if not username or not email or not password:
        flash('Заполните все поля', 'error')
        return redirect(url_for('register'))
    
    if password != confirm_password:
        flash('Пароли не совпадают', 'error')
        return redirect(url_for('register'))
    
    username_error = validate_username(username)
    if username_error:
        flash(username_error, 'error')
        return redirect(url_for('register'))
    
    email_error = validate_email(email)
    if email_error:
        flash(email_error, 'error')
        return redirect(url_for('register'))
    
    password_error = validate_password(password)
    if password_error:
        flash(password_error, 'error')
        return redirect(url_for('register'))
    
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        flash('Имя пользователя уже занято', 'error')
        return redirect(url_for('register'))
    
    existing_email = User.query.filter_by(email=email).first()
    if existing_email:
        flash('Email уже зарегистрирован', 'error')
        return redirect(url_for('register'))
    
    try:
        hashed_password = hash_password(password)
        new_user = User(
            username=username,
            email=email,
            password_hash=hashed_password,
            email_verified=True,
            created_at=datetime.now(timezone.utc)
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        session['user_id'] = new_user.id
        flash('Регистрация успешна! Добро пожаловать в Messenger!', 'success')
        return redirect(url_for('feed'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка регистрации: {str(e)}', 'error')
        return redirect(url_for('register'))

@app.route('/verify-email-page')
def verify_email_page():
    if 'pending_verification_user_id' not in session and 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session.get('pending_verification_user_id') or session.get('user_id')
    user = db.session.get(User, user_id)
    
    if user and user.email_verified:
        flash('Email уже подтвержден', 'success')
        if 'pending_verification_user_id' in session:
            session.pop('pending_verification_user_id')
            session['user_id'] = user.id
        return redirect(url_for('feed'))
    
    return render_template('auth/verify_email.html', email=user.email if user else None)

@app.route('/verify-email/<token>')
def verify_email(token):
    email = verify_verification_token(token)
    
    if not email:
        flash('Ссылка подтверждения недействительна или истекла', 'error')
        return redirect(url_for('register'))
    
    user = User.query.filter_by(email=email).first()
    
    if not user:
        flash('Пользователь не найден', 'error')
        return redirect(url_for('register'))
    
    if user.email_verified:
        flash('Email уже подтвержден', 'info')
    else:
        user.email_verified = True
        db.session.commit()
        flash('Email успешно подтвержден! Теперь вы можете войти.', 'success')
    
    session.pop('pending_verification_user_id', None)
    session['user_id'] = user.id
    
    return redirect(url_for('feed'))

@app.route('/resend-verification', methods=['POST'])
@limiter.limit("3 per hour")
def resend_verification():
    user_id = session.get('pending_verification_user_id') or session.get('user_id')
    
    if not user_id:
        flash('Сессия истекла', 'error')
        return redirect(url_for('register'))
    
    user = db.session.get(User, user_id)
    
    if not user:
        flash('Пользователь не найден', 'error')
        return redirect(url_for('register'))
    
    if user.email_verified:
        flash('Email уже подтвержден', 'success')
        if 'pending_verification_user_id' in session:
            session.pop('pending_verification_user_id')
            session['user_id'] = user.id
        return redirect(url_for('feed'))
    
    if send_verification_email(user.email, user.username):
        flash('Письмо с подтверждением отправлено повторно', 'success')
    else:
        flash('Не удалось отправить письмо. Попробуйте позже.', 'error')
    
    return redirect(url_for('verify_email_page'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        
        if not email:
            flash('Введите email', 'error')
            return redirect(url_for('forgot_password'))
        
        user = User.query.filter_by(email=email).first()
        
        if user:
            send_password_reset_email(email, user.username)
            flash('Инструкции по сбросу пароля отправлены на ваш email', 'success')
        else:
            flash('Если аккаунт с таким email существует, инструкции отправлены', 'info')
        
        return redirect(url_for('login'))
    
    return render_template('auth/forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    email = verify_verification_token(token)
    
    if not email:
        flash('Ссылка сброса пароля недействительна или истекла', 'error')
        return redirect(url_for('login'))
    
    user = User.query.filter_by(email=email).first()
    
    if not user:
        flash('Пользователь не найден', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if password != confirm_password:
            flash('Пароли не совпадают', 'error')
            return redirect(url_for('reset_password', token=token))
        
        password_error = validate_password(password)
        if password_error:
            flash(password_error, 'error')
            return redirect(url_for('reset_password', token=token))
        
        user.password_hash = hash_password(password)
        db.session.commit()
        
        flash('Пароль успешно изменен! Теперь вы можете войти.', 'success')
        return redirect(url_for('login'))
    
    return render_template('auth/reset_password.html')

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    if request.method == 'GET':
        return render_template('auth/login.html')
    
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    
    if not username or not password:
        flash('Заполните все поля', 'error')
        return redirect(url_for('login'))
    
    user = User.query.filter_by(username=username).first()
    
    if not user or not verify_password(user.password_hash, password):
        flash('Неверное имя пользователя или пароль', 'error')
        return redirect(url_for('login'))
    
    # Проверка бана
    if user.is_banned:
        flash('Ваш аккаунт заблокирован. Обратитесь к администратору.', 'error')
        return redirect(url_for('login'))
    
    if not user.email_verified:
        session['pending_verification_user_id'] = user.id
        flash('Пожалуйста, подтвердите ваш email адрес', 'warning')
        return redirect(url_for('verify_email_page'))
    
    if user.is_2fa_enabled:
        session['pre_2fa_user_id'] = user.id
        return redirect(url_for('verify_2fa_login'))
    
    session['user_id'] = user.id
    user.last_seen = datetime.now(timezone.utc)
    user.is_online = True
    db.session.commit()
    
    flash('Вход выполнен успешно!', 'success')
    return redirect(url_for('feed'))

@app.route('/logout')
def logout():
    user_id = session.get('user_id')
    if user_id:
        user = db.session.get(User, user_id)
        if user:
            user.is_online = False
            user.last_seen = datetime.now(timezone.utc)
            db.session.commit()
    
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))

@app.route('/demo/db-check')
@login_required
def demo_db_check():
    # Доступ только владельцу
    user = db.session.get(User, session.get('user_id'))
    if not user or user.role != 'owner':
        return "Доступ запрещён", 403
    
    # Получаем последние 10 сообщений
    messages = Message.query.order_by(Message.id.desc()).limit(10).all()
    
    # Формируем HTML-таблицу
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Проверка шифрования в БД</title>
        <style>
            body { font-family: monospace; padding: 20px; background: #1e1e1e; color: #fff; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { padding: 10px; border: 1px solid #444; text-align: left; word-break: break-all; }
            th { background: #333; }
            .encrypted { background: #2d4a2d; padding: 5px; border-radius: 4px; display: block; }
        </style>
    </head>
    <body>
        <h1>🔍 Проверка шифрования в базе данных</h1>
        <p>✅ Все сообщения хранятся ТОЛЬКО в зашифрованном виде.<br>
        ✅ Сервер НЕ видит исходный текст.</p>
        <table>
            <tr>
                <th>ID</th>
                <th>Отправитель</th>
                <th>Получатель</th>
                <th>Зашифрованное содержимое</th>
                <th>Флаг шифрования</th>
                <th>Время</th>
            </tr>
    """
    
    for msg in messages:
        sender = db.session.get(User, msg.sender_id)
        receiver = db.session.get(User, msg.receiver_id)
        encrypted_preview = msg.encrypted_content[:80] + "..." if msg.encrypted_content and len(msg.encrypted_content) > 80 else msg.encrypted_content
        
        html += f"""
            <tr>
                <td>{msg.id}</td>
                <td>{sender.username if sender else '?'}</td>
                <td>{receiver.username if receiver else '?'}</td>
                <td><span class="encrypted">{encrypted_preview}</span></td>
                <td>{'✅ E2EE' if msg.is_encrypted else '❌ НЕ ЗАШИФРОВАНО'}</td>
                <td>{msg.created_at.strftime('%H:%M:%S')}</td>
            </tr>
        """
    
    html += "</table></body></html>"
    return html
    
@app.route('/verify_2fa_login', methods=['GET', 'POST'])
def verify_2fa_login():
    if 'pre_2fa_user_id' not in session:
        return redirect(url_for('login'))
    
    user = db.session.get(User, session['pre_2fa_user_id'])
    
    if request.method == 'POST':
        token = request.form.get('token', '').strip()
        
        if not token or not verify_otp_token(user.otp_secret, token):
            flash('Неверный код аутентификации', 'error')
            return render_template('auth/verify_2fa.html')
        
        session['user_id'] = user.id
        session.pop('pre_2fa_user_id', None)
        user.last_seen = datetime.now(timezone.utc)
        user.is_online = True
        db.session.commit()
        
        flash('Вход выполнен успешно!', 'success')
        return redirect(url_for('feed'))
    
    return render_template('auth/verify_2fa.html')


# ========================
# 2FA Роуты
# ========================

@app.route('/enable_2fa')
@login_required
def enable_2fa():
    user = db.session.get(User, session['user_id'])
    
    if not user.otp_secret:
        user.otp_secret = generate_otp_secret()
        db.session.commit()
    
    otp_uri = get_otp_uri(user.username, user.otp_secret)
    qr = qrcode.make(otp_uri)
    
    buffered = BytesIO()
    qr.save(buffered, format="PNG")
    qr_base64 = base64.b64encode(buffered.getvalue()).decode()
    
    return render_template('profile/settings.html', 
                         qr_code=qr_base64,
                         otp_secret=user.otp_secret)

@app.route('/disable_2fa', methods=['POST'])
@login_required
def disable_2fa():
    user = db.session.get(User, session['user_id'])
    user.otp_secret = None
    user.is_2fa_enabled = False
    db.session.commit()
    
    flash('Двухфакторная аутентификация отключена', 'success')
    return redirect(url_for('profile'))

@app.route('/verify_2fa', methods=['POST'])
@login_required
def verify_2fa():
    user = db.session.get(User, session['user_id'])
    token = request.form.get('token', '').strip()
    
    if not token or not verify_otp_token(user.otp_secret, token):
        flash('Неверный код аутентификации', 'error')
        return redirect(url_for('enable_2fa'))
    
    user.is_2fa_enabled = True
    db.session.commit()
    
    flash('Двухфакторная аутентификация включена', 'success')
    return redirect(url_for('profile'))


# ========================
# Профиль и настройки
# ========================

@app.route('/profile')
@login_required
def profile():
    user = db.session.get(User, session['user_id'])
    recent_posts = Post.query.filter_by(user_id=user.id).order_by(Post.created_at.desc()).limit(5).all()
    return render_template('profile/profile.html', 
                         user=user, 
                         recent_posts=recent_posts,
                         current_user=user)

@app.route('/profile/<username>')
@login_required
def user_profile(username):
    current_user_id = session['user_id']
    current_user = db.session.get(User, current_user_id)
    user = User.query.filter_by(username=username).first_or_404()
    
    are_friends = Friendship.query.filter(
        (
            (Friendship.user_id == current_user_id) & 
            (Friendship.friend_id == user.id) & 
            (Friendship.status == 'accepted')
        ) | (
            (Friendship.user_id == user.id) & 
            (Friendship.friend_id == current_user_id) & 
            (Friendship.status == 'accepted')
        )
    ).first() is not None
    
    recent_posts = Post.query.filter_by(user_id=user.id).order_by(Post.created_at.desc()).limit(5).all()
    
    return render_template('profile/profile.html', 
                         user=user, 
                         is_friend=are_friends,
                         recent_posts=recent_posts,
                         current_user=current_user)

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    user = db.session.get(User, session['user_id'])
    
    if request.method == 'POST':
        new_username = request.form.get('username', '').strip()
        
        if new_username and new_username != user.username:
            existing = User.query.filter_by(username=new_username).first()
            if existing:
                flash('Имя пользователя уже занято', 'error')
            else:
                user.username = new_username
                db.session.commit()
                flash('Имя пользователя обновлено', 'success')
        
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        
        if current_password and new_password:
            if verify_password(user.password_hash, current_password):
                password_error = validate_password(new_password)
                if password_error:
                    flash(password_error, 'error')
                else:
                    user.password_hash = hash_password(new_password)
                    db.session.commit()
                    flash('Пароль изменен', 'success')
            else:
                flash('Текущий пароль неверен', 'error')
    
    return render_template('profile/settings.html', user=user)


# ========================
# Лента и посты (ВСЕ С @login_required)
# ========================

@app.route('/feed')
@login_required
def feed():
    user_id = session['user_id']
    
    friend_ids = [user_id]
    
    friendships_as_user = Friendship.query.filter(
        Friendship.user_id == user_id,
        Friendship.status == 'accepted'
    ).all()
    
    friendships_as_friend = Friendship.query.filter(
        Friendship.friend_id == user_id,
        Friendship.status == 'accepted'
    ).all()
    
    for fs in friendships_as_user:
        friend_ids.append(fs.friend_id)
    
    for fs in friendships_as_friend:
        friend_ids.append(fs.user_id)
    
    friend_ids = list(set(friend_ids))
    
    posts = Post.query.filter(Post.user_id.in_(friend_ids)) \
                      .order_by(Post.created_at.desc()) \
                      .limit(255) \
                      .all()
    
    return render_template('posts/feed.html', posts=posts)

@app.route('/create_post', methods=['GET', 'POST'])
@login_required
def create_post():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        
        if not title or not content:
            flash('Заполните все поля', 'error')
            return redirect(url_for('create_post'))
        
        new_post = Post(
            title=title,
            content=content,
            user_id=session['user_id'],
            created_at=datetime.now(timezone.utc)
        )
        
        db.session.add(new_post)
        db.session.commit()
        
        flash('Пост опубликован', 'success')
        return redirect(url_for('feed'))
    
    return render_template('posts/create_post.html')

@app.route('/post/<int:post_id>')
@login_required
def post_detail(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template('posts/post_detail.html', post=post)

@app.route('/like_post/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    user = db.session.get(User, session['user_id'])
    
    if user in post.likes:
        post.likes.remove(user)
        liked = False
    else:
        post.likes.append(user)
        liked = True
        
        if post.author.id != user.id:
            notification = Notification(
                user_id=post.author.id,
                type='like',
                content=f'{user.username} понравился ваш пост',
                related_id=post.id,
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(notification)
    
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'liked': liked,
            'likes_count': len(post.likes)
        })
    
    return redirect(request.referrer or url_for('feed'))

@app.route('/post/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    
    # Проверка прав: только автор может редактировать
    if post.user_id != session['user_id']:
        flash('Вы не можете редактировать этот пост', 'error')
        return redirect(url_for('feed'))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        
        if not title or not content:
            flash('Заполните все поля', 'error')
            return redirect(url_for('edit_post', post_id=post_id))
        
        post.title = title
        post.content = content
        post.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        
        flash('Пост обновлен!', 'success')
        return redirect(url_for('feed'))
    
    return render_template('posts/edit_post.html', post=post)

@app.route('/comment/<int:post_id>', methods=['POST'])
@login_required
def add_comment(post_id):
    post = Post.query.get_or_404(post_id)
    content = request.form.get('content', '').strip()
    
    if not content:
        flash('Комментарий не может быть пустым', 'error')
        return redirect(url_for('post_detail', post_id=post_id))
    
    comment = Comment(
        content=content,
        user_id=session['user_id'],
        post_id=post_id,
        created_at=datetime.now(timezone.utc)
    )
    
    db.session.add(comment)
    
    if post.author.id != session['user_id']:
        user = db.session.get(User, session['user_id'])
        notification = Notification(
            user_id=post.author.id,
            type='comment',
            content=f'{user.username} прокомментировал ваш пост',
            related_id=post.id,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(notification)
    
    db.session.commit()
    
    return redirect(url_for('post_detail', post_id=post_id))

@app.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    
    # Проверка прав: автор, админ или модератор могут удалить
    user = db.session.get(User, session['user_id'])
    
    if post.user_id != session['user_id'] and user.role not in ['admin', 'moderator', 'owner']:
        flash('Вы не можете удалить этот пост', 'error')
        return redirect(url_for('feed'))
    
    db.session.delete(post)
    db.session.commit()
    
    flash('Пост удален', 'success')
    return redirect(request.referrer or url_for('feed'))

# ========================
# Друзья (ВСЕ С @login_required)
# ========================

@app.route('/search')
@login_required
def search():
    try:
        query = request.args.get('q', '').strip()
        current_user_id = session['user_id']
        current_user = db.session.get(User, current_user_id)
        
        users = []
        if query:
            users = User.query.filter(
                User.username.ilike(f'%{query}%'),
                User.id != current_user_id
            ).limit(30).all()
        
        return render_template('friend/search.html', 
                             users=users, 
                             query=query,
                             current_user=current_user)
    except Exception as e:
        print(f"Ошибка в поиске: {e}")
        return render_template('friend/search.html', users=[], query='', current_user=None), 500

@app.route('/friends')
@login_required
def friends():
    current_user = db.session.get(User, session['user_id'])
    if not current_user:
        return redirect(url_for('login'))
    
    current_user_id = current_user.id
    
    incoming_friendships = Friendship.query.filter(
        Friendship.friend_id == current_user_id,
        Friendship.status == 'pending'
    ).all()
    
    incoming_requests = []
    for friendship in incoming_friendships:
        user = db.session.get(User, friendship.user_id)
        if user:
            incoming_requests.append(user)
    
    outgoing_friendships = Friendship.query.filter(
        Friendship.user_id == current_user_id,
        Friendship.status == 'pending'
    ).all()
    
    outgoing_requests = []
    for friendship in outgoing_friendships:
        user = db.session.get(User, friendship.friend_id)
        if user:
            outgoing_requests.append(user)
    
    friendships_as_user = Friendship.query.filter(
        Friendship.user_id == current_user_id,
        Friendship.status == 'accepted'
    ).all()
    
    friendships_as_friend = Friendship.query.filter(
        Friendship.friend_id == current_user_id,
        Friendship.status == 'accepted'
    ).all()
    
    friends_list = []
    friend_ids = set()
    
    for friendship in friendships_as_user:
        friend = db.session.get(User, friendship.friend_id)
        if friend and friend.id not in friend_ids:
            friends_list.append(friend)
            friend_ids.add(friend.id)
    
    for friendship in friendships_as_friend:
        friend = db.session.get(User, friendship.user_id)
        if friend and friend.id not in friend_ids:
            friends_list.append(friend)
            friend_ids.add(friend.id)
    
    return render_template('friend/friends.html',
                         incoming_requests=incoming_requests,
                         outgoing_requests=outgoing_requests,
                         friends=friends_list,
                         current_user=current_user)

@app.route('/accept_friend/<int:friend_id>', methods=['POST'])
@login_required
def accept_friend(friend_id):
    try:
        current_user_id = session['user_id']
        current_user = db.session.get(User, current_user_id)
        friend = User.query.get_or_404(friend_id)
        
        friendship = Friendship.query.filter(
            (Friendship.user_id == friend_id) &
            (Friendship.friend_id == current_user_id) &
            (Friendship.status == 'pending')
        ).first()
        
        if friendship:
            friendship.status = 'accepted'
            
            # Уведомление для друга, что его приняли
            notification = Notification(
                user_id=friend_id,
                type='friend_accept',
                content=f'{current_user.username} принял ваш запрос в друзья',
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(notification)
            db.session.commit()
            
            flash('Запрос принят', 'success')
            
            # WebSocket уведомление
            socketio.emit('notification_update', {
                'user_id': friend_id,
                'message': f'{current_user.username} принял вас в друзья'
            }, room=f'user_{friend_id}')
            
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка: {str(e)}', 'error')
        
    return redirect(url_for('friends'))

@app.route('/cancel_friend_request/<int:user_id>', methods=['POST'])
@login_required
def cancel_friend_request(user_id):
    current_user_id = session['user_id']
    
    friendship = Friendship.query.filter(
        (Friendship.user_id == current_user_id) &
        (Friendship.friend_id == user_id) &
        (Friendship.status == 'pending')
    ).first()
    
    if friendship:
        db.session.delete(friendship)
        db.session.commit()
        flash('Запрос отменен', 'info')
    else:
        flash('Запрос не найден', 'error')
    
    user = db.session.get(User, user_id)
    return redirect(url_for('user_profile', username=user.username))

@app.route('/reject_friend/<int:friend_id>', methods=['POST'])
@login_required 
def reject_friend(friend_id):
    try:
        current_user_id = session['user_id']
        
        friendship = Friendship.query.filter(
            (Friendship.user_id == friend_id) &
            (Friendship.friend_id == current_user_id) &
            (Friendship.status == 'pending')
        ).first()
        
        if friendship:
            db.session.delete(friendship)
            db.session.commit()
            flash('Запрос отклонен', 'info')
        else:
            flash('Запрос не найден', 'error')
            
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка: {str(e)}', 'error')
        
    return redirect(url_for('friends'))

@app.route('/add_friend/<int:user_id>', methods=['POST'])
@login_required
def add_friend(user_id):
    user_to_add = User.query.get_or_404(user_id)
    current_user_id = session['user_id']
    current_user = db.session.get(User, current_user_id)
    
    if current_user_id == user_id:
        flash('Нельзя отправить запрос самому себе', 'error')
        return redirect(url_for('profile', username=user_to_add.username))
    
    existing_friendship = Friendship.query.filter(
        or_(
            and_(Friendship.user_id == current_user_id, Friendship.friend_id == user_id),
            and_(Friendship.user_id == user_id, Friendship.friend_id == current_user_id)
        )
    ).first()
    
    if existing_friendship:
        if existing_friendship.status == 'pending':
            flash('Запрос уже отправлен', 'warning')
        elif existing_friendship.status == 'accepted':
            flash('Вы уже друзья', 'info')
        return redirect(url_for('profile', username=user_to_add.username))
    
    new_friendship = Friendship(
        user_id=current_user_id,
        friend_id=user_id,
        status='pending',
        action_user_id=current_user_id,
        created_at=datetime.now(timezone.utc)
    )
    
    db.session.add(new_friendship)
    db.session.commit()
    
    notification = Notification(
        user_id=user_id,
        sender_id=current_user_id,
        type='friend_request',
        content=f'Пользователь {current_user.username} отправил вам запрос на дружбу',
        is_read=False,
        created_at=datetime.now(timezone.utc),
        related_id=new_friendship.id
    )
    
    db.session.add(notification)
    db.session.commit()
    
    flash('Запрос в друзья отправлен', 'success')
    return redirect(url_for('profile', username=user_to_add.username))

@app.route('/remove_friend/<int:friend_id>', methods=['POST'])
@login_required
def remove_friend(friend_id):
    try:
        current_user_id = session['user_id']
        
        friendships = Friendship.query.filter(
            or_(
                and_(Friendship.user_id == current_user_id, Friendship.friend_id == friend_id),
                and_(Friendship.user_id == friend_id, Friendship.friend_id == current_user_id)
            )
        ).all()
        
        for friendship in friendships:
            db.session.delete(friendship)
        
        db.session.commit()
        
        friend = db.session.get(User, friend_id)
        flash(f'👋 {friend.username} удален из друзей', 'info')
        
    except Exception as e:
        db.session.rollback()
        print(f"Ошибка удаления друга: {e}")
        flash('Ошибка при удалении из друзей', 'error')
    
    return redirect(url_for('friends'))


# ========================
# Уведомления
# ========================

@app.route('/notifications')
@login_required
def notifications():
    try:
        user_id = session['user_id']
        user = db.session.get(User, user_id)
        
        if not user:
            flash('Пользователь не найден', 'error')
            return redirect(url_for('login'))
        
        notifications_list = Notification.query.filter_by(
            user_id=user_id
        ).order_by(Notification.created_at.desc()).all()
        
        notifications_with_senders = []
        for notification in notifications_list:
            sender = None
            if notification.sender_id:
                sender = db.session.get(User, notification.sender_id)
            
            notifications_with_senders.append({
                'notification': notification,
                'sender': sender
            })
        
        for notification in notifications_list:
            if not notification.is_read:
                notification.is_read = True
        
        db.session.commit()
        
        return render_template('notifications.html', 
                             notifications=notifications_with_senders,
                             current_user=user)
        
    except Exception as e:
        print(f"Ошибка в notifications: {str(e)}")
        flash(f'Ошибка загрузки уведомлений: {str(e)}', 'error')
        return redirect(url_for('feed'))

@app.route('/notifications/count')
@login_required
def notifications_count():
    user_id = session['user_id']
    count = Notification.query.filter_by(
        user_id=user_id,
        is_read=False
    ).count()
    
    return jsonify({'count': count})


# ========================
# Сообщения и чат
# ========================

@app.route('/messages')
@login_required
def messages():
    user = db.session.get(User, session['user_id'])
    
    # ========== ЛИЧНЫЕ ЧАТЫ (существующий код) ==========
    conversations = []
    
    sent_conversations = db.session.query(
        Message.receiver_id,
        db.func.max(Message.created_at).label('last_message')
    ).filter(Message.sender_id == user.id).group_by(Message.receiver_id)
    
    received_conversations = db.session.query(
        Message.sender_id,
        db.func.max(Message.created_at).label('last_message')
    ).filter(Message.receiver_id == user.id).group_by(Message.sender_id)
    
    all_conversations = {}
    
    for receiver_id, last_message in sent_conversations:
        all_conversations[receiver_id] = last_message
    
    for sender_id, last_message in received_conversations:
        if sender_id in all_conversations:
            if last_message > all_conversations[sender_id]:
                all_conversations[sender_id] = last_message
        else:
            all_conversations[sender_id] = last_message
    
    for other_user_id, last_message in sorted(all_conversations.items(), 
                                             key=lambda x: x[1], 
                                             reverse=True):
        other_user = db.session.get(User, other_user_id)
        if other_user:
            unread_count = Message.query.filter_by(
                sender_id=other_user_id,
                receiver_id=user.id,
                is_read=False
            ).count()
            
            conversations.append({
                'user': other_user,
                'last_message': last_message,
                'unread_count': unread_count
            })
    
    # ========== НОВОЕ: ГРУППОВЫЕ ЧАТЫ ==========
    my_groups = db.session.query(ChatGroup).join(GroupMember).filter(
        GroupMember.user_id == user.id
    ).order_by(ChatGroup.created_at.desc()).all()
    
    # Для каждой группы получаем последнее сообщение
    groups_with_info = []
    for group in my_groups:
        last_msg = GroupMessage.query.filter_by(group_id=group.id)\
            .order_by(GroupMessage.created_at.desc()).first()
        
        unread_count = 0  # TODO: можно добавить подсчёт непрочитанных в группах
        
        groups_with_info.append({
            'group': group,
            'last_message': last_msg.created_at if last_msg else group.created_at,
            'unread_count': unread_count
        })
    
    # Сортируем группы по последнему сообщению
    groups_with_info.sort(key=lambda x: x['last_message'], reverse=True)
    
    return render_template('messages/inbox.html', 
                         conversations=conversations,
                         groups=groups_with_info)  # ← передаём группы в шаблон

@app.route('/chat/<username>')
@login_required
def chat(username):
    current_user = db.session.get(User, session['user_id'])
    other_user = User.query.filter_by(username=username).first_or_404()
    
    are_friends = Friendship.query.filter(
        (
            (Friendship.user_id == current_user.id) & 
            (Friendship.friend_id == other_user.id) & 
            (Friendship.status == 'accepted')
        ) | (
            (Friendship.user_id == other_user.id) & 
            (Friendship.friend_id == current_user.id) & 
            (Friendship.status == 'accepted')
        )
    ).first() is not None
    
    if not are_friends:
        flash('Вы можете писать только друзьям', 'error')
        return redirect(url_for('messages'))
    
    messages_list = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == other_user.id)) |
        ((Message.sender_id == other_user.id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.created_at.asc()).all()
    
    unread_messages = Message.query.filter_by(
        sender_id=other_user.id,
        receiver_id=current_user.id,
        is_read=False
    ).all()
    
    for msg in unread_messages:
        msg.mark_as_read()
    
    db.session.commit()
    
    return render_template('messages/chat.html',
                         other_user=other_user,
                         messages=messages_list)


# ========================
# API для фронтенда
# ========================

@app.route('/api/messages/<int:user_id>')
@login_required
def api_get_messages(user_id):
    current_user_id = session['user_id']
    
    are_friends = Friendship.query.filter(
        (
            (Friendship.user_id == current_user_id) & 
            (Friendship.friend_id == user_id) & 
            (Friendship.status == 'accepted')
        ) | (
            (Friendship.user_id == user_id) & 
            (Friendship.friend_id == current_user_id) & 
            (Friendship.status == 'accepted')
        )
    ).first() is not None
    
    if not are_friends:
        return jsonify({'error': 'Вы не друзья с этим пользователем'}), 403
    
    messages_list = Message.query.filter(
        ((Message.sender_id == current_user_id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == current_user_id))
    ).order_by(Message.created_at.asc()).all()
    
    messages_data = []
    for msg in messages_list:
        messages_data.append({
            'id': msg.id,
            'text': msg.encrypted_content or (msg.sticker_id and 'sticker') or '',
            'sender_id': msg.sender_id,
            'sender_username': msg.sender.username,
            'receiver_id': msg.receiver_id,
            'created_at': msg.created_at.isoformat(),
            'is_read': msg.is_read,
            'is_mine': msg.sender_id == current_user_id,
            'is_encrypted': msg.is_encrypted
        })
    
    return jsonify({'messages': messages_data})

@app.route('/api/messages/read', methods=['POST'])
@login_required
def mark_messages_read():
    try:
        user_id = session['user_id']
        Message.query.filter_by(receiver_id=user_id, is_read=False).update({'is_read': True})
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========================
# ЭМОДЗИ-РЕАКЦИИ
# ========================

@app.route('/api/message/<int:message_id>/react', methods=['POST'])
@login_required
def add_reaction(message_id):
    try:
        data = request.get_json()
        emoji = data.get('emoji')
        
        if not emoji:
            return jsonify({'error': 'Emoji обязателен'}), 400
        
        message = Message.query.get(message_id)
        if not message:
            return jsonify({'error': 'Сообщение не найдено'}), 404
        
        user_id = session.get('user_id')
        
        existing = Reaction.query.filter_by(message_id=message_id, user_id=user_id).first()
        
        if existing:
            if existing.emoji == emoji:
                db.session.delete(existing)
            else:
                existing.emoji = emoji
        else:
            reaction = Reaction(message_id=message_id, user_id=user_id, emoji=emoji)
            db.session.add(reaction)
        
        db.session.commit()
        
        reactions = Reaction.query.filter_by(message_id=message_id).all()
        reactions_data = [{'user_id': r.user_id, 'emoji': r.emoji} for r in reactions]
        
        # Отправляем обновление через WebSocket отдельно
        room_name = f'chat_{min(message.sender_id, message.receiver_id)}_{max(message.sender_id, message.receiver_id)}'
        
        # Используем socketio для отправки
        try:
            socketio.emit('message_reaction', {
                'message_id': message_id,
                'reactions': reactions_data
            }, room=room_name)
        except Exception as e:
            print(f"⚠️ Не удалось отправить WebSocket: {e}")
        
        return jsonify({'success': True, 'reactions': reactions_data})
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/message/<int:message_id>/reactions', methods=['GET'])
@login_required
def get_reactions(message_id):
    reactions = Reaction.query.filter_by(message_id=message_id).all()
    reactions_data = [{'user_id': r.user_id, 'emoji': r.emoji} for r in reactions]
    return jsonify({'reactions': reactions_data})

# ========================
# WebSocket обработчики (С ПРОВЕРКОЙ АВТОРИЗАЦИИ)
# ========================

@socketio.on('connect')
def handle_connect():
    if 'user_id' in session:
        user_id = session['user_id']
        user = db.session.get(User, user_id)
        
        if user and not user.is_banned:
            join_room(f'user_{user_id}')
            user.is_online = True
            user.last_seen = datetime.now(timezone.utc)
            db.session.commit()
            print(f'✅ Пользователь {user_id} подключился')
            emit('user_status', {'user_id': user_id, 'status': 'online'}, broadcast=True)
        else:
            print(f'❌ Отказ в подключении: пользователь {user_id} забанен или не существует')
            return False
    else:
        print('❌ Отказ в подключении: нет сессии')
        return False

@socketio.on('disconnect')
def handle_disconnect():
    if 'user_id' in session:
        user_id = session['user_id']
        user = db.session.get(User, user_id)
        if user:
            user.is_online = False
            user.last_seen = datetime.now(timezone.utc)
            db.session.commit()
        
        print(f'👋 Пользователь {user_id} отключился')
        emit('user_status', {'user_id': user_id, 'status': 'offline'}, broadcast=True)

@socketio.on('join_chat')
def handle_join_chat(data):
    if 'user_id' not in session:
        emit('error', {'message': 'Требуется авторизация'})
        return
    
    other_user_id = data.get('other_user_id')
    if other_user_id:
        user_id = session['user_id']
        room_name = f'chat_{min(user_id, other_user_id)}_{max(user_id, other_user_id)}'
        join_room(room_name)
        print(f'📌 Пользователь {user_id} присоединился к чату с {other_user_id}')

@socketio.on('send_message')
def handle_send_message(data):
    try:
        receiver_id = data.get('receiver_id')
        temp_id = data.get('temp_id')
        is_sticker = data.get('is_sticker', False)
        is_attachment = data.get('is_attachment', False)
        
        encrypted = data.get('encrypted', '')
        iv = data.get('iv', '')
        text = data.get('text', '')
        
        sticker_id = data.get('sticker_id')
        sticker_code = data.get('sticker_code')
        
        sender_id = session.get('user_id')
        
        if not receiver_id:
            emit('error', {'message': 'Не указан получатель'})
            return
        
        if not sender_id:
            emit('error', {'message': 'Требуется авторизация'})
            return
        
        # Получаем отправителя
        sender = db.session.get(User, sender_id)
        if not sender:
            emit('error', {'message': 'Отправитель не найден'})
            return
        
        # Проверка дружбы
        are_friends = Friendship.query.filter(
            (
                (Friendship.user_id == sender_id) & 
                (Friendship.friend_id == receiver_id) & 
                (Friendship.status == 'accepted')
            ) | (
                (Friendship.user_id == receiver_id) & 
                (Friendship.friend_id == sender_id) & 
                (Friendship.status == 'accepted')
            )
        ).first() is not None
        
        if not are_friends:
            emit('error', {'message': 'Вы можете писать только друзьям'})
            return
        
        # Сохраняем сообщение
        if is_sticker:
            message = Message(
                encrypted_content=encrypted,
                encryption_nonce=iv,
                sticker_id=sticker_id,
                sender_id=sender_id,
                receiver_id=receiver_id,
                is_encrypted=True,
                created_at=datetime.now(timezone.utc)
            )
        elif is_attachment:
            message = Message(
                encrypted_content=encrypted,
                encryption_nonce=iv,
                sender_id=sender_id,
                receiver_id=receiver_id,
                is_encrypted=True,
                is_attachment=True,
                attachment_type=data.get('attachment_type'),
                attachment_name=data.get('attachment_name'),
                attachment_size=data.get('attachment_size'),
                created_at=datetime.now(timezone.utc)
            )
        else:
            message = Message(
                encrypted_content=encrypted,
                encryption_nonce=iv,
                sender_id=sender_id,
                receiver_id=receiver_id,
                is_encrypted=True,
                created_at=datetime.now(timezone.utc)
            )
        
        db.session.add(message)
        
        # Уведомление
        notification = Notification(
            user_id=receiver_id,
            type='message',
            content=f'Новое сообщение от {sender.username}',
            related_id=sender_id,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(notification)
        db.session.commit()
        
        # Отправляем обратно
        room_name = f'chat_{min(sender_id, receiver_id)}_{max(sender_id, receiver_id)}'
        
        message_data = {
            'id': message.id,
            'encrypted': encrypted,
            'iv': iv,
            'sender_id': sender_id,
            'sender_username': sender.username,
            'receiver_id': receiver_id,
            'created_at': message.created_at.isoformat(),
            'is_read': message.is_read,
            'temp_id': temp_id,
            'is_sticker': is_sticker,
            'is_attachment': is_attachment,
            'sticker_id': sticker_id,
            'sticker_code': sticker_code
        }
        
        emit('new_message', message_data, room=room_name)
        print(f"✅ Сообщение #{message.id} отправлено")
        
    except Exception as e:
        print(f'❌ Ошибка: {e}')
        import traceback
        traceback.print_exc()
        db.session.rollback()
        emit('error', {'message': str(e)})

@socketio.on('read_message')
def handle_read_message(data):
    message_id = data.get('message_id')
    if message_id:
        message = Message.query.get(message_id)
        if message and message.receiver_id == session.get('user_id'):
            message.is_read = True
            message.read_at = datetime.now(timezone.utc)
            db.session.commit()
            
            # Уведомляем отправителя, что сообщение прочитано
            room_name = f'chat_{min(message.sender_id, message.receiver_id)}_{max(message.sender_id, message.receiver_id)}'
            emit('message_read', {
                'message_id': message_id,
                'read_at': message.read_at.isoformat()
            }, room=room_name)
            print(f"✅ Сообщение {message_id} отмечено как прочитанное")

@socketio.on('typing')
def handle_typing(data):
    if 'user_id' not in session:
        return
    
    receiver_id = data.get('receiver_id')
    if receiver_id:
        sender_id = session['user_id']
        sender = db.session.get(User, sender_id)
        
        if sender and not sender.is_banned:
            emit('user_typing', {
                'sender_id': sender_id,
                'sender_username': sender.username
            }, room=f'user_{receiver_id}')

# ========================
# ГРУППОВЫЕ ЧАТЫ
# ========================

@app.route('/groups')
@login_required
def groups_list():
    """Список групп пользователя"""
    user_id = session['user_id']
    
    # Группы, где пользователь состоит
    my_groups = db.session.query(ChatGroup).join(GroupMember).filter(
        GroupMember.user_id == user_id
    ).order_by(ChatGroup.created_at.desc()).all()
    
    # Группы, созданные пользователем (где он админ)
    created_groups = ChatGroup.query.filter_by(created_by=user_id).all()
    
    return render_template('groups/list.html', 
                         my_groups=my_groups, 
                         created_groups=created_groups)


@app.route('/groups/create', methods=['GET', 'POST'])
@login_required
def create_group():
    """Создание новой группы"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        is_private = request.form.get('is_private') == 'on'
        
        if not name:
            flash('Введите название группы', 'error')
            return redirect(url_for('create_group'))
        
        # Генерируем ключи группы
        
        # Генерируем групповой ключ (AES-256)
        group_key = secrets.token_bytes(32)
        group_key_b64 = base64.b64encode(group_key).decode()
        
        # Генерируем публичный ключ группы (для верификации)
        temp_key = E2EEncryption.generate_key_pair(secrets.token_urlsafe(32))
        
        group = ChatGroup(
            name=name,
            description=description,
            created_by=session['user_id'],
            is_private=is_private,
            invite_code=secrets.token_urlsafe(16),
            group_public_key=temp_key['public_key'],
            encrypted_group_key=group_key_b64  # временно, потом перешифруем
        )
        db.session.add(group)
        db.session.flush()
        
        # Добавляем создателя как админа
        member = GroupMember(
            group_id=group.id,
            user_id=session['user_id'],
            role='admin'
        )
        db.session.add(member)
        db.session.commit()
        
        flash(f'Группа "{name}" успешно создана!', 'success')
        return redirect(url_for('group_chat', group_id=group.id))
    
    return render_template('groups/create.html')


@app.route('/groups/<int:group_id>')
@login_required
def group_chat(group_id):
    """Чат группы"""
    group = ChatGroup.query.get_or_404(group_id)
    current_user_id = session['user_id']
    
    # Проверяем, есть ли пользователь в группе
    membership = GroupMember.query.filter_by(
        group_id=group_id, user_id=current_user_id
    ).first()
    
    if not membership and group.is_private:
        flash('Вы не состоите в этой группе', 'error')
        return redirect(url_for('groups_list'))
    
    # Загружаем участников
    members = GroupMember.query.filter_by(group_id=group_id).all()
    
    # Загружаем сообщения (последние 100)
    messages = GroupMessage.query.filter_by(group_id=group_id)\
        .order_by(GroupMessage.created_at.asc())\
        .limit(100)\
        .all()
    
    # Получаем E2EE ключ группы (если есть)
    group_encrypted_key = None
    if membership and membership.encrypted_group_key_for_user:
        group_encrypted_key = membership.encrypted_group_key_for_user
    
    return render_template('groups/chat.html', 
                         group=group,
                         members=members,
                         messages=messages,
                         group_encrypted_key=group_encrypted_key,
                         current_user_role=membership.role if membership else None)


@app.route('/groups/<int:group_id>/invite')
@login_required
def group_invite(group_id):
    """Получить ссылку-приглашение (только для админов)"""
    group = ChatGroup.query.get_or_404(group_id)
    
    membership = GroupMember.query.filter_by(
        group_id=group_id, user_id=session['user_id']
    ).first()
    
    if not membership or membership.role != 'admin':
        return jsonify({'error': 'Доступ запрещён. Только администраторы.'}), 403
    
    invite_link = url_for('join_group', code=group.invite_code, _external=True)
    return jsonify({'invite_link': invite_link})


@app.route('/groups/join/<code>')
@login_required
def join_group(code):
    """Присоединиться к группе по ссылке"""
    group = ChatGroup.query.filter_by(invite_code=code).first_or_404()
    current_user_id = session['user_id']
    
    existing = GroupMember.query.filter_by(
        group_id=group.id, user_id=current_user_id
    ).first()
    
    if existing:
        flash('Вы уже в группе', 'info')
        return redirect(url_for('group_chat', group_id=group.id))
    
    # Добавляем участника
    member = GroupMember(
        group_id=group.id,
        user_id=current_user_id,
        role='member'
    )
    db.session.add(member)
    db.session.commit()
    
    flash(f'Вы присоединились к группе "{group.name}"', 'success')
    return redirect(url_for('group_chat', group_id=group.id))


@app.route('/groups/<int:group_id>/members')
@login_required
def group_members(group_id):
    """Список участников группы (API)"""
    group = ChatGroup.query.get_or_404(group_id)
    
    membership = GroupMember.query.filter_by(
        group_id=group_id, user_id=session['user_id']
    ).first()
    
    if not membership:
        return jsonify({'error': 'Нет доступа'}), 403
    
    members = []
    for m in GroupMember.query.filter_by(group_id=group_id).all():
        members.append({
            'id': m.user.id,
            'username': m.user.username,
            'avatar': m.user.avatar,
            'role': m.role,
            'is_online': m.user.is_online
        })
    
    return jsonify({'members': members})


@app.route('/groups/<int:group_id>/add-member', methods=['POST'])
@login_required
def add_group_member(group_id):
    """Добавить участника (админ)"""
    group = ChatGroup.query.get_or_404(group_id)
    
    membership = GroupMember.query.filter_by(
        group_id=group_id, user_id=session['user_id']
    ).first()
    
    if not membership or membership.role != 'admin':
        return jsonify({'error': 'Только администраторы могут добавлять участников'}), 403
    
    data = request.get_json()
    username = data.get('username')
    
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    existing = GroupMember.query.filter_by(group_id=group_id, user_id=user.id).first()
    if existing:
        return jsonify({'error': 'Пользователь уже в группе'}), 400
    
    new_member = GroupMember(
        group_id=group_id,
        user_id=user.id,
        role='member'
    )
    db.session.add(new_member)
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'{username} добавлен в группу'})


@app.route('/groups/<int:group_id>/remove-member', methods=['POST'])
@login_required
def remove_group_member(group_id):
    """Удалить участника (админ)"""
    group = ChatGroup.query.get_or_404(group_id)
    
    current_membership = GroupMember.query.filter_by(
        group_id=group_id, user_id=session['user_id']
    ).first()
    
    if not current_membership or current_membership.role != 'admin':
        return jsonify({'error': 'Только администраторы могут удалять участников'}), 403
    
    data = request.get_json()
    user_id = data.get('user_id')
    
    if user_id == session['user_id']:
        return jsonify({'error': 'Нельзя удалить себя'}), 400
    
    member = GroupMember.query.filter_by(group_id=group_id, user_id=user_id).first()
    if not member:
        return jsonify({'error': 'Участник не найден'}), 404
    
    db.session.delete(member)
    db.session.commit()
    
    return jsonify({'success': True})


@app.route('/groups/<int:group_id>/leave', methods=['POST'])
@login_required
def leave_group(group_id):
    """Выйти из группы"""
    group = ChatGroup.query.get_or_404(group_id)
    current_user_id = session['user_id']
    
    # Проверяем, есть ли пользователь в группе
    member = GroupMember.query.filter_by(
        group_id=group_id, user_id=current_user_id
    ).first()
    
    if not member:
        flash('Вы не состоите в этой группе', 'error')
        return redirect(url_for('groups_list'))
    
    # Проверяем, не единственный ли это админ
    admins = GroupMember.query.filter_by(
        group_id=group_id, role='admin'
    ).count()
    
    if member.role == 'admin' and admins == 1:
        flash('Вы единственный администратор. Сначала назначьте другого администратора или удалите группу.', 'error')
        return redirect(url_for('group_chat', group_id=group_id))
    
    # Удаляем участника
    db.session.delete(member)
    db.session.commit()
    
    flash(f'Вы вышли из группы "{group.name}"', 'info')
    return redirect(url_for('groups_list'))


@app.route('/groups/<int:group_id>/delete', methods=['POST'])
@login_required
def delete_group(group_id):
    """Удалить группу (только создатель)"""
    group = ChatGroup.query.get_or_404(group_id)
    current_user_id = session['user_id']
    
    # Только создатель может удалить группу
    if group.created_by != current_user_id:
        flash('Только создатель группы может удалить её', 'error')
        return redirect(url_for('group_chat', group_id=group_id))
    
    # Удаляем все сообщения и участников (cascade отработает)
    db.session.delete(group)
    db.session.commit()
    
    flash(f'Группа "{group.name}" удалена', 'success')
    return redirect(url_for('groups_list'))


@app.route('/groups/<int:group_id>/promote', methods=['POST'])
@login_required
def promote_to_admin(group_id):
    """Назначить участника администратором (только админ)"""
    group = ChatGroup.query.get_or_404(group_id)
    current_user_id = session['user_id']
    
    current_member = GroupMember.query.filter_by(
        group_id=group_id, user_id=current_user_id
    ).first()
    
    if not current_member or current_member.role != 'admin':
        return jsonify({'error': 'Только администраторы могут назначать администраторов'}), 403
    
    data = request.get_json()
    user_id = data.get('user_id')
    
    target_member = GroupMember.query.filter_by(
        group_id=group_id, user_id=user_id
    ).first()
    
    if not target_member:
        return jsonify({'error': 'Участник не найден'}), 404
    
    if target_member.role == 'admin':
        return jsonify({'error': 'Пользователь уже администратор'}), 400
    
    target_member.role = 'admin'
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Администратор назначен'})

# ========================
# WebSocket для групповых чатов (НОВЫЕ - базовая реализация групповых чатов)
# ========================

@socketio.on('join_group')
def handle_join_group(data):
    """Присоединение к комнате группы"""
    if 'user_id' not in session:
        return
    
    group_id = data.get('group_id')
    user_id = session['user_id']
    
    # Проверяем, что пользователь в группе
    member = GroupMember.query.filter_by(group_id=group_id, user_id=user_id).first()
    if member:
        room_name = f'group_{group_id}'
        join_room(room_name)
        print(f'📌 User {user_id} joined group room {room_name}')


@socketio.on('send_group_message')
def handle_send_group_message(data):
    """Отправка сообщения в группу"""
    if 'user_id' not in session:
        return
    
    group_id = data.get('group_id')
    encrypted = data.get('encrypted')
    iv = data.get('iv')
    sender_id = session['user_id']
    
    # Проверка, что пользователь в группе
    member = GroupMember.query.filter_by(group_id=group_id, user_id=sender_id).first()
    if not member:
        emit('error', {'message': 'Нет доступа'})
        return
    
    # Сохраняем сообщение
    message = GroupMessage(
        group_id=group_id,
        sender_id=sender_id,
        encrypted_content=encrypted,
        encryption_nonce=iv,
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(message)
    db.session.commit()
    
    # Отправляем всем в комнате
    sender = db.session.get(User, sender_id)
    room_name = f'group_{group_id}'
    emit('new_group_message', {
        'id': message.id,
        'encrypted': encrypted,
        'iv': iv,
        'sender_id': sender_id,
        'sender_username': sender.username,
        'created_at': message.created_at.isoformat()
    }, room=room_name)


@socketio.on('group_typing')
def handle_group_typing(data):
    """Индикатор печатания в группе"""
    if 'user_id' not in session:
        return
    
    group_id = data.get('group_id')
    sender_id = session['user_id']
    sender = db.session.get(User, sender_id)
    
    if sender:
        room_name = f'group_{group_id}'
        emit('group_typing', {
            'sender_id': sender_id,
            'sender_username': sender.username
        }, room=room_name, include_self=False)

# ========================
# E2EE API Роуты (НОВЫЕ - правильное E2EE)
# ========================

@app.route('/api/e2ee/public_key', methods=['POST'])
@login_required
def e2ee_save_public_key():
    """Сохранение публичного ключа пользователя"""
    try:
        data = request.get_json()
        public_key = data.get('public_key')
        
        if not public_key:
            return jsonify({'error': 'Нет ключа'}), 400
        
        user = db.session.get(User, session['user_id'])
        user.public_key = public_key
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/e2ee/public_key/<int:user_id>', methods=['GET'])
@login_required
def e2ee_get_public_key(user_id):
    """Получение публичного ключа пользователя"""
    user = db.session.get(User, user_id)
    
    if not user or not user.public_key:
        return jsonify({'error': 'Ключ не найден'}), 404
    
    return jsonify({'public_key': user.public_key})

@app.route('/api/e2ee/messages/<int:user_id>', methods=['GET'])
@login_required
def e2ee_get_messages(user_id):
    """Получение зашифрованных сообщений (даже если собеседник офлайн)"""
    current_user_id = session['user_id']
    
    # Получаем все сообщения между пользователями
    messages = Message.query.filter(
        ((Message.sender_id == current_user_id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == current_user_id))
    ).order_by(Message.created_at.asc()).all()
    
    messages_data = []
    for msg in messages:
        messages_data.append({
            'id': msg.id,
            'encrypted': msg.encrypted_content,
            'nonce': msg.encryption_nonce,
            'sender_id': msg.sender_id,
            'created_at': msg.created_at.isoformat()
        })
    
    # Помечаем сообщения от собеседника как прочитанные
    Message.query.filter_by(
        sender_id=user_id,
        receiver_id=current_user_id,
        is_read=False
    ).update({'is_read': True})
    db.session.commit()
    
    return jsonify({'messages': messages_data})

# ========================
# Groups API (НОВЫЕ - базовая реализация групповых чатов)
# ========================

@app.route('/api/group-messages/<int:group_id>')
@login_required
def api_group_messages(group_id):
    """Получить сообщения группы"""
    group = ChatGroup.query.get_or_404(group_id)
    
    membership = GroupMember.query.filter_by(
        group_id=group_id, user_id=session['user_id']
    ).first()
    
    if not membership:
        return jsonify({'error': 'Нет доступа'}), 403
    
    messages = GroupMessage.query.filter_by(group_id=group_id)\
        .order_by(GroupMessage.created_at.asc())\
        .limit(100)\
        .all()
    
    messages_data = []
    for msg in messages:
        messages_data.append({
            'id': msg.id,
            'encrypted': msg.encrypted_content,
            'nonce': msg.encryption_nonce,
            'sender_id': msg.sender_id,
            'sender_username': msg.sender.username,
            'created_at': msg.created_at.isoformat()
        })
    
    return jsonify({'messages': messages_data})

# ========================
# Аватарки
# ========================

from werkzeug.utils import secure_filename
from PIL import Image
import os

def save_avatar(user_id, file):
    """Сохраняет аватарку и создает миниатюру"""
    if not file or file.filename == '':
        return None
    
    # Разрешенные расширения
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    
    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    
    if not allowed_file(file.filename):
        flash('Неверный формат. Поддерживаются: png, jpg, jpeg, gif, webp', 'error')
        return None
    
    # Генерируем имя файла
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f'user_{user_id}_{int(datetime.now(timezone.utc).timestamp())}.{ext}'
    
    # Пути для сохранения
    avatar_path = os.path.join('static/uploads/avatars', filename)
    thumb_path = os.path.join('static/uploads/avatars/thumb', f'thumb_{filename}')
    
    # Сохраняем оригинал
    file.save(avatar_path)
    
    # Создаем миниатюру (200x200)
    try:
        img = Image.open(avatar_path)
        img.thumbnail((200, 200), Image.Resampling.LANCZOS)
        img.save(thumb_path, optimize=True, quality=85)
    except Exception as e:
        print(f"Ошибка создания миниатюры: {e}")
        thumb_path = avatar_path
    
    return filename

@app.route('/upload_avatar', methods=['POST'])
@login_required
def upload_avatar():
    """Загрузка аватарки"""
    if 'avatar' not in request.files:
        flash('Файл не выбран', 'error')
        return redirect(url_for('profile'))
    
    file = request.files['avatar']
    user_id = session['user_id']
    user = db.session.get(User, user_id)
    
    # Удаляем старую аватарку
    if user.avatar:
        old_path = os.path.join('static/uploads/avatars', user.avatar)
        old_thumb = os.path.join('static/uploads/avatars/thumb', f'thumb_{user.avatar}')
        if os.path.exists(old_path):
            os.remove(old_path)
        if os.path.exists(old_thumb):
            os.remove(old_thumb)
    
    # Сохраняем новую
    filename = save_avatar(user_id, file)
    if filename:
        user.avatar = filename
        user.avatar_thumb = f'thumb_{filename}'
        db.session.commit()
        flash('Аватарка обновлена!', 'success')
    else:
        flash('Не удалось загрузить аватарку', 'error')
    
    return redirect(url_for('profile'))

@app.route('/avatar/<int:user_id>')
def get_avatar(user_id):
    """Получить аватарку пользователя"""
    user = db.session.get(User, user_id)
    if user and user.avatar:
        return redirect(url_for('static', filename=f'uploads/avatars/{user.avatar}'))
    return redirect(url_for('static', filename='img/default-avatar.png'))

# ========================
# Стикеры
# ========================

STICKERS = [
    {'id': 1, 'code': '😊', 'name': 'Улыбка'},
    {'id': 2, 'code': '😂', 'name': 'Смех'},
    {'id': 3, 'code': '🥰', 'name': 'Любовь'},
    {'id': 4, 'code': '😎', 'name': 'Крутой'},
    {'id': 5, 'code': '🤔', 'name': 'Задумался'},
    {'id': 6, 'code': '😭', 'name': 'Плач'},
    {'id': 7, 'code': '😡', 'name': 'Злость'},
    {'id': 8, 'code': '🎉', 'name': 'Праздник'},
    {'id': 9, 'code': '❤️', 'name': 'Сердце'},
    {'id': 10, 'code': '🔥', 'name': 'Огонь'},
    {'id': 11, 'code': '👍', 'name': 'Лайк'},
    {'id': 12, 'code': '👎', 'name': 'Дизлайк'},
]

@app.route('/api/stickers')
@login_required
def get_stickers():
    """Получить список доступных стикеров"""
    return jsonify(STICKERS)

@app.route('/api/sticker/<int:sticker_id>')
@login_required
def get_sticker(sticker_id):
    """Получить конкретный стикер"""
    sticker = next((s for s in STICKERS if s['id'] == sticker_id), None)
    if sticker:
        return jsonify(sticker)
    return jsonify({'error': 'Стикер не найден'}), 404

# ========================
# Утилиты и обработчики ошибок
# ========================

@app.context_processor
def inject_user():
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        return {'current_user': user}
    return {'current_user': None}

@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

@app.before_request
def auto_promote_owner():
    owner_username = os.environ.get('OWNER_USERNAME')
    if owner_username:
        user = User.query.filter_by(username=owner_username).first()
        if user and user.role != 'owner':
            user.role = 'owner'
            user.email_verified = True
            db.session.commit()

# ========================
# Точка входа
# ========================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    print("=" * 50)
    print("🚀 Messenger запущен!")
    print("📍 http://localhost:5000")
    print("🔒 Защита маршрутов: ВКЛЮЧЕНА")
    print("🔐 WebSocket авторизация: ВКЛЮЧЕНА")
    print("=" * 50)
    
    
    socketio.run(app, 
             host='0.0.0.0',
             port=int(os.environ.get('PORT', 5000)),
             debug=False
             )
