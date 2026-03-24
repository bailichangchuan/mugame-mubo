from flask import Blueprint, render_template, redirect, url_for, jsonify, request
from flask_login import login_required, current_user
from flask_socketio import emit, join_room
from extensions import db, socketio
from config import Config  # 修改这一行
from models import GameRoom, User, CombatLog
from map_loader import MapLoader, MapData
import random

# 然后在使用的地方修改为
CARD_CONFIG = Config.CARD_CONFIG  # 添加这一行

room_bp = Blueprint('room', __name__, url_prefix='/game/bo')

# --- 页面路由 (HTTP View) ---

@room_bp.route('/')
def index():
    """首页：显示创建和加入表单"""
    # if not current_user.is_authenticated:
    #     return redirect('/game/bo/login')
    return render_template('home.html', user=current_user)

@room_bp.route('/guide')
def game_guide():
    """游戏说明页面"""
    return render_template('game_guide.html')

@room_bp.route('/room/<int:room_id>')
@login_required
def room_view(room_id):
    """房间页：根据状态分发到 等待页 或 游戏页"""
    room = GameRoom.query.get_or_404(room_id)
    
    # 获取双方名字用于显示
    p1 = User.query.get(room.player1_id)
    p2 = User.query.get(room.player2_id) if room.player2_id else None

    context = {
        'room': room,
        'p1_name': p1.username if p1 else '未知',
        'p2_name': p2.username if p2 else '等待加入...',
        'user': current_user
    }

    if room.status == 'waiting':
        return render_template('waiting.html', **context)
    else:
        # 游戏进行中或已结束，渲染游戏页
        return render_template('game.html', **context)

@room_bp.route('/ai-room/<int:room_id>')
@login_required
def ai_room_view(room_id):  # 修改函数名
    """AI房间页：根据状态分发到 等待页 或 游戏页"""
    room = GameRoom.query.get_or_404(room_id)
    
    # 获取双方名字用于显示
    p1 = User.query.get(room.player1_id)
    p2 = "AI" 

    context = {
        'room': room,
        'p1_name': p1.username if p1 else '未知',
        'p2_name': p2,
        'user': current_user
    }

    if room.status == 'waiting':
        return render_template('waiting.html', **context)
    else:
        # 游戏进行中或已结束，渲染游戏页
        return render_template('game.html', **context)

# --- API 接口 (用于表单提交，返回JSON让前端跳转) ---

@room_bp.route('/api/create', methods=['POST'])
@login_required
# 在创建房间时初始化卡片数据
def create_room_api():
    # 获取请求数据
    data = request.json
    map_name = data.get('map_name', 'default_map')
    
    # 加载地图数据
    map_data = MapLoader.load_map(map_name)
    map_info = MapData(map_data)
    
    # 初始化棋盘
    width = map_info.width
    height = map_info.height
    initial_board = []
    for _ in range(height): initial_board.append([None] * width)
    
    # 根据地图数据设置初始棋子
    # 红方 (R)
    for piece in map_info.get_initial_pieces('R'):
        x, y = piece['x'], piece['y']
        if 0 <= y < height and 0 <= x < width:
            initial_board[y][x] = {'type': piece['type'], 'side': 'R'}
    
    # 黑方 (B)
    for piece in map_info.get_initial_pieces('B'):
        x, y = piece['x'], piece['y']
        if 0 <= y < height and 0 <= x < width:
            initial_board[y][x] = {'type': piece['type'], 'side': 'B'}

    # 【新增】初始化玩家卡牌库存
    # 结构: cards = { player_id: { 'card_1': 5, 'card_4': 2 ... } }
    initial_cards = {}
    
    # 1. 为创建者 (当前用户) 发放卡牌
    # 确保 CARD_CONFIG 在文件顶部已经引入或定义了
    initial_cards[str(current_user.id)] = {k: v['limit'] for k, v in CARD_CONFIG.items()}

    # 构建游戏状态
    game_state = {
        'board': initial_board,
        'turn': current_user.id,
        'turn_number': 1,              # 初始化回合数为1
        'steps_left': 0,
        'has_rolled': False,
        'winner': None,
        'cards': initial_cards,        # 此时里面只有 P1 的卡牌
        'active_card': None,           # 旧字段 (为了兼容性可留)
        'active_cards': {},            # 【建议】初始化新的多用户激活字典
        'terrain': map_data['terrain'], # 保存地形数据
        'terrain_types': map_data['terrain_types'], # 保存地形类型
        'piece_types': map_data['piece_types'] # 保存棋子类型
    }

    new_room = GameRoom(player1_id=current_user.id, status='waiting')
    new_room.set_state(game_state)
    db.session.add(new_room)
    db.session.commit()

    return jsonify({'success': True, 'room_id': new_room.id})

@room_bp.route('/api/join', methods=['POST'])
@login_required
def join_room_api():
    data = request.json
    room_id = data.get('room_id')
    room = GameRoom.query.get(room_id)
    
    if not room:
        return jsonify({'success': False, 'msg': '房间不存在'})
    
    if room.status == 'waiting' and room.player1_id != current_user.id:
        room.player2_id = current_user.id
        room.status = 'playing' # 状态改变！
        
        # 【新增】给加入的玩家发放卡片
        state = room.get_state()
        # 确保 cards 字典存在
        if 'cards' not in state:
            state['cards'] = {}
        # 给新用户发放卡片
        state['cards'][str(current_user.id)] = {k: v['limit'] for k, v in CARD_CONFIG.items()}
        room.set_state(state)
        
        # 【新增】增加双方玩家的棋局数
        p1 = User.query.get(room.player1_id)
        p2 = User.query.get(current_user.id)
        if p1:
            p1.games_played += 1
        if p2:
            p2.games_played += 1
        
        db.session.commit()
        
        # 通知已经在等待页面的房主：游戏开始了，请刷新
        socketio.emit('player_joined_event', {'room_id': room.id}, room=str(room.id))
        return jsonify({'success': True, 'room_id': room.id})
    
    # 或者是断线重连/观战
    if room.player1_id == current_user.id or room.player2_id == current_user.id:
        # 断线重连时检查卡片是否存在
        state = room.get_state()
        if 'cards' not in state:
            state['cards'] = {}
        # 如果用户没有卡片，发放一套
        if str(current_user.id) not in state['cards']:
            state['cards'][str(current_user.id)] = {k: v['limit'] for k, v in CARD_CONFIG.items()}
            room.set_state(state)
            db.session.commit()
        return jsonify({'success': True, 'room_id': room.id})
    
    return jsonify({'success': False, 'msg': '无法加入该房间'})

# --- SocketIO 事件 (保持连接逻辑) ---

from flask import request # 确保头部引入了 request

@socketio.on('connect_to_room')
def on_connect_room(data):
    """
    前端加载页面后主动发送此事件来绑定Socket房间
    修复点：连接成功后，立即把当前棋盘状态发给这个用户
    """
    room_id = data.get('room_id')
    join_room(str(room_id))
    
    # 获取房间数据
    room = GameRoom.query.get(room_id)
    if room:
        # 【关键修复】：立即发送当前状态给刚刚连接的用户 (request.sid)
        # 这样用户一进网页就能看到棋子，而不需要等别人动
        emit('board_update', {
            'state': room.get_state()
        }, room=request.sid)

@room_bp.route('/result/<int:room_id>')
@login_required
def result_view(room_id):
    """游戏结算页面"""
    room = GameRoom.query.get_or_404(room_id)
    
    # 获取游戏最终状态
    state = room.get_state()
    winner_side = state.get('winner') # 'R' 或 'B'
    
    winner_name = "未知"
    
    # 根据 winner_side 判断获胜的用户名
    if winner_side == 'R':
        user = User.query.get(room.player1_id)
        if user: winner_name = user.username
    elif winner_side == 'B':
        user = User.query.get(room.player2_id)
        if user: winner_name = user.username

    return render_template('result.html', 
                           room_id=room.id, 
                           winner_side=winner_side, 
                           winner_name=winner_name,
                           user=current_user)

@room_bp.route('/map-editor')
@login_required
def map_editor_view():
    """地图编辑器页面"""
    return render_template('map_editor.html', user=current_user)

@room_bp.route('/rankings')
@login_required
def rankings_view():
    """用户排名页面"""
    return render_template('rankings.html', user=current_user)

@room_bp.route('/api/save-map', methods=['POST'])
@login_required
def save_map_api():
    """保存地图数据"""
    from map_loader import MapLoader
    
    data = request.json
    map_name = data.get('map_name')
    map_data = data.get('map_data')
    
    if not map_name or not map_data:
        return jsonify({'success': False, 'msg': '缺少必要参数'})
    
    try:
        # 保存地图到数据库
        MapLoader.save_map(map_data, map_name, created_by=current_user.id)
        
        return jsonify({'success': True, 'msg': '地图保存成功'})
        
    except Exception as e:
        return jsonify({'success': False, 'msg': f'保存失败: {str(e)}'})

@room_bp.route('/api/create-ai', methods=['POST'])
@login_required
def create_ai_room_api():
    """创建AI游戏房间"""
    # 获取请求数据
    data = request.json
    map_name = data.get('map_name', 'default_map')
    
    # 加载地图数据
    from map_loader import MapLoader
    map_data = MapLoader.load_map(map_name)
    
    # 初始化棋盘
    width = map_data['map_info']['width']
    height = map_data['map_info']['height']
    initial_board = []
    for _ in range(height): initial_board.append([None] * width)
    
    # 根据地图数据设置初始棋子
    # 红方 (R)
    for piece in map_data['initial_pieces']['R']:
        x, y = piece['x'], piece['y']
        if 0 <= y < height and 0 <= x < width:
            initial_board[y][x] = {'type': piece['type'], 'side': 'R'}
    
    # 黑方 (B)
    for piece in map_data['initial_pieces']['B']:
        x, y = piece['x'], piece['y']
        if 0 <= y < height and 0 <= x < width:
            initial_board[y][x] = {'type': piece['type'], 'side': 'B'}

    # 初始化卡牌
    initial_cards = {}
    initial_cards[str(current_user.id)] = {k: v['limit'] for k, v in CARD_CONFIG.items()}

    # 构建游戏状态
    game_state = {
        'board': initial_board,
        'turn': current_user.id,
        'turn_number': 1,              # 初始化回合数为1
        'steps_left': 0,
        'has_rolled': False,
        'winner': None,
        'cards': initial_cards,
        'active_card': None,
        'active_cards': {},
        'terrain': map_data['terrain'],
        'terrain_types': map_data['terrain_types'],
        'piece_types': map_data['piece_types']
    }

    new_room = GameRoom(player1_id=current_user.id, status='waiting')
    new_room.set_state(game_state)
    db.session.add(new_room)
    
    # 【新增】增加玩家的棋局数
    user = User.query.get(current_user.id)
    if user:
        user.games_played += 1
    
    db.session.commit()

    return jsonify({'success': True, 'room_id': new_room.id})

@room_bp.route('/api/get-maps')
@login_required
def get_maps_api():
    """获取可用地图列表"""
    from map_loader import MapLoader
    
    try:
        maps = MapLoader.get_available_maps()
        map_list = []
        
        for map_name in maps:
            try:
                map_data = MapLoader.load_map(map_name)
                map_list.append({
                    'name': map_name,
                    'display_name': map_data['map_info']['name'],
                    'width': map_data['map_info']['width'],
                    'height': map_data['map_info']['height']
                })
            except Exception as e:
                # 跳过无效的地图文件
                pass
        
        return jsonify({'success': True, 'maps': map_list})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})

@room_bp.route('/api/update-terrain', methods=['POST'])
@login_required
def update_terrain_api():
    """更新地形数据"""
    from models import Terrain
    
    try:
        data = request.json
        terrain_id = data.get('terrain_id')
        terrain_data = data.get('terrain_data')
        
        if not terrain_id or not terrain_data:
            return jsonify({'success': False, 'msg': '缺少必要参数'})
        
        # 查找地形
        terrain = Terrain.query.filter_by(terrain_id=terrain_id).first()
        if not terrain:
            # 如果地形不存在，创建新地形
            terrain = Terrain(terrain_id=terrain_id)
            db.session.add(terrain)
        
        # 更新地形数据
        for key, value in terrain_data.items():
            if hasattr(terrain, key):
                setattr(terrain, key, value)
        
        db.session.commit()
        return jsonify({'success': True, 'msg': '地形数据更新成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'msg': str(e)})

@room_bp.route('/api/delete-terrain', methods=['POST'])
@login_required
def delete_terrain_api():
    """删除地形数据"""
    from models import Terrain
    
    try:
        data = request.json
        terrain_id = data.get('terrain_id')
        
        if not terrain_id:
            return jsonify({'success': False, 'msg': '缺少必要参数'})
        
        # 查找地形
        terrain = Terrain.query.filter_by(terrain_id=terrain_id).first()
        if not terrain:
            return jsonify({'success': False, 'msg': '地形不存在'})
        
        # 不能删除平原地形
        if terrain_id == 'plain':
            return jsonify({'success': False, 'msg': '不能删除平原地形'})
        
        # 删除地形
        db.session.delete(terrain)
        db.session.commit()
        return jsonify({'success': True, 'msg': '地形数据删除成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'msg': str(e)})

@room_bp.route('/api/update-piece', methods=['POST'])
@login_required
def update_piece_api():
    """更新棋子数据"""
    from models import Piece
    
    try:
        data = request.json
        piece_id = data.get('piece_id')
        piece_data = data.get('piece_data')
        
        if not piece_id or not piece_data:
            return jsonify({'success': False, 'msg': '缺少必要参数'})
        
        # 查找棋子
        piece = Piece.query.filter_by(piece_id=piece_id).first()
        if not piece:
            # 如果棋子不存在，创建新棋子
            piece = Piece(piece_id=piece_id)
            db.session.add(piece)
        
        # 更新棋子数据
        for key, value in piece_data.items():
            if hasattr(piece, key):
                setattr(piece, key, value)
        
        db.session.commit()
        return jsonify({'success': True, 'msg': '棋子数据更新成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'msg': str(e)})

@room_bp.route('/api/delete-piece', methods=['POST'])
@login_required
def delete_piece_api():
    """删除棋子数据"""
    from models import Piece
    
    try:
        data = request.json
        piece_id = data.get('piece_id')
        
        if not piece_id:
            return jsonify({'success': False, 'msg': '缺少必要参数'})
        
        # 查找棋子
        piece = Piece.query.filter_by(piece_id=piece_id).first()
        if not piece:
            return jsonify({'success': False, 'msg': '棋子不存在'})
        
        # 不能删除枭棋子
        if piece_id == 'X':
            return jsonify({'success': False, 'msg': '不能删除枭棋子'})
        
        # 删除棋子
        db.session.delete(piece)
        db.session.commit()
        return jsonify({'success': True, 'msg': '棋子数据删除成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'msg': str(e)})

@room_bp.route('/api/load-map/<map_name>')
@login_required
def load_map_api(map_name):
    """加载指定的地图"""
    from map_loader import MapLoader
    
    try:
        map_data = MapLoader.load_map(map_name)
        return jsonify({'success': True, 'map_data': map_data})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})

@room_bp.route('/api/get-terrain-types')
@login_required
def get_terrain_types_api():
    """获取所有地形类型"""
    from models import Terrain
    
    try:
        terrains = Terrain.query.all()
        terrain_types = {}
        
        for terrain in terrains:
            terrain_types[terrain.terrain_id] = {
                'name': terrain.name,
                'description': terrain.description,
                'passability': terrain.passability,
                'move_cost': terrain.move_cost,
                'combat_bonus': terrain.combat_bonus,
                'color': terrain.color
            }
        
        return jsonify({'success': True, 'terrain_types': terrain_types})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})

@room_bp.route('/api/get-piece-types')
def get_piece_types_api():
    """获取所有棋子类型"""
    from models import Piece
    
    try:
        pieces = Piece.query.all()
        piece_types = {}
        
        for piece in pieces:
            piece_types[piece.piece_id] = {
                'name': piece.name,
                'description': piece.description,
                'move_range': piece.move_range,
                'combat_range': piece.combat_range,
                'base_power': piece.base_power,
                'attack_type': piece.attack_type,
                'move_cost': piece.move_cost,
                'defense_power': piece.defense_power,
                'attack_coop': piece.attack_coop,
                'defense_coop': piece.defense_coop,
                'coop_range': piece.coop_range,
                'piece_picture': piece.piece_picture,
                'terrain_change': piece.terrain_change
            }
        
        return jsonify({'success': True, 'piece_types': piece_types})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})

@room_bp.route('/api/room-stats/<int:room_id>')
@login_required
def get_room_stats_api(room_id):
    """获取游戏对局的统计信息，包括连续胜利和失败次数"""
    try:
        room = GameRoom.query.get(room_id)
        if not room:
            return jsonify({'success': False, 'msg': '房间不存在'})
        
        # 检查用户是否是房间的参与者
        if room.player1_id != current_user.id and room.player2_id != current_user.id:
            return jsonify({'success': False, 'msg': '你不是该房间的参与者'})
        
        stats = {
            'room_id': room.id,
            'player1_id': room.player1_id,
            'player2_id': room.player2_id,
            'player1_streak': room.player1_streak,
            'player2_streak': room.player2_streak,
            'status': room.status,
            'winner_id': room.winner_id
        }
        
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})

@room_bp.route('/api/user-rankings')
@login_required
def get_user_rankings_api():
    """获取用户排名数据"""
    try:
        # 查询所有用户，按游戏获胜数降序排列
        users = User.query.order_by(User.games_won.desc()).all()
        
        rankings = []
        for i, user in enumerate(users, 1):
            # 计算胜率
            win_rate = (user.games_won / user.games_played * 100) if user.games_played > 0 else 0
            
            rankings.append({
                'rank': i,
                'username': user.username,
                'games_played': user.games_played,
                'games_won': user.games_won,
                'win_rate': round(win_rate, 2)
            })
        
        return jsonify({'success': True, 'rankings': rankings})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})

@room_bp.route('/api/top-users')
@login_required
def get_top_users_api():
    """获取排名前三的用户"""
    try:
        # 查询排名前三的用户，按游戏获胜数降序排列
        users = User.query.order_by(User.games_won.desc()).limit(3).all()
        
        top_users = []
        for i, user in enumerate(users, 1):
            # 计算胜率
            win_rate = (user.games_won / user.games_played * 100) if user.games_played > 0 else 0
            
            top_users.append({
                'rank': i,
                'username': user.username,
                'games_played': user.games_played,
                'games_won': user.games_won,
                'win_rate': round(win_rate, 2)
            })
        
        return jsonify({'success': True, 'top_users': top_users})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})

@room_bp.route('/combat-logs/<int:room_id>')
@login_required
def combat_logs_view(room_id):
    """战斗记录页面，仅允许对局双方查看"""
    room = GameRoom.query.get_or_404(room_id)
    
    # 检查用户是否是房间的参与者
    if room.player1_id != current_user.id and room.player2_id != current_user.id:
        return redirect(url_for('room.index'))
    
    # 获取战斗记录
    combat_logs = CombatLog.query.filter_by(room_id=room_id).order_by(CombatLog.combat_sequence).all()
    
    # 获取双方玩家信息
    player1 = User.query.get(room.player1_id)
    player2 = User.query.get(room.player2_id)
    
    context = {
        'room': room,
        'combat_logs': combat_logs,
        'player1': player1,
        'player2': player2,
        'user': current_user
    }
    
    return render_template('combat_logs.html', **context)

@room_bp.route('/api/combat-logs/<int:room_id>')
@login_required
def get_combat_logs_api(room_id):
    """获取战斗记录数据，仅允许对局双方查看"""
    room = GameRoom.query.get(room_id)
    
    if not room:
        return jsonify({'success': False, 'msg': '房间不存在'})
    
    # 检查用户是否是房间的参与者
    if room.player1_id != current_user.id and room.player2_id != current_user.id:
        return jsonify({'success': False, 'msg': '你不是该房间的参与者'})
    
    # 获取战斗记录
    combat_logs = CombatLog.query.filter_by(room_id=room_id).order_by(CombatLog.turn_number, CombatLog.id).all()
    
    logs_data = []
    for log in combat_logs:
        logs_data.append({
            'id': log.id,
            'turn_number': log.turn_number,
            'attacker_id': log.attacker_id,
            'defender_id': log.defender_id,
            'attacker_sticks': log.get_attacker_sticks(),
            'defender_sticks': log.get_defender_sticks(),
            'attacker_binary': log.attacker_binary,
            'defender_binary': log.defender_binary,
            'attacker_power': log.attacker_power,
            'defender_power': log.defender_power,
            'winner': log.winner,
            'distance': log.distance,
            'created_at': log.created_at.isoformat()
        })
    
    return jsonify({'success': True, 'logs': logs_data})

@room_bp.route('/my-games')
@login_required
def my_games_view():
    """用户个人对局记录页面"""
    return render_template('my_games.html', user=current_user)

@room_bp.route('/api/my-games')
@login_required
def get_my_games_api():
    """获取当前用户参与的所有对局数据"""
    try:
        # 查询用户作为player1或player2参与的所有房间
        rooms = GameRoom.query.filter(
            (GameRoom.player1_id == current_user.id) | (GameRoom.player2_id == current_user.id)
        ).order_by(GameRoom.id.desc()).all()
        
        games_data = []
        for room in rooms:
            player1 = User.query.get(room.player1_id)
            player2 = User.query.get(room.player2_id) if room.player2_id else None
            
            # 确定当前用户在该房间中的角色和结果
            if room.player1_id == current_user.id:
                my_side = '红方'
                opponent = player2
            else:
                my_side = '黑方'
                opponent = player1
            
            # 确定对局结果
            if room.status == 'finished':
                if room.winner_id == current_user.id:
                    result = '胜利'
                elif room.winner_id is None:
                    result = '平局'
                else:
                    result = '失败'
            else:
                result = '进行中'
            
            games_data.append({
                'room_id': room.id,
                'status': room.status,
                'result': result,
                'my_side': my_side,
                'opponent': opponent.username if opponent else '等待加入',
                'opponent_id': opponent.id if opponent else None,
                'created_at': room.id  # 使用room_id作为创建时间的替代
            })
        
        return jsonify({'success': True, 'games': games_data})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})
