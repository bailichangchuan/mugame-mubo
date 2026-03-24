from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_login import LoginManager

db = SQLAlchemy()
socketio = SocketIO()
# socketio = SocketIO(
#     path='/game/bo/socket.io',
#     cors_allowed_origins='*',
#     manage_session=False,
#     async_mode='eventlet'
# )
login_manager = LoginManager()
login_manager.login_view = 'auth.login'