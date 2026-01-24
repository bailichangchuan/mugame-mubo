import eventlet
# 【必须】在导入其他库之前打补丁，让标准库支持协程
eventlet.monkey_patch()

from flask import Flask
from config import Config
from extensions import db, socketio, login_manager
from models import User

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # 初始化扩展
    db.init_app(app)
    login_manager.init_app(app)
    
    # 【修改】加入 async_mode='eventlet'
    # path 参数保持你原有的设置，配合 Nginx
    socketio.init_app(app, 
                      path='/bo/socket.io', 
                      cors_allowed_origins="*", 
                      async_mode='eventlet')
    
    # 注册蓝图
    from routes.auth import auth_bp
    from routes.room import room_bp
    
    # 导入 game 模块以注册 SocketIO 事件
    import routes.game 

    app.register_blueprint(auth_bp)
    app.register_blueprint(room_bp)

    # 创建数据库表
    with app.app_context():
        db.create_all()

    return app

# User Loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 创建全局 app 对象，供 Gunicorn 导入
app = create_app()

if __name__ == '__main__':
    # 这里的设置仅在直接运行 python3 app.py 时生效（开发环境）
    # 生产环境 Gunicorn 会忽略这里
    socketio.run(app, host='0.0.0.0', port=5211, debug=True)
