from flask import Flask, send_from_directory
from config import Config
from extensions import db, socketio, login_manager
from models import User
from jinja2 import FileSystemLoader
import os

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # 添加皮肤模板路径到 Jinja2 环境
    skin_template_path = os.path.join(app.root_path, 'skins', 'mubo', 'templates')
    if os.path.exists(skin_template_path):
        app.jinja_loader = FileSystemLoader([app.template_folder, skin_template_path])
        
        original_get_source = app.jinja_loader.get_source
        
        def patched_get_source(environment, template):
            if '/' in template:
                prefix, name = template.split('/', 1)
                if prefix == 'mubo':
                    skin_path = os.path.join(skin_template_path, name)
                    if os.path.exists(skin_path):
                        with open(skin_path, 'r', encoding='utf-8') as f:
                            return f.read(), skin_path, lambda: True
            return original_get_source(environment, template)
        
        app.jinja_loader.get_source = patched_get_source

    # 初始化扩展
    db.init_app(app)
    # 本地测试用
    socketio.init_app(app)
    # 部署到服务器用
    #socketio.init_app(app, path='/game/bo/socket.io', cors_allowed_origins="*")
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
    
    # 添加皮肤文件路由
    @app.route('/skins/<path:filename>')
    def serve_skin_file(filename):
        skin_dir = os.path.join(app.root_path, 'skins')
        return send_from_directory(skin_dir, filename)

    return app

# User Loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

app = create_app()

if __name__ == '__main__':
    socketio.run(app, port=5212, debug=True)