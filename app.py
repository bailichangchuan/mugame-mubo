from flask import Flask
from config import Config
from extensions import db, socketio, login_manager
from models import User

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # 初始化扩展
    db.init_app(app)
    socketio.init_app(app)
    login_manager.init_app(app)

    # 注册蓝图
    from routes.auth import auth_bp
    from routes.room import room_bp
    # game.py 没有蓝图，它通过 socketio 事件工作，但需要被导入以注册事件
    import routes.game 

    app.register_blueprint(auth_bp)
    app.register_blueprint(room_bp) # 挂载在根路径或你喜欢的路径

    # 创建数据库表
    with app.app_context():
        db.create_all()

    return app

# User Loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

app = create_app()

if __name__ == '__main__':
    socketio.run(app, port=5212, debug=True)