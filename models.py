from flask_login import UserMixin
from extensions import db
import json

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120))

class GameRoom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player1_id = db.Column(db.Integer, db.ForeignKey('user.id')) # 红方
    player2_id = db.Column(db.Integer, db.ForeignKey('user.id')) # 黑方
    status = db.Column(db.String(20), default='waiting') # waiting, playing, finished
    winner_id = db.Column(db.Integer, nullable=True)
    
    # 游戏状态存储为 JSON
    # 包含: board_layout, current_turn(player_id), steps_left(int)
    state = db.Column(db.Text, default='{}')

    def get_state(self):
        return json.loads(self.state) if self.state else {}

    def set_state(self, data):
        self.state = json.dumps(data)