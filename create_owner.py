# create_owner.py
import os
from getpass import getpass
from app import app, db
from models import User
from auth import hash_password

def create_owner():
    with app.app_context():
        owner = User.query.filter_by(role='owner').first()
        if owner:
            print("⚠️ Владелец уже существует!")
            return

        print("=" * 50)
        print("👑 Создание владельца Messenger")
        print("=" * 50)
        username = input("Введите логин владельца: ").strip()
        while not username:
            username = input("Логин не может быть пустым. Введите ещё раз: ").strip()

        email = input("Введите email владельца: ").strip().lower()
        while '@' not in email or '.' not in email.split('@')[-1]:
            email = input("Некорректный email. Введите ещё раз: ").strip().lower()

        password = getpass("Введите пароль владельца (минимум 8 символов): ")
        while len(password) < 8:
            password = getpass("Пароль должен содержать хотя бы 8 символов. Введите ещё раз: ")
        confirm = getpass("Подтвердите пароль: ")
        while password != confirm:
            print("Пароли не совпадают.")
            password = getpass("Введите пароль: ")
            confirm = getpass("Подтвердите пароль: ")

        owner = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role='owner',
            email_verified=True,
            is_online=False
        )
        db.session.add(owner)
        db.session.commit()
        print("=" * 50)
        print("✅ Владелец успешно создан!")
        print("=" * 50)

if __name__ == '__main__':
    create_owner()