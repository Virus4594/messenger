# tests/test_admin.py
import json
from models import User, Post, Comment
from auth import hash_password
from datetime import datetime, timezone

def login_via_session(client, user_id):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id

def create_user(db, username, role='user', is_banned=False, email_verified=True):
    user = User(
        username=username,
        email=f'{username}@example.com',
        password_hash=hash_password('Test123!'),
        role=role,
        email_verified=email_verified,
        is_banned=is_banned
    )
    db.session.add(user)
    db.session.commit()
    return user

def test_admin_dashboard_access_admin(client, db, admin_user):
    login_via_session(client, admin_user.id)
    response = client.get('/admin/')
    assert response.status_code == 200

def test_regular_user_cannot_access_admin(client, db):
    user = create_user(db, 'regular')
    login_via_session(client, user.id)
    response = client.get('/admin/')
    assert response.status_code == 403

def test_owner_can_change_role(client, db, owner_user):
    target = create_user(db, 'target', role='user')
    login_via_session(client, owner_user.id)
    
    response = client.post(f'/admin/users/{target.id}/change-role',
                          json={'role': 'moderator'},
                          content_type='application/json')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] == True
    
    updated_user = db.session.get(User, target.id)
    assert updated_user.role == 'moderator'

def test_owner_cannot_change_own_role(client, db, owner_user):
    login_via_session(client, owner_user.id)
    
    response = client.post(f'/admin/users/{owner_user.id}/change-role',
                          json={'role': 'admin'},
                          content_type='application/json')
    
    assert response.status_code == 400
    data = response.get_json()
    assert data['error'] == 'Нельзя изменить роль владельца'

def test_owner_cannot_change_owner_role(client, db, owner_user):
    another_owner = create_user(db, 'another_owner', role='owner')
    login_via_session(client, owner_user.id)
    
    response = client.post(f'/admin/users/{another_owner.id}/change-role',
                          json={'role': 'admin'},
                          content_type='application/json')
    
    assert response.status_code == 400
    data = response.get_json()
    assert data['error'] == 'Нельзя изменить роль владельца'

def test_admin_can_ban_user(client, db, admin_user):
    target = create_user(db, 'target_user', role='user')
    login_via_session(client, admin_user.id)
    
    response = client.post(f'/admin/users/{target.id}/toggle-ban',
                          content_type='application/json')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] == True
    assert data['is_banned'] == True
    
    updated_user = db.session.get(User, target.id)
    assert updated_user.is_banned == True

def test_admin_can_unban_user(client, db, admin_user):
    target = create_user(db, 'banned_user', role='user', is_banned=True)
    login_via_session(client, admin_user.id)
    
    response = client.post(f'/admin/users/{target.id}/toggle-ban',
                          content_type='application/json')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] == True
    assert data['is_banned'] == False
    
    updated_user = db.session.get(User, target.id)
    assert updated_user.is_banned == False

def test_admin_cannot_ban_owner(client, db, admin_user, owner_user):
    login_via_session(client, admin_user.id)
    
    response = client.post(f'/admin/users/{owner_user.id}/toggle-ban',
                          content_type='application/json')
    
    assert response.status_code == 400
    data = response.get_json()
    assert 'Нельзя заблокировать владельца' in data['error']

def test_admin_cannot_ban_self(client, db, admin_user):
    login_via_session(client, admin_user.id)
    
    response = client.post(f'/admin/users/{admin_user.id}/toggle-ban',
                          content_type='application/json')
    
    assert response.status_code in [400, 403]
    data = response.get_json()
    # В зависимости от логики приложения может быть разное сообщение
    assert data['error'] in ['Нельзя заблокировать себя', 'Только владелец может блокировать администраторов']

def test_moderator_can_delete_post(client, db, moderator_user):
    user = create_user(db, 'post_owner')
    
    post = Post(
        title='Test Post',
        content='Test content',
        user_id=user.id,
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(post)
    db.session.commit()
    post_id = post.id
    
    login_via_session(client, moderator_user.id)
    response = client.post(f'/admin/posts/{post_id}/delete',
                          content_type='application/json')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] == True
    assert db.session.get(Post, post_id) is None

def test_moderator_can_delete_comment(client, db, moderator_user):
    user = create_user(db, 'comment_owner')
    
    post = Post(
        title='Test Post',
        content='Test content',
        user_id=user.id,
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(post)
    db.session.commit()
    
    comment = Comment(
        content='Test comment',
        user_id=user.id,
        post_id=post.id,
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(comment)
    db.session.commit()
    comment_id = comment.id
    
    login_via_session(client, moderator_user.id)
    response = client.post(f'/admin/comments/{comment_id}/delete',
                          content_type='application/json')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] == True
    assert db.session.get(Comment, comment_id) is None