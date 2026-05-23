from operator import or_, and_
from datetime import datetime, timedelta, timezone
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import validates
from flask_migrate import Migrate

db = SQLAlchemy()

# Ассоциативные таблицы
post_likes = db.Table('post_likes',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), primary_key=True)
)

class Friendship(db.Model):
    __tablename__ = 'friendships'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    friend_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    action_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    user = db.relationship('User', foreign_keys=[user_id], backref='initiated_friendships')
    friend = db.relationship('User', foreign_keys=[friend_id], backref='received_friendships')
    action_user = db.relationship('User', foreign_keys=[action_user_id])
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'friend_id', name='unique_friendship'),
    )

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    email_verified = db.Column(db.Boolean, default=False)
    verification_token = db.Column(db.String(200), nullable=True)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    last_seen = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    is_online = db.Column(db.Boolean, default=False)
    
    # 2FA
    otp_secret = db.Column(db.String(32))
    is_2fa_enabled = db.Column(db.Boolean, default=False)

    # E2EE ключи (без лишних отступов!)
    public_key = db.Column(db.Text, nullable=True)
    private_key_encrypted = db.Column(db.Text, nullable=True)
    key_derivation_salt = db.Column(db.String(64), nullable=True)
    encryption_algorithm = db.Column(db.String(20), default='AES-256-GCM')
    
    role = db.Column(db.String(20), default='user')
    is_banned = db.Column(db.Boolean, default=False)
    ban_reason = db.Column(db.String(500), nullable=True)
    banned_until = db.Column(db.DateTime, nullable=True)
    banned_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Кто назначил роль
    role_assigned_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    role_assigned_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    avatar = db.Column(db.String(200), nullable=True)  # Путь к аватарке
    avatar_thumb = db.Column(db.String(200), nullable=True)  # Миниатюра

    # Отношения
    posts = db.relationship('Post', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', 
                                   backref='sender', lazy='dynamic')
    received_messages = db.relationship('Message', foreign_keys='Message.receiver_id', 
                                       backref='receiver', lazy='dynamic')
    comments = db.relationship('Comment', backref='author', lazy='dynamic')
    
    @property
    def friends(self):
        friends_as_user = User.query.join(
            Friendship, Friendship.friend_id == User.id
        ).filter(
            Friendship.user_id == self.id,
            Friendship.status == 'accepted'
        ).all()
        
        friends_as_friend = User.query.join(
            Friendship, Friendship.user_id == User.id
        ).filter(
            Friendship.friend_id == self.id,
            Friendship.status == 'accepted'
        ).all()
        
        all_friends = list(set(friends_as_user + friends_as_friend))
        return all_friends
    
    def get_friends(self):
        return self.friends
    
    def is_friend(self, other_user):
        friendship = Friendship.query.filter(
            (
                (Friendship.user_id == self.id) & 
                (Friendship.friend_id == other_user.id) & 
                (Friendship.status == 'accepted')
            ) | (
                (Friendship.user_id == other_user.id) & 
                (Friendship.friend_id == self.id) & 
                (Friendship.status == 'accepted')
            )
        ).first()
        return friendship is not None

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    comments = db.relationship('Comment', backref='post', lazy='dynamic', 
                              cascade='all, delete-orphan')
    likes = db.relationship('User', secondary=post_likes, backref=db.backref('liked_posts', lazy='dynamic'))

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    encrypted_content = db.Column(db.Text, nullable=True)  # Зашифрованное сообщение (может быть NULL для стикеров/вложений)
    sticker_id = db.Column(db.Integer, nullable=True)  # ID стикера
    encryption_nonce = db.Column(db.String(100), nullable=True)  # Nonce для расшифровки
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime, nullable=True)

    # Отправитель и получатель
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Вложения
    is_attachment = db.Column(db.Boolean, default=False)
    attachment = db.Column(db.String(500), nullable=True)  # Путь к файлу
    attachment_type = db.Column(db.String(50), nullable=True)  # image, file, video
    attachment_name = db.Column(db.String(200), nullable=True)  # Оригинальное имя
    attachment_size = db.Column(db.Integer, nullable=True)  # Размер в KB
    
    # E2EE поля
    encrypted_attachment_key = db.Column(db.Text, nullable=True)  # Ключ для вложений
    is_encrypted = db.Column(db.Boolean, default=True)
    encryption_version = db.Column(db.String(10), default='1.0')

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.now(timezone.utc)



class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    type = db.Column(db.String(50), nullable=False)
    content = db.Column(db.String(500))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    related_id = db.Column(db.Integer)
    
    user = db.relationship('User', foreign_keys=[user_id], backref='notifications')
    sender = db.relationship('User', foreign_keys=[sender_id])

class Reaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    emoji = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    
    message = db.relationship('Message', backref='reactions')
    user = db.relationship('User', backref='reactions')
    
    __table_args__ = (
        db.UniqueConstraint('message_id', 'user_id', name='unique_user_message_reaction'),
    )


# ========================
# ГРУППОВЫЕ ЧАТЫ
# ========================

class ChatGroup(db.Model):
    """Групповой чат"""
    __tablename__ = 'chat_groups'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    avatar = db.Column(db.String(200), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    is_private = db.Column(db.Boolean, default=False)
    invite_code = db.Column(db.String(50), unique=True, nullable=True)
    
    # E2EE для группы: общий ключ, зашифрованный для каждого участника
    group_public_key = db.Column(db.Text, nullable=True)  # публичный ключ группы
    encrypted_group_key = db.Column(db.Text, nullable=True)  # зашифрованный ключ группы
    
    # Связи
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_groups')
    members = db.relationship('GroupMember', backref='group', lazy='dynamic', cascade='all, delete-orphan')
    messages = db.relationship('GroupMessage', backref='group', lazy='dynamic', cascade='all, delete-orphan')
    
    @property
    def member_count(self):
        return self.members.count()
    
    @property
    def member_list(self):
        return [m.user for m in self.members.all()]


class GroupMember(db.Model):
    """Участник группы"""
    __tablename__ = 'group_members'
    
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('chat_groups.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    role = db.Column(db.String(20), default='member')  # admin, member
    joined_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    is_muted = db.Column(db.Boolean, default=False)
    
    # Для E2EE: зашифрованная копия ключа группы для этого участника
    encrypted_group_key_for_user = db.Column(db.Text, nullable=True)
    
    # Связи
    user = db.relationship('User', foreign_keys=[user_id], backref='group_memberships')
    
    __table_args__ = (db.UniqueConstraint('group_id', 'user_id', name='unique_group_member'),)


class GroupMessage(db.Model):
    """Сообщение в группе"""
    __tablename__ = 'group_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('chat_groups.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # E2EE поля (сообщение шифруется групповым ключом)
    encrypted_content = db.Column(db.Text, nullable=True)
    encryption_nonce = db.Column(db.String(100), nullable=True)
    
    # Стикеры и вложения
    sticker_id = db.Column(db.Integer, nullable=True)
    sticker_code = db.Column(db.String(10), nullable=True)
    is_attachment = db.Column(db.Boolean, default=False)
    attachment = db.Column(db.String(500), nullable=True)
    attachment_type = db.Column(db.String(50), nullable=True)
    attachment_name = db.Column(db.String(200), nullable=True)
    attachment_size = db.Column(db.Integer, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    
    # Кто прочитал (JSON массив ID пользователей)
    read_by = db.Column(db.Text, default='[]')
    
    # Связи
    group = db.relationship('ChatGroup', foreign_keys=[group_id])
    sender = db.relationship('User', foreign_keys=[sender_id], backref='group_messages')
    
    def mark_as_read(self, user_id):
        import json
        read_list = json.loads(self.read_by) if self.read_by else []
        if user_id not in read_list:
            read_list.append(user_id)
            self.read_by = json.dumps(read_list)
    
    @property
    def is_read_by_all(self):
        import json
        read_list = json.loads(self.read_by) if self.read_by else []
        group_size = GroupMember.query.filter_by(group_id=self.group_id).count()
        return len(read_list) >= group_size - 1  # минус отправитель