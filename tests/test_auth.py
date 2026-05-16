# tests/test_auth.py
import pytest
import time
from models import User
from auth import hash_password

def login_via_session(client, user_id):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id

def test_register_success(client, db):
    response = client.post('/register', data={
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'ValidPass1!',
        'confirm_password': 'ValidPass1!'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    user = User.query.filter_by(username='testuser').first()
    assert user is not None
    assert user.email == 'test@example.com'

def test_register_duplicate_username(client, db):
    client.post('/register', data={
        'username': 'duplicate',
        'email': 'first@example.com',
        'password': 'ValidPass1!',
        'confirm_password': 'ValidPass1!'
    }, follow_redirects=True)
    
    response = client.post('/register', data={
        'username': 'duplicate',
        'email': 'second@example.com',
        'password': 'ValidPass1!',
        'confirm_password': 'ValidPass1!'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert 'Имя пользователя уже занято' in response.data.decode('utf-8')

def test_register_duplicate_email(client, db):
    client.post('/register', data={
        'username': 'user1',
        'email': 'same@example.com',
        'password': 'ValidPass1!',
        'confirm_password': 'ValidPass1!'
    }, follow_redirects=True)
    
    response = client.post('/register', data={
        'username': 'user2',
        'email': 'same@example.com',
        'password': 'ValidPass1!',
        'confirm_password': 'ValidPass1!'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    response_text = response.data.decode('utf-8')
    # Проверяем, что нет rate limit и есть сообщение об ошибке
    assert '429' not in response_text
    assert 'Email уже зарегистрирован' in response_text or 'already registered' in response_text

def test_register_weak_password(client, db):
    response = client.post('/register', data={
        'username': 'weakuser',
        'email': 'weak@example.com',
        'password': 'weak',
        'confirm_password': 'weak'
    }, follow_redirects=True)
    
    # Проверяем, что нет rate limit
    assert response.status_code != 429
    assert response.status_code == 200
    assert 'Пароль должен содержать минимум 8 символов' in response.data.decode('utf-8')

def test_register_password_no_uppercase(client, db):
    response = client.post('/register', data={
        'username': 'nouppercase',
        'email': 'test@example.com',
        'password': 'password123!',
        'confirm_password': 'password123!'
    }, follow_redirects=True)
    
    assert response.status_code != 429
    assert response.status_code == 200
    assert 'Пароль должен содержать заглавные буквы' in response.data.decode('utf-8')

def test_register_password_no_digit(client, db):
    response = client.post('/register', data={
        'username': 'nodigit',
        'email': 'test@example.com',
        'password': 'Password!',
        'confirm_password': 'Password!'
    }, follow_redirects=True)
    
    assert response.status_code != 429
    assert response.status_code == 200
    assert 'Пароль должен содержать цифры' in response.data.decode('utf-8')

def test_register_invalid_email(client, db):
    response = client.post('/register', data={
        'username': 'bademail',
        'email': 'invalid-email',
        'password': 'ValidPass1!',
        'confirm_password': 'ValidPass1!'
    }, follow_redirects=True)
    
    assert response.status_code != 429
    assert response.status_code == 200
    assert 'Введите корректный email адрес' in response.data.decode('utf-8')

def test_login_success(client, db):
    password_hash = hash_password('ValidPass1!')
    user = User(
        username='loginuser',
        email='login@example.com',
        password_hash=password_hash,
        email_verified=True
    )
    db.session.add(user)
    db.session.commit()
    
    response = client.post('/login', data={
        'username': 'loginuser',
        'password': 'ValidPass1!'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    with client.session_transaction() as sess:
        assert sess.get('user_id') == user.id

def test_login_wrong_password(client, db):
    password_hash = hash_password('ValidPass1!')
    user = User(
        username='loginuser2',
        email='login2@example.com',
        password_hash=password_hash,
        email_verified=True
    )
    db.session.add(user)
    db.session.commit()
    
    response = client.post('/login', data={
        'username': 'loginuser2',
        'password': 'WrongPassword'
    }, follow_redirects=True)
    
    assert 'Неверное имя пользователя или пароль' in response.data.decode('utf-8')

def test_login_wrong_username(client, db):
    response = client.post('/login', data={
        'username': 'nonexistent',
        'password': 'ValidPass1!'
    }, follow_redirects=True)
    
    assert 'Неверное имя пользователя или пароль' in response.data.decode('utf-8')

def test_login_banned_user(client, db):
    password_hash = hash_password('ValidPass1!')
    user = User(
        username='banneduser',
        email='banned@example.com',
        password_hash=password_hash,
        email_verified=True,
        is_banned=True
    )
    db.session.add(user)
    db.session.commit()
    
    response = client.post('/login', data={
        'username': 'banneduser',
        'password': 'ValidPass1!'
    }, follow_redirects=True)
    
    assert 'аккаунт заблокирован' in response.data.decode('utf-8')

def test_login_unverified_email(client, db):
    password_hash = hash_password('ValidPass1!')
    user = User(
        username='unverified',
        email='unverified@example.com',
        password_hash=password_hash,
        email_verified=False
    )
    db.session.add(user)
    db.session.commit()
    
    response = client.post('/login', data={
        'username': 'unverified',
        'password': 'ValidPass1!'
    }, follow_redirects=True)
    
    assert 'подтвердите ваш email' in response.data.decode('utf-8')

def test_logout(client, db, test_user):
    login_via_session(client, test_user.id)
    response = client.get('/logout', follow_redirects=True)
    assert response.status_code == 200
    
    with client.session_transaction() as sess:
        assert 'user_id' not in sess

def test_protected_route_requires_login(client):
    response = client.get('/feed', follow_redirects=True)
    assert 'войдите в систему' in response.data.decode('utf-8')