import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'pc_builder_hard_key_2024'
    # 使用 SQLite
    SQLALCHEMY_DATABASE_URI = 'sqlite:///game_data.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # SSO 配置
    SSO_LOGIN_URL = "https://muvocal.com/auth/login"
    SSO_VERIFY_URL = "https://muvocal.com/auth/verify_token"
    SSO_CLIENT_ID = "bo_app"
    SSO_CLIENT_SECRET = "bo_secret"
    SSO_REDIRECT_URI = "https://muvocal.com/game/bo/sso_callback"

    # game.py 顶部添加配置
    CARD_CONFIG = {
        'card_1': {'name': '二位定一', 'limit': 7, 'desc': '第2位必为1'}, # 普通
        'card_2': {'name': '首位定一', 'limit': 5, 'desc': '第1位必为1'}, # 普通
        'card_3': {'name': '双星高照', 'limit': 3, 'desc': '前2位必为1'}, # 稀有
        'card_4': {'name': '三阳开泰', 'limit': 2, 'desc': '前3位必为1'}  # 传说 
    }
    #图片配置
    RED_PICTURE = "https://cdn.muvocal.com/up/2026/2/9/a0654f2b-a535-404e-a6f0-0f92c5f34b88.png"
    BLACK_PICTURE = "https://cdn.muvocal.com/up/2026/2/9/265deb34-41ef-4f9f-8495-84af758646df.png"

# 添加模块级别的变量
CARD_CONFIG = Config.CARD_CONFIG
