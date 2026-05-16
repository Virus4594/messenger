# set_owner.py
import os
from app import app, db
from models import User

with app.app_context():
    username = os.environ.get('OWNER_USERNAME')
    if username:
        user = User.query.filter_by(username=username).first()
        if user and user.role != 'owner':
            user.role = 'owner'
            user.email_verified = True
            db.session.commit()
            print(f"✅ {username} теперь владелец!")
        else:
            print(f"ℹ️ {username} уже владелец или не найден")
    else:
        print("⚠️ OWNER_USERNAME не задан")
