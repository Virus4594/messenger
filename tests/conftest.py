# tests/conftest.py
import os
import pytest

os.environ['FLASK_ENV'] = 'testing'
os.environ['RATELIMIT_ENABLED'] = 'False'

@pytest.fixture(scope='session')
def app():
    from config import Config
    
    class TestConfig(Config):
        TESTING = True
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
        WTF_CSRF_ENABLED = False
        SECRET_KEY = 'test-secret-key-for-testing'
        RATELIMIT_ENABLED = False
        RATELIMIT_DEFAULT = None
        MAIL_SUPPRESS_SEND = True
        SOCKETIO_ASYNC_MODE = 'threading'
        WTF_CSRF_CHECK_DEFAULT = False
        RATELIMIT_STORAGE_URL = 'memory://'
        RATELIMIT_STRATEGY = 'fixed-window'
        RATELIMIT_HEADERS_ENABLED = False
    
    from app import app as flask_app
    flask_app.config.from_object(TestConfig)
    
    with flask_app.app_context():
        yield flask_app

@pytest.fixture(scope='function')
def client(app):
    return app.test_client()

@pytest.fixture(scope='function')
def db(app):
    from models import db as _db
    
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.remove()
        _db.drop_all()

@pytest.fixture(scope='function')
def test_user(db):
    from models import User
    from auth import hash_password
    
    user = User(
        username='testuser',
        email='test@example.com',
        password_hash=hash_password('Test123!'),
        role='user',
        email_verified=True
    )
    db.session.add(user)
    db.session.commit()
    return user

@pytest.fixture(scope='function')
def admin_user(db):
    from models import User
    from auth import hash_password
    
    admin = User(
        username='admin',
        email='admin@example.com',
        password_hash=hash_password('Admin123!'),
        role='admin',
        email_verified=True
    )
    db.session.add(admin)
    db.session.commit()
    return admin

@pytest.fixture(scope='function')
def owner_user(db):
    from models import User
    from auth import hash_password
    
    owner = User(
        username='owner',
        email='owner@example.com',
        password_hash=hash_password('Owner123!'),
        role='owner',
        email_verified=True
    )
    db.session.add(owner)
    db.session.commit()
    return owner

@pytest.fixture(scope='function')
def moderator_user(db):
    from models import User
    from auth import hash_password
    
    moderator = User(
        username='moderator',
        email='moderator@example.com',
        password_hash=hash_password('Mod123!'),
        role='moderator',
        email_verified=True
    )
    db.session.add(moderator)
    db.session.commit()
    return moderator