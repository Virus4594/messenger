# tests/test_chat.py
import pytest
from models import Message, User, Friendship
from auth import hash_password
from datetime import datetime, timezone

def login_via_session(client, user_id):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id

def create_user(db, username, email_verified=True):
    user = User(
        username=username,
        email=f'{username}@example.com',
        password_hash=hash_password('Test123!'),
        role='user',
        email_verified=email_verified
    )
    db.session.add(user)
    db.session.commit()
    return user

def create_friendship(db, user1, user2, status='accepted'):
    friendship = Friendship(
        user_id=user1.id,
        friend_id=user2.id,
        status=status
    )
    db.session.add(friendship)
    db.session.commit()
    return friendship

def test_message_encryption_flag(client, db):
    user1 = create_user(db, 'alice')
    user2 = create_user(db, 'bob')
    create_friendship(db, user1, user2)
    
    msg = Message(
        sender_id=user1.id,
        receiver_id=user2.id,
        encrypted_content="dummy_encrypted_base64_string",
        encryption_nonce="dummy_nonce_base64",
        is_encrypted=True,
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(msg)
    db.session.commit()
    
    saved_msg = Message.query.first()
    assert saved_msg is not None
    assert saved_msg.is_encrypted == True
    assert saved_msg.encrypted_content is not None
    assert saved_msg.encryption_nonce is not None

def test_message_sticker(client, db):
    user1 = create_user(db, 'sticker_sender')
    user2 = create_user(db, 'sticker_receiver')
    create_friendship(db, user1, user2)
    
    msg = Message(
        sender_id=user1.id,
        receiver_id=user2.id,
        sticker_id=1,
        is_encrypted=True,
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(msg)
    db.session.commit()
    
    saved_msg = Message.query.first()
    assert saved_msg is not None
    assert saved_msg.sticker_id == 1

def test_chat_only_between_friends(client, db):
    user1 = create_user(db, 'alice')
    user2 = create_user(db, 'bob')
    user3 = create_user(db, 'charlie')
    
    create_friendship(db, user1, user2)
    
    login_via_session(client, user1.id)
    
    # Должен иметь доступ к чату с другом
    response = client.get(f'/chat/{user2.username}')
    assert response.status_code == 200
    
    # Не должен иметь доступ к чату с не-другом
    response = client.get(f'/chat/{user3.username}', follow_redirects=True)
    assert response.status_code == 200
    assert 'Вы можете писать только друзьям' in response.data.decode('utf-8')

def test_message_read_status(client, db):
    user1 = create_user(db, 'sender')
    user2 = create_user(db, 'receiver')
    create_friendship(db, user1, user2)
    
    msg = Message(
        sender_id=user1.id,
        receiver_id=user2.id,
        encrypted_content="test_encrypted",
        is_encrypted=True,
        is_read=False
    )
    db.session.add(msg)
    db.session.commit()
    
    assert msg.is_read == False
    
    login_via_session(client, user2.id)
    response = client.post('/api/messages/read', content_type='application/json')
    
    assert response.status_code == 200
    updated_msg = db.session.get(Message, msg.id)
    assert updated_msg.is_read == True

def test_messages_api_requires_auth(client, db):
    response = client.get('/api/messages/1')
    assert response.status_code == 401

def test_get_messages_with_friend(client, db):
    user1 = create_user(db, 'friend1')
    user2 = create_user(db, 'friend2')
    create_friendship(db, user1, user2)
    
    msg = Message(
        sender_id=user1.id,
        receiver_id=user2.id,
        encrypted_content="encrypted_hello_world",
        encryption_nonce="test_nonce_123",
        is_encrypted=True,
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(msg)
    db.session.commit()
    
    login_via_session(client, user1.id)
    response = client.get(f'/api/messages/{user2.id}')
    
    assert response.status_code == 200
    data = response.get_json()
    assert 'messages' in data
    assert len(data['messages']) >= 1
    # Проверяем, что сообщение зашифровано
    if len(data['messages']) > 0:
        assert data['messages'][0]['is_encrypted'] == True
        assert 'encrypted' in data['messages'][0]['text']

def test_send_message_to_non_friend_blocked(client, db):
    user1 = create_user(db, 'user1')
    user2 = create_user(db, 'user2')
    # Нет дружбы
    
    login_via_session(client, user1.id)
    
    response = client.get(f'/chat/{user2.username}', follow_redirects=True)
    assert 'Вы можете писать только друзьям' in response.data.decode('utf-8')
    
    api_response = client.get(f'/api/messages/{user2.id}')
    assert api_response.status_code == 403