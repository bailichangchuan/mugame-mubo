from flask import Blueprint, request, redirect, url_for, session, current_app
from flask_login import login_user, logout_user
import requests
from models import User
from extensions import db, login_manager

# 设定 url_prefix 为 /game/bo
auth_bp = Blueprint('auth', __name__, url_prefix='/game/bo')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # 从 current_app.config 获取配置
    sso_login_url = current_app.config.get('SSO_LOGIN_URL')
    client_id = current_app.config.get('SSO_CLIENT_ID')
    redirect_uri = current_app.config.get('SSO_REDIRECT_URI')
    
    # 跳转到 SSO 登录页面
    return redirect(f"{sso_login_url}?client_id={client_id}&redirect_uri={redirect_uri}")

@auth_bp.route('/sso_callback')
def sso_callback():
    # 从 SSO 回调中获取 token
    token = request.args.get('token')
    if not token:
        return "认证失败：未接收到 token", 401
    
    # 获取验证 URL 配置
    sso_verify_url = current_app.config.get('SSO_VERIFY_URL')
    
    # 验证 token
    try:
        verify_response = requests.get(
            f"{sso_verify_url}?token={token}",
            headers={'Accept': 'application/json'}
        )
    except requests.RequestException:
        return "认证服务器连接失败", 500
    
    if verify_response.status_code != 200 or not verify_response.json().get('valid'):
        return "认证失败：无效的 token", 401
    
    # 获取用户信息
    user_info = verify_response.json().get('user', {})
    username = user_info.get('username')
    email = user_info.get('email')

    if not username:
        return "认证失败：用户信息不完整", 400

    # 从数据库加载或创建用户
    user = User.query.filter_by(username=username).first()
    if user:
        # 用户已存在，直接登录
        login_user(user)
    else:
        # 用户不存在，创建新用户
        user = User(username=username, email=email)
        db.session.add(user)
        db.session.commit()
        login_user(user)
    
    session.permanent = True
    
    # 登录成功，重定向到游戏首页或 API 提示
    # 假设前端首页在根路径，或者你可以重定向到一个 JSON 响应
    return redirect(url_for('room.index')) 

@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('room.index'))

# Flask-Login 用户加载回调
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))