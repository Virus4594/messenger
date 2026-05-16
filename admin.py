from flask import Blueprint, render_template, request, jsonify, session
from flask_wtf.csrf import generate_csrf
from functools import wraps
from models import db, User, Post, Comment, Message, Friendship
from auth import login_required
from datetime import datetime, timedelta, timezone

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Функция для декорирования маршрутов без CSRF (будет вызвана из app.py)
def exempt_csrf_for_admin(app_csrf):
    app_csrf.exempt(admin_bp)

def owner_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        user = db.session.get(User, session.get('user_id'))
        if not user or user.role != 'owner':
            return jsonify({'error': 'Доступ запрещен. Требуются права владельца.'}), 403
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        user = db.session.get(User, session.get('user_id'))
        if not user or user.role not in ['owner', 'admin']:
            return jsonify({'error': 'Доступ запрещен. Требуются права администратора.'}), 403
        return f(*args, **kwargs)
    return decorated_function

def moderator_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        user = db.session.get(User, session.get('user_id'))
        if not user or user.role not in ['owner', 'admin', 'moderator']:
            return jsonify({'error': 'Доступ запрещен.'}), 403
        return f(*args, **kwargs)
    return decorated_function


# ============================================================
# ВСЕ МАРШРУТЫ (без декораторов CSRF, они будут добавлены в app.py)
# ============================================================

@admin_bp.route('/')
@admin_required
def dashboard():
    current_user = db.session.get(User, session.get('user_id'))
    stats = {
        'users': User.query.count(),
        'posts': Post.query.count(),
        'comments': Comment.query.count(),
        'messages': Message.query.count(),
        'online': User.query.filter_by(is_online=True).count(),
        'banned': User.query.filter_by(is_banned=True).count(),
    }
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    recent_posts = Post.query.order_by(Post.created_at.desc()).limit(10).all()
    
    return render_template('admin/dashboard.html',
                         stats=stats,
                         recent_users=recent_users,
                         recent_posts=recent_posts,
                         current_user=current_user)


@admin_bp.route('/statistics')
@admin_required
def statistics():
    today = datetime.now(timezone.utc) - timedelta(days=1)
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    
    stats = {
        'total_users': User.query.count(),
        'total_posts': Post.query.count(),
        'total_comments': Comment.query.count(),
        'total_messages': Message.query.count(),
        'active_today': User.query.filter(User.last_seen > today).count(),
        'new_this_week': User.query.filter(User.created_at > week_ago).count(),
        'online_now': User.query.filter_by(is_online=True).count(),
        'owners': User.query.filter_by(role='owner').count(),
        'admins': User.query.filter_by(role='admin').count(),
        'moderators': User.query.filter_by(role='moderator').count(),
        'regular_users': User.query.filter_by(role='user').count(),
        'banned_users': User.query.filter_by(is_banned=True).count(),
    }
    return render_template('admin/statistics.html', stats=stats)


@admin_bp.route('/users')
@admin_required
def users():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    role_filter = request.args.get('role', '')
    
    query = User.query
    if search:
        query = query.filter(User.username.contains(search) | User.email.contains(search))
    if role_filter:
        query = query.filter_by(role=role_filter)
    
    users = query.order_by(User.created_at.desc()).paginate(page=page, per_page=20)
    current_user = db.session.get(User, session.get('user_id'))
    
    return render_template('admin/users.html',
                         users=users,
                         search=search,
                         role_filter=role_filter,
                         current_user=current_user)


@admin_bp.route('/users/<int:user_id>/change-role', methods=['POST'])
@owner_required
def change_role(user_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Нет данных'}), 400
        
        new_role = data.get('role')
        if new_role not in ['user', 'moderator', 'admin']:
            return jsonify({'error': 'Неверная роль'}), 400
        
        target_user = db.session.get(User, user_id)
        current_user = db.session.get(User, session.get('user_id'))
        
        if not target_user:
            return jsonify({'error': 'Пользователь не найден'}), 404
        
        if target_user.role == 'owner':
            return jsonify({'error': 'Нельзя изменить роль владельца'}), 400
        
        if target_user.id == current_user.id:
            return jsonify({'error': 'Нельзя изменить свою роль'}), 400
        
        old_role = target_user.role
        target_user.role = new_role
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Роль изменена с "{old_role}" на "{new_role}"'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/users/<int:user_id>/toggle-ban', methods=['POST'])
@admin_required
def toggle_ban(user_id):
    try:
        target_user = db.session.get(User, user_id)
        current_user = db.session.get(User, session.get('user_id'))
        
        if not target_user:
            return jsonify({'error': 'Пользователь не найден'}), 404
        
        if target_user.role == 'owner':
            return jsonify({'error': 'Нельзя заблокировать владельца'}), 400
        
        if target_user.role == 'admin' and current_user.role != 'owner':
            return jsonify({'error': 'Только владелец может блокировать администраторов'}), 400
        
        if target_user.id == current_user.id:
            return jsonify({'error': 'Нельзя заблокировать себя'}), 400
        
        target_user.is_banned = not target_user.is_banned
        db.session.commit()
        
        return jsonify({
            'success': True,
            'is_banned': target_user.is_banned,
            'message': 'Пользователь заблокирован' if target_user.is_banned else 'Пользователь разблокирован'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@owner_required
def delete_user(user_id):
    try:
        target_user = db.session.get(User, user_id)
        current_user = db.session.get(User, session.get('user_id'))
        
        if not target_user:
            return jsonify({'error': 'Пользователь не найден'}), 404
        
        if target_user.id == current_user.id:
            return jsonify({'error': 'Нельзя удалить себя'}), 400
        
        if target_user.role == 'owner':
            return jsonify({'error': 'Нельзя удалить владельца'}), 400
        
        db.session.delete(target_user)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Пользователь удален'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/posts')
@moderator_required
def posts():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    query = Post.query
    if search:
        query = query.filter(Post.title.contains(search) | Post.content.contains(search))
    
    posts = query.order_by(Post.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('admin/posts.html', posts=posts, search=search)


@admin_bp.route('/posts/<int:post_id>/delete', methods=['POST'])
@moderator_required
def delete_post(post_id):
    try:
        post = db.session.get(Post, post_id)
        if not post:
            return jsonify({'error': 'Пост не найден'}), 404
        db.session.delete(post)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Пост удален'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/comments')
@moderator_required
def comments():
    page = request.args.get('page', 1, type=int)
    comments = Comment.query.order_by(Comment.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('admin/comments.html', comments=comments)


@admin_bp.route('/comments/<int:comment_id>/delete', methods=['POST'])
@moderator_required
def delete_comment(comment_id):
    try:
        comment = db.session.get(Comment, comment_id)
        if not comment:
            return jsonify({'error': 'Комментарий не найден'}), 404
        db.session.delete(comment)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Комментарий удален'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/settings')
@owner_required
def settings():
    return render_template('admin/settings.html')