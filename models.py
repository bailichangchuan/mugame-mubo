from flask_login import UserMixin
from extensions import db
from datetime import datetime
import json

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120))
    games_played = db.Column(db.Integer, default=0)  # 下棋数
    games_won = db.Column(db.Integer, default=0)     # 获胜数

class Map(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)  # 地图标识符
    display_name = db.Column(db.String(100), nullable=False)  # 地图显示名称
    description = db.Column(db.Text)  # 地图描述
    width = db.Column(db.Integer, nullable=False)  # 地图宽度
    height = db.Column(db.Integer, nullable=False)  # 地图高度
    data = db.Column(db.Text, nullable=False)  # 地图数据（JSON格式）
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))  # 创建者
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # 创建时间
    
    def get_data(self):
        return json.loads(self.data) if self.data else {}
    
    def set_data(self, data):
        self.data = json.dumps(data)

class GameRoom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player1_id = db.Column(db.Integer, db.ForeignKey('user.id')) # 红方
    player2_id = db.Column(db.Integer, db.ForeignKey('user.id')) # 黑方
    map_id = db.Column(db.Integer, db.ForeignKey('map.id'), default=1) # 使用的地图
    status = db.Column(db.String(20), default='waiting') # waiting, playing, finished
    winner_id = db.Column(db.Integer, nullable=True)
    player1_streak = db.Column(db.Integer, default=0) # 红方连续胜利次数
    player2_streak = db.Column(db.Integer, default=0) # 黑方连续胜利次数
    
    # 游戏状态存储为 JSON
    # 包含: board_layout, current_turn(player_id), steps_left(int)
    state = db.Column(db.Text, default='{}')

    def get_state(self):
        return json.loads(self.state) if self.state else {}

    def set_state(self, data):
        self.state = json.dumps(data)

class Terrain(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    terrain_id = db.Column(db.String(50), unique=True, nullable=False)  # 地形标识符
    name = db.Column(db.String(100), nullable=False)  # 地形名称
    description = db.Column(db.Text)  # 地形描述
    passability = db.Column(db.Integer, default=1)  # 可通行性 0-不可通行, 1-可通行
    move_cost = db.Column(db.Integer, default=1)  # 移动成本
    combat_bonus = db.Column(db.Float, default=1.0)  # 战斗加成
    color = db.Column(db.String(20), default='#f0e6d2')  # 地形颜色
    picture_url = db.Column(db.String(20))

class Piece(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    piece_id = db.Column(db.String(50), unique=True, nullable=False)  # 棋子标识符
    name = db.Column(db.String(100), nullable=False)  # 棋子名称
    description = db.Column(db.Text)  # 棋子描述
    move_range = db.Column(db.Integer, default=1)  # 移动范围
    combat_range = db.Column(db.Integer, default=1)  # 攻击范围
    move_cost = db.Column(db.Float, default=1.0)  # 移动成本，即移动一格所需要的成本
    base_power = db.Column(db.Float, default=1.0)  # 基础攻击力（作为攻击方时的倍率）
    defense_power = db.Column(db.Float, default=1.0)  # 防守方倍率
    attack_coop = db.Column(db.Float, default=1.0)  # 攻击连携倍率
    defense_coop = db.Column(db.Float, default=1.0)  # 防守连携倍率
    coop_range = db.Column(db.Integer, default=1)  # 连携范围
    attack_type = db.Column(db.String(20), default='melee')  # 攻击类型: melee(近战), ranged(远程)
    piece_picture = db.Column(db.String(20))  # 棋子图片URL
    terrain_change = db.Column(db.Boolean, default=False)  # 是否改变地形

class CombatLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('game_room.id'), nullable=False)  # 游戏房间ID
    combat_sequence = db.Column(db.Integer, nullable=False, default=1)  # 战斗顺序ID（该对局中的第几场战斗）
    turn_number = db.Column(db.Integer, nullable=False)  # 回合数
    attacker_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # 进攻方用户ID
    defender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # 防守方用户ID
    attacker_sticks = db.Column(db.Text, nullable=False)  # 进攻方抽签结果 (JSON格式)
    defender_sticks = db.Column(db.Text, nullable=False)  # 防守方抽签结果 (JSON格式)
    attacker_binary = db.Column(db.String(10), nullable=False)  # 进攻方二进制结果
    defender_binary = db.Column(db.String(10), nullable=False)  # 防守方二进制结果
    attacker_power = db.Column(db.Float, nullable=False)  # 进攻方最终战力
    defender_power = db.Column(db.Float, nullable=False)  # 防守方最终战力
    attacker_piece = db.Column(db.String(10), nullable=False)  # 进攻方棋子类型
    defender_piece = db.Column(db.String(10), nullable=False)  # 防守方棋子类型
    attacker_card = db.Column(db.String(20), nullable=True)  # 进攻方使用的锦囊牌
    defender_card = db.Column(db.String(20), nullable=True)  # 防守方使用的锦囊牌
    winner = db.Column(db.String(20), nullable=False)  # 战斗胜利者: attacker, defender, draw
    distance = db.Column(db.Integer, nullable=False)  # 攻击距离
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # 记录创建时间
    
    def get_attacker_sticks(self):
        try:
            return json.loads(self.attacker_sticks) if self.attacker_sticks else []
        except (json.JSONDecodeError, TypeError):
            return []
    
    def set_attacker_sticks(self, sticks):
        try:
            self.attacker_sticks = json.dumps(sticks)
        except (json.JSONDecodeError, TypeError):
            self.attacker_sticks = '[]'
    
    def get_defender_sticks(self):
        try:
            return json.loads(self.defender_sticks) if self.defender_sticks else []
        except (json.JSONDecodeError, TypeError):
            return []
    
    def set_defender_sticks(self, sticks):
        try:
            self.defender_sticks = json.dumps(sticks)
        except (json.JSONDecodeError, TypeError):
            self.defender_sticks = '[]'