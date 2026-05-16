# create_admin.py
from app import app, db
from models import User
from auth import hash_password

with app.app_context():
    # Проверяем, существует ли уже админ
    admin = User.query.filter_by(username='admin').first()
    
    if not admin:
        admin = User(
            username='ViRuS',
            email='virusvirusov22@gmail.com',
            password_hash=hash_password('ViRuS4594VS!'),
            role='admin',
            email_verified=True,
            is_online=False
        )
        db.session.add(admin)
        db.session.commit()
        print("=" * 50)
        print("✅ Администратор успешно создан!")
        print("📌 Логин: ViRuS")
        print("📌 Пароль: ViRuS4594VS!")
        print("=" * 50)
    else:
        print("⚠️ Администратор уже существует!")
        print(f"📌 Имя: {admin.username}")
        print(f"📌 Роль: {admin.role}")