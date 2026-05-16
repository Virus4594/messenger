from app import app, db, Message, User

with app.app_context():
    messages = Message.query.order_by(Message.created_at.desc()).all()
    
    print("\n" + "="*60)
    print("📨 ВСЕ СООБЩЕНИЯ В БАЗЕ ДАННЫХ")
    print("="*60)
    
    for msg in messages:
        sender = db.session.get(User, msg.sender_id)
        receiver = db.session.get(User, msg.receiver_id)
        
        print(f"\n📝 ID: {msg.id}")
        print(f"   От: {sender.username if sender else '?'} (ID: {msg.sender_id})")
        print(f"   Кому: {receiver.username if receiver else '?'} (ID: {msg.receiver_id})")
        print(f"   Время: {msg.created_at}")
        
        if msg.is_encrypted:
            print(f"   Содержание: 🔒 ЗАШИФРОВАНО (E2EE)")
            print(f"   Зашифровано: {msg.encrypted_content[:50]}..." if msg.encrypted_content else "")
        else:
            print(f"   Содержание: {msg.content}")
        
        if msg.sender_id == msg.receiver_id:
            print(f"   ⚠️ ВНИМАНИЕ: Сообщение самому себе!")
    
    print("\n" + "="*60)
    print(f"📊 Всего сообщений: {len(messages)}")
    print("="*60)