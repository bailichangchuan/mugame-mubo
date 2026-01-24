import random
from flask_login import current_user
from flask_socketio import emit
from extensions import db, socketio
from config import CARD_CONFIG
from models import GameRoom

# --- 辅助函数: 掷采算法 ---
def generate_sticks():
    """
    生成6个二进制数 (0或1)
    返回:
    1. sticks: 列表，如 [0, 1, 1, 0, 1, 0]
    2. move_val: 移动步数 (Sum)，如 3
    3. combat_val: 战斗数值 (Decimal)，如 26 (011010)
    """
    sticks = [random.randint(0, 1) for _ in range(6)]
    move_val = sum(sticks)
    
    # 二进制转十进制
    binary_str = "".join(str(x) for x in sticks)
    combat_val = int(binary_str, 2)
    
    return sticks, move_val, combat_val

# --- SocketIO 事件 ---

@socketio.on('roll_for_turn')
def handle_roll(data):
    """玩家回合开始时，掷采决定步数"""
    room_id = data.get('room_id')
    room = GameRoom.query.get(room_id)
    state = room.get_state()
    
    if state['turn'] != current_user.id:
        emit('error', {'msg': '不是你的回合'})
        return
        
    # 检查是否已经掷过骰子 (需要在state里记录 has_rolled)
    if state.get('has_rolled', False):
        emit('error', {'msg': '本回合已经掷过采了'})
        return

    # 生成移动步数
    sticks, move_steps, _ = generate_sticks()
    
    # 规则修正：虽然是1-6随机，但二进制相加可能为0。
    # 这里我们保留0的可能性（也就是这回合动不了，运气极差），或者你也可以强制设为1。
    # 既然你说 "1-6"，那如果随到0，我们可以给个保底1，或者严格按规则。
    # 这里按严格规则：随到0就是0步，直接结束回合。
    if move_steps == 0:
        emit('roll_result', {
          'sticks': sticks,
          'steps': 0,
          'msg': "掷出 0，得 0 步，直接结束回合"
        }, room=str(room.id))
        state['steps_left'] = 0
        state['has_rolled'] = True
        room.set_state(state)

    state['steps_left'] = move_steps
    state['has_rolled'] = True
    
    # 如果步数为0，自动结束回合吗？为了体验，让玩家自己点结束，或者看一眼0步再结束。
    
    room.set_state(state)
    db.session.commit()
    
    emit('roll_result', {
        'sticks': sticks,
        'steps': move_steps,
        'msg': f"掷出 {sticks}，得 {move_steps} 步"
    }, room=str(room.id))
    
    # 同步步数显示
    emit('board_update', {'state': state}, room=str(room.id))


@socketio.on('move_piece')
def handle_move(data):
    room_id = data.get('room_id')
    room = GameRoom.query.get(room_id)
    if not room or room.status != 'playing': return

    state = room.get_state()
    current_player_id = current_user.id
    
    # --- 1. 基础校验 (保持不变) ---
    if state['turn'] != current_player_id:
        emit('error', {'msg': '不是你的回合'})
        return
    if not state.get('has_rolled', False):
        emit('error', {'msg': '请先掷采决定步数'})
        return
    if state['steps_left'] <= 0:
        emit('error', {'msg': '没有剩余步数了'})
        return
    # 如果当前正在决斗中，禁止移动其他棋子
    if state.get('pending_combat') and state['pending_combat']['active']:
        emit('error', {'msg': '决斗进行中，无法移动'})
        return

    fr, fc = data['from_r'], data['from_c']
    tr, tc = data['to_r'], data['to_c']
    board = state['board']
    attacker = board[fr][fc]
    target = board[tr][tc]

    side = 'R' if room.player1_id == current_player_id else 'B'
    if not attacker or attacker['side'] != side: return
    # if abs(fr - tr) + abs(fc - tc) != 1:
    #     emit('error', {'msg': '只能移动一格'})
    #     return

    # --- 2. 逻辑分岔点 ---

    # 计算曼哈顿距离
    dist = abs(fr - tr) + abs(fc - tc)
    
    valid_move = False
    
    # 1. 普通移动/攻击：距离为1
    if dist == 1:
        valid_move = True
        
    # 2. “矢”的特殊远程攻击
    # 条件：是'T'棋 + 目标是敌人 + 距离在2到3之间 + 直线 + 中间无阻挡
    elif (attacker['type'] == 'T' and target is not None and target['side'] != side):
        if 2 <= dist <= 3:
            # 必须是直线 (同行或同列)
            if fr == tr or fc == tc:
                if not is_path_blocked(board, fr, fc, tr, tc):
                    valid_move = True
                else:
                    emit('error', {'msg': '路径上有阻挡，无法攻击'})
                    return
            else:
                emit('error', {'msg': '矢只能直线攻击'})
                return
    
    if not valid_move:
        emit('error', {'msg': '移动不符合规则'})
        return
    
    # 情况 A: 移动到空地 (直接完成)
    if target is None:
        board[tr][tc] = attacker
        board[fr][fc] = None
        
        # 扣除步数并检查回合结束
        state['steps_left'] -= 1
        turn_ended = check_turn_end(room, state) # 调用辅助函数
        
        room.set_state(state)
        db.session.commit()
        emit('board_update', {'state': state, 'turn_ended': turn_ended}, room=str(room.id))

    # 情况 B: 移动到己方 (报错)
    elif target['side'] == side:
        emit('error', {'msg': '不能吃己方棋子'})
        return

    # 情况 C: 遭遇战 (修改为：开启决斗状态，暂停结算)
    else:
        # 初始化决斗数据，不进行计算，不扣步数
        state['pending_combat'] = {
            'active': True,
            'attacker': {
                'pos': [fr, fc], 
                'side': side, 
                'sticks': None, 
                'val': None, 
                'has_rolled': False
            },
            'defender': {
                'pos': [tr, tc], 
                'side': target['side'], 
                'sticks': None, 
                'val': None, 
                'has_rolled': False
            }
        }
        # 此时需要把 distance 传给战斗状态，以便结算时使用
        # 我们把距离存入 pending_combat 中
        
        if target is not None and target['side'] != side:
            state['pending_combat'] = {
                'active': True,
                'distance': dist, # 【新增】记录攻击距离
                'attacker': {'pos': [fr, fc], 'side': side, 'sticks': None, 'val': None, 'has_rolled': False},
                'defender': {'pos': [tr, tc], 'side': target['side'], 'sticks': None, 'val': None, 'has_rolled': False}
            }
        
        room.set_state(state)
        db.session.commit()
        # 广播状态，前端此时会弹出“决斗面板”
        emit('board_update', {'state': state}, room=str(room.id))

# routes/room.py (新增函数)

# game.py -> handle_combat_roll

@socketio.on('combat_roll')
def handle_combat_roll(data):
    print(f"=== 接收到决斗抽签请求 ===")
    print(f"请求数据: {data}")
    print(f"当前用户: {current_user.id if current_user.is_authenticated else '未认证'}")
    
    room_id = data.get('room_id')
    print(f"房间ID: {room_id}")
    
    room = GameRoom.query.get(room_id)
    if not room:
        print(f"错误: 房间 {room_id} 不存在")
        emit('error', {'msg': '房间不存在'})
        return
    
    state = room.get_state()
    print(f"游戏状态: {state}")
    
    combat = state.get('pending_combat')
    if not combat or not combat['active']:
        print(f"错误: 没有激活的决斗状态")
        emit('error', {'msg': '当前没有激活的决斗'})
        return

    # 1. 判定身份
    user_side = 'R' if room.player1_id == current_user.id else 'B'
    role = None
    if user_side == combat['attacker']['side']:
        role = 'attacker'
    elif user_side == combat['defender']['side']:
        role = 'defender'
    else:
        print(f"错误: 用户 {current_user.id} 不是决斗参与者")
        emit('error', {'msg': '你不是当前决斗的参与者'})
        return

    print(f"用户身份: {role} ({user_side})")
    
    if combat[role]['has_rolled']:
        print(f"错误: {role} 已经掷过采了")
        emit('error', {'msg': '你已经掷过采了'})
        return

    # --- 2. 生成基础随机数 ---
    sticks = [random.randint(0, 1) for _ in range(6)]
    print(f"生成的采: {sticks}")
    
    # --- 3. 【核心修改】应用卡牌逻辑 ---
    active_card_type = state.get('active_cards', {}).get(str(current_user.id))
    print(f"激活的卡牌: {active_card_type}")
    
    if active_card_type:
        user_cards = state['cards'].get(str(current_user.id), {})
        
        if user_cards.get(active_card_type, 0) > 0:
            # 应用卡牌效果 (修改 sticks)
            if active_card_type == 'card_1':   # 第二位1
                sticks[1] = 1
            elif active_card_type == 'card_2': # 第一位1
                sticks[0] = 1
            elif active_card_type == 'card_3': # 前二位1
                sticks[0] = 1; sticks[1] = 1
            elif active_card_type == 'card_4': # 前三位1
                sticks[0] = 1; sticks[1] = 1; sticks[2] = 1
            
            # 扣除库存
            state['cards'][str(current_user.id)][active_card_type] -= 1
            
            # 消耗掉激活状态
            del state['active_cards'][str(current_user.id)]
            
            # 记录消息以便前端展示
            combat['msg'] = f"{'红方' if user_side=='R' else '黑方'} 使用了策略卡！"
            print(f"应用卡牌效果: {active_card_type}")

    # 计算数值
    binary_str = "".join(str(x) for x in sticks)
    val = int(binary_str, 2)
    print(f"计算的数值: {val} (二进制: {binary_str})")

    # 4. 记录结果
    combat[role]['sticks'] = sticks
    combat[role]['val'] = val
    combat[role]['has_rolled'] = True
    print(f"记录 {role} 的结果: {sticks}, {val}")
    
    room.set_state(state)
    db.session.commit()
    emit('board_update', {'state': state}, room=str(room.id))
    print(f"广播状态更新")

    # 5. 双方都掷采完毕，进入结算
    if combat['attacker']['has_rolled'] and combat['defender']['has_rolled']:
        print(f"双方都已掷采，开始结算")
        resolve_combat(room, state)

# game.py -> resolve_combat

def resolve_combat(room, state):
    combat = state['pending_combat']
    board = state['board']
    
    atk_info = combat['attacker']
    def_info = combat['defender']
    dist = combat.get('distance', 1)
    
    # 获取棋子对象
    fr, fc = atk_info['pos']
    tr, tc = def_info['pos']
    attacker_piece = board[fr][fc]
    target_piece = board[tr][tc]

    # --- 1. 调用计算器 (替代了原有的一大坨代码) ---
    atk_power = CombatCalculator.calculate_power(
        piece=attacker_piece, 
        base_val=atk_info['val'], 
        distance=dist, 
        role='attacker', 
        enemy_piece=target_piece
    )
    
    def_power = CombatCalculator.calculate_power(
        piece=target_piece, 
        base_val=def_info['val'], 
        distance=dist, 
        role='defender', 
        enemy_piece=attacker_piece
    )

    combat_log = {
        'attacker': {'val': atk_info['val'], 'final_power': atk_power, 'side': atk_info['side']},
        'defender': {'val': def_info['val'], 'final_power': def_power, 'side': def_info['side']},
        'distance': dist,
        'winner': None,
        'msg': ''
    }

    # --- 2. 判定胜负 (保持原有逻辑) ---
    
    # 特殊规则：矢的远程狙击 (距离3)
    if attacker_piece['type'] == 'T' and dist == 3:
        if atk_power >= 32:
            combat_log['winner'] = 'attacker'
            combat_log['msg'] = f"远程狙击成功！战力 {atk_power} >= 32"
            
            # 只有狙击成功才吃子
            if target_piece['type'] == 'X':
                state['winner'] = atk_info['side']
                room.status = 'finished'
            
            # 远程击杀后，攻击者跳跃过去
            board[tr][tc] = attacker_piece
            board[fr][fc] = None
        else:
            combat_log['winner'] = 'draw'
            combat_log['msg'] = f"远程被格挡 ({atk_power} < 32)"
            # 棋盘不动
    else:
        # 标准对决
        if atk_power > def_power:
            combat_log['winner'] = 'attacker'
            combat_log['msg'] = f"进攻胜利 ({atk_power} vs {def_power})"
            
            if target_piece['type'] == 'X':
                state['winner'] = atk_info['side']
                room.status = 'finished'
            
            board[tr][tc] = attacker_piece
            board[fr][fc] = None
        else:
            combat_log['winner'] = 'defender'
            combat_log['msg'] = f"防守反杀 ({def_power} >= {atk_power})"
            
            # 进攻方死亡
            board[fr][fc] = None
            # 检查枭是否死亡 (防止反杀枭导致游戏未结束的Bug)
            if attacker_piece['type'] == 'X':
                state['winner'] = def_info['side']
                room.status = 'finished'

    # --- 3. 结算收尾 ---
    state['steps_left'] -= 1
    state['pending_combat'] = None
    
    # 全局检查 (保险起见)
    # check_global_winner(room, state) 

    turn_ended = check_turn_end(room, state)
    room.set_state(state)
    db.session.commit()
    
    emit('board_update', {
        'state': state, 
        'combat': combat_log, 
        'turn_ended': turn_ended
    }, room=str(room.id))

# 计算函数拆分

class CombatCalculator:
    """专门负责计算战斗数值的策略类"""

    @staticmethod
    def calculate_power(piece, base_val, distance, role, enemy_piece):
        """
        计算棋子的最终战力
        :param piece: 己方棋子对象
        :param base_val: 掷采出的基础数值
        :param distance: 战斗距离
        :param role: 'attacker' 或 'defender'
        :param enemy_piece: 对手棋子对象 (用于判断是否有针对性克制)
        :return: final_power (float)
        """
        p_type = piece['type']
        multiplier = 1.0

        # --- 1. 通用规则 (如：枭的全局加成) ---
        if p_type == 'X':
            multiplier *= 1.3
        
        # --- 2. 基于角色的特殊逻辑 ---
        if role == 'defender':
            # 如果防守方是普通兵，且面对枭... (示例扩展)
            pass 

        # --- 3. 兵种特有逻辑 (分发到具体方法) ---
        if p_type == 'T':
            multiplier *= CombatCalculator._calc_arrow_bonus(distance, role)
        elif p_type == 'S':
            multiplier *= CombatCalculator._calc_soldier_bonus(distance)
            
        # 计算结果
        return round(base_val * multiplier, 1)

    @staticmethod
    def _calc_arrow_bonus(distance, role):
        """处理 '矢' 的距离逻辑"""
        if distance == 1:
            return 0.8
        elif distance == 2:
            # 进攻方1.1倍，防守方0.9倍 (根据你之前的逻辑)
            return 1.1 if role == 'attacker' else 0.9
        elif distance == 3:
            return 0.6
        return 1.0

    @staticmethod
    def _calc_soldier_bonus(distance):
        """处理 '散' 的逻辑 (目前标准是1.0，方便以后扩展)"""
        return 1.0

# def resolve_combat(room, state):
#     combat = state['pending_combat']
#     board = state['board']
    
#     atk_info = combat['attacker']
#     def_info = combat['defender']
    
#     # 获取坐标和棋子对象
#     fr, fc = atk_info['pos']
#     tr, tc = def_info['pos']
#     attacker_piece = board[fr][fc]
#     target_piece = board[tr][tc] # 防守方的棋子

#     # --- 1. 计算战斗力 (核心修改) ---
    
#     # 获取基础投掷点数
#     atk_base = atk_info['val']
#     def_base = def_info['val']
    
#     # 初始倍率均为 1.0
#     atk_multiplier = 1.0
#     def_multiplier = 1.0
    
#     # 枭棋判定：如果是 'X' (枭)，倍率为 1.3
#     if attacker_piece['type'] == 'X':
#         atk_multiplier = 1.3
    
#     if target_piece['type'] == 'X':
#         def_multiplier = 1.3
        
#     # 计算最终战力 (保留一位小数，防止浮点精度问题)
#     atk_power = round(atk_base * atk_multiplier, 1)
#     def_power = round(def_base * def_multiplier, 1)

#     # --- 2. 准备返回给前端的日志 ---
#     combat_log = {
#         'attacker': {
#             'val': atk_base, 
#             'multiplier': atk_multiplier, 
#             'final_power': atk_power,
#             'side': atk_info['side'],
#             'is_xiao': attacker_piece['type'] == 'X'
#         },
#         'defender': {
#             'val': def_base, 
#             'multiplier': def_multiplier, 
#             'final_power': def_power,
#             'side': def_info['side'],
#             'is_xiao': target_piece['type'] == 'X'
#         },
#         'winner': None,
#         'msg': ''
#     }

#     # --- 3. 比大小 (使用计算后的 Power) ---
#     if atk_power > def_power:
#         # 进攻方胜利
#         combat_log['winner'] = 'attacker'
#         combat_log['msg'] = f"进攻成功！(枭加成)" if atk_multiplier > 1 else "进攻成功！"
        
#         # 判定是否吃掉主帅 (游戏结束)
#         if target_piece['type'] == 'X':
#             state['winner'] = atk_info['side']
#             room.status = 'finished'
            
#         # 移动棋子
#         board[tr][tc] = attacker_piece
#         board[fr][fc] = None
        
#     else:
#         # 防守方胜利 (反杀)
#         combat_log['winner'] = 'defender'
#         combat_log['msg'] = f"遭遇反杀！(枭加成)" if def_multiplier > 1 else "遭遇反杀！"
        
#         # 移除进攻方
#         board[fr][fc] = None
#         # 防守方不动

#     # --- 4. 结算收尾 (不变) ---
#     state['steps_left'] -= 1
#     state['pending_combat'] = None
#     turn_ended = check_turn_end(room, state)

#     room.set_state(state)
#     db.session.commit()
    
#     emit('board_update', {
#         'state': state, 
#         'combat': combat_log, 
#         'turn_ended': turn_ended
#     }, room=str(room.id))

# 辅助函数：更新回合逻辑（用于 handle_move 普通移动）
def update_turn_logic(room, state):
    if state['steps_left'] <= 0:
        next_id = room.player2_id if state['turn'] == room.player1_id else room.player1_id
        state['turn'] = next_id
        state['has_rolled'] = False
        state['steps_left'] = 0
    room.set_state(state)
    db.session.commit()
    emit('board_update', {'state': state}, room=str(room.id))

@socketio.on('end_turn_manually')
def handle_end_turn(data):
    room_id = data.get('room_id')
    room = GameRoom.query.get(room_id)
    state = room.get_state()
    
    if state['turn'] == current_user.id:
        next_player = room.player2_id if state['turn'] == room.player1_id else room.player1_id
        state['turn'] = next_player
        state['has_rolled'] = False
        state['steps_left'] = 0
        room.set_state(state)
        db.session.commit()
        emit('board_update', {'state': state}, room=str(room.id))

# --- 在 game.py 底部补充这个函数 ---

def check_turn_end(room, state):
    """
    检查回合是否结束
    返回: True(结束) / False(未结束)
    """
    if state['steps_left'] <= 0:
        # 切换到下一个玩家
        next_player = room.player2_id if state['turn'] == room.player1_id else room.player1_id
        state['turn'] = next_player
        
        # 重置掷采状态
        state['has_rolled'] = False
        state['steps_left'] = 0 
        return True
    return False

def is_path_blocked(board, fr, fc, tr, tc):
    """
    检查从 (fr, fc) 到 (tr, tc) 之间是否有棋子阻挡 (不包含起点和终点)
    仅支持直线 (同行或同列)
    """
    if fr == tr: # 同一行
        step = 1 if tc > fc else -1
        for c in range(fc + step, tc, step):
            if board[fr][c] is not None:
                return True # 有阻挡
    elif fc == tc: # 同一列
        step = 1 if tr > fr else -1
        for r in range(fr + step, tr, step):
            if board[r][fc] is not None:
                return True # 有阻挡
    else:
        return True # 不是直线，视为阻挡（不允许斜向远程攻击）
        
    return False # 没有阻挡

@socketio.on('select_card')
def handle_select_card(data):
    room_id = data.get('room_id')
    card_type = data.get('card_type')
    
    room = GameRoom.query.get(room_id)
    state = room.get_state()
    user_key = str(current_user.id)
    
    # --- 【新增】核心校验逻辑 ---
    
    # 1. 检查是否有正在进行的战斗
    combat = state.get('pending_combat')
    if not combat or not combat.get('active'):
        return emit('error', {'msg': '卡牌仅能在战斗决斗阶段使用'})

    # 2. 确认当前用户在战斗中的身份 (进攻方 or 防守方)
    user_side = 'R' if room.player1_id == current_user.id else 'B'
    my_role = None
    
    if combat['attacker']['side'] == user_side:
        my_role = 'attacker'
    elif combat['defender']['side'] == user_side:
        my_role = 'defender'
    
    if not my_role:
        return emit('error', {'msg': '你没有参与当前的战斗'})

    # 3. 检查是否已经掷过采了 (掷过后不能再改)
    if combat[my_role]['has_rolled']:
        return emit('error', {'msg': '你已经完成掷采，无法再使用卡牌'})

    # --- (校验通过) ---

    # 4. 校验库存
    user_cards = state['cards'].get(user_key, {})
    if user_cards.get(card_type, 0) <= 0:
        return emit('error', {'msg': '该卡牌已用完'})

    # 5. 切换选中状态
    if 'active_cards' not in state or not isinstance(state['active_cards'], dict):
        state['active_cards'] = {}
        
    current_selected = state['active_cards'].get(user_key)
    if current_selected == card_type:
        del state['active_cards'][user_key] # 取消
    else:
        state['active_cards'][user_key] = card_type # 选中

    room.set_state(state)
    db.session.commit()
    emit('board_update', {'state': state}, room=str(room.id))