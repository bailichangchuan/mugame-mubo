from flask import Blueprint, render_template, redirect, url_for, jsonify, request
from flask_login import login_required, current_user
from flask_socketio import emit, join_room
from extensions import db, socketio
from config import Config  # 修改这一行
from models import GameRoom, User
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
    initial_board = []
    for _ in range(9): initial_board.append([None] * 9)
    # --- 红方 (R) --- 
    # 位于棋盘底部 (视觉上的 Row 0, 1 -> 数组索引 8, 7)
    
    # 第一排 (y=0 -> row=8): 散棋在 (1,0), (2,0), (6,0), (7,0)
    initial_board[8][1] = {'type': 'S', 'side': 'B'}
    initial_board[8][2] = {'type': 'S', 'side': 'B'}
    initial_board[8][6] = {'type': 'S', 'side': 'B'}
    initial_board[8][7] = {'type': 'S', 'side': 'B'}

    initial_board[8][3] = {'type': 'T', 'side': 'B'}
    initial_board[8][5] = {'type': 'T', 'side': 'B'}
    
    # 第一排中间 (y=0 -> row=8): 枭棋在 (4,0)
    initial_board[8][4] = {'type': 'X', 'side': 'B'}

    # 第二排 (y=1 -> row=7): 散棋在 (2,1) 到 (6,1)
    # 坐标: (2,1), (3,1), (4,1), (5,1), (6,1)
    for c in range(2, 7): # range(2, 7) 包含 2,3,4,5,6
        initial_board[7][c] = {'type': 'S', 'side': 'B'}


    # --- 黑方 (B) --- 
    # 位于棋盘顶部 (镜像对称 -> 数组索引 0, 1)
    
    # 第一排 (顶端 row=0) - 对应红方的 row=8
    initial_board[0][1] = {'type': 'S', 'side': 'R'}
    initial_board[0][2] = {'type': 'S', 'side': 'R'}
    initial_board[0][6] = {'type': 'S', 'side': 'R'}
    initial_board[0][7] = {'type': 'S', 'side': 'R'}

    initial_board[0][3] = {'type': 'T', 'side': 'R'}
    initial_board[0][5] = {'type': 'T', 'side': 'R'}
    
    # 枭棋
    initial_board[0][4] = {'type': 'X', 'side': 'R'}

    # 第二排 (row=1) - 对应红方的 row=7
    for c in range(2, 7):
        initial_board[1][c] = {'type': 'S', 'side': 'R'}

    # 【新增】初始化玩家卡牌库存
    # 结构: cards = { player_id: { 'card_1': 5, 'card_4': 2 ... } }
# 【修复】初始化卡牌
    initial_cards = {}
    
    # 1. 为创建者 (当前用户) 发放卡牌
    # 确保 CARD_CONFIG 在文件顶部已经引入或定义了
    initial_cards[str(current_user.id)] = {k: v['limit'] for k, v in CARD_CONFIG.items()}

    # ❌【删除或注释掉】下面这块报错的代码
    # 因为创建房间时只有你自己，还没有 player2，变量也没定义
    # for pid in [room_player1_id, room_player2_id]: 
    #     if pid:
    #         initial_cards[str(pid)] = ...

    game_state = {
        'board': initial_board,
        'turn': current_user.id,
        'steps_left': 0,
        'has_rolled': False,
        'winner': None,
        'cards': initial_cards,        # 此时里面只有 P1 的卡牌
        'active_card': None,           # 旧字段 (为了兼容性可留)
        'active_cards': {}             # 【建议】初始化新的多用户激活字典
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