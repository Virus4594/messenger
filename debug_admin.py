from app import app, db, User

with app.app_context():
    print("\n=== ТЕКУЩИЕ ПОЛЬЗОВАТЕЛИ ===")
    for u in User.query.all():
        print(f"ID: {u.id}, Username: {u.username}, Role: '{u.role}', Banned: {u.is_banned}")
    
    print("\n=== КТО ЗАЛОГИНЕН В СЕССИИ? ===")
    print("Запусти сервер и зайди под owner, потом проверь сессию")