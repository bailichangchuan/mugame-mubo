import random
from flask_login import current_user
from flask_socketio import emit
from extensions import db, socketio
from config import CARD_CONFIG
from models import GameRoom, User

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
    
    # 计算高度差
    height_diff = 0
    if 'terrain' in state and 'height' in state['terrain']:
        if 0 <= fr < len(state['terrain']['height']) and 0 <= fc < len(state['terrain']['height'][fr]):
            current_height = state['terrain']['height'][fr][fc]
        else:
            current_height = 0
        if 0 <= tr < len(state['terrain']['height']) and 0 <= tc < len(state['terrain']['height'][tr]):
            target_height = state['terrain']['height'][tr][tc]
        else:
            target_height = 0
        height_diff = current_height - target_height
    
    # 确定棋子类型（近战/远程）
    attacker_type = attacker.get('type', 'S')
    # 默认为近战
    attack_type = 'melee'
    
    # 检查是否为远程棋子
    if attacker_type in ['T', 'P']:
        attack_type = 'ranged'
    
    # 1. 近战攻击：只能攻击距离为1的目标
    if attack_type == 'melee':
        if dist == 1:
            valid_move = True
    # 2. 远程攻击：可以攻击更远的目标
    elif attack_type == 'ranged':
        # 计算基础攻击距离
        base_range = 3
        # 计算最大攻击距离
        max_range = base_range + height_diff
        max_range = max(1, max_range)  # 确保至少可以攻击1格
        
        # 检查攻击距离是否在范围内
        if 1 <= dist <= max_range:
            # 必须是直线 (同行或同列)
            if fr == tr or fc == tc:
                if not is_path_blocked(board, fr, fc, tr, tc):
                    valid_move = True
                else:
                    emit('error', {'msg': '路径上有阻挡，无法攻击'})
                    return
            else:
                emit('error', {'msg': '远程攻击只能直线攻击'})
                return
    
    if not valid_move:
        emit('error', {'msg': '移动不符合规则'})
        return
    # 在 handle_move 函数中修改
    # 情况 A: 移动到空地 (直接完成)
    if target is None:
        # 检查目标地形是否可站人
        if 'terrain' in state:
            # 检查是否有passability字段
            if 'passability' in state['terrain']:
                target_terrain = state['terrain']['passability'][tr][tc]
                if target_terrain == 0:
                    emit('error', {'msg': '该地形不可站立'})
                    return
            # 如果没有passability字段，根据地形类型判断
            elif 'type' in state['terrain'] and 'terrain_types' in state:
                target_terrain_type = state['terrain']['type'][tr][tc]
                if target_terrain_type in state['terrain_types']:
                    terrain_info = state['terrain_types'][target_terrain_type]
                    if terrain_info.get('passability', 1) == 0:
                        emit('error', {'msg': '该地形不可站立'})
                        return
        
        # 计算移动成本
        move_cost = 1
        
        # 地形移动成本
        if 'terrain_types' in state and 'terrain' in state:
            target_terrain_type = state['terrain']['type'][tr][tc]
            if target_terrain_type in state['terrain_types']:
                move_cost = state['terrain_types'][target_terrain_type]['move_cost']
        
        # 炮棋子移动消耗两倍
        if attacker['type'] == 'P':
            move_cost *= 2
        
        # 高度差判断和成本计算
        height_cost = 0
        if 'terrain' in state and 'height' in state['terrain']:
            current_height = state['terrain']['height'][fr][fc]
            target_height = state['terrain']['height'][tr][tc]
            height_diff = target_height - current_height  # 目标区块高度-当前区块高度
            
            # 检查高度差是否允许移动
            if abs(height_diff) > 1:
                emit('error', {'msg': '高度差过大，无法移动'})
                return
            
            # 计算高度移动成本
            height_cost = height_diff
        
        total_cost = move_cost + height_cost
        
        # 检查是否有足够的步数
        if state['steps_left'] < total_cost:
            emit('error', {'msg': f'步数不足，移动需要 {total_cost} 步'})
            return
        
        # 执行移动
        board[tr][tc] = attacker
        board[fr][fc] = None
        
        # 扣除步数并检查回合结束
        state['steps_left'] -= total_cost
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
    """处理决斗抽签请求"""
    # print(f"=== 接收到决斗抽签请求 ===")
    # print(f"请求数据: {data}")
    # print(f"当前用户: {current_user.id if current_user.is_authenticated else '未认证'}")
    
    # 1. 验证请求和获取数据
    validation_result = validate_combat_roll_request(data)
    if not validation_result['valid']:
        return emit('error', {'msg': validation_result['message']})
    
    room = validation_result['room']
    state = validation_result['state']
    combat = validation_result['combat']
    user_side = validation_result['user_side']
    role = validation_result['role']
    
    # 2. 生成随机数和应用卡牌效果
    combat_data = process_combat_roll(state, current_user.id, user_side, role, combat)
    
    # 3. 记录结果到状态
    update_combat_state(combat, role, combat_data)
    
    # 4. 保存状态并广播更新
    save_and_broadcast_state(room, state, combat_data)
    
    # 5. 检查是否需要结算
    if combat['attacker']['has_rolled'] and combat['defender']['has_rolled']:
        print(f"双方都已掷采，开始结算")
        resolve_combat(room, state)

def validate_combat_roll_request(data):
    """验证决斗抽签请求的有效性"""
    room_id = data.get('room_id')
    print(f"房间ID: {room_id}")
    
    room = GameRoom.query.get(room_id)
    if not room:
        print(f"错误: 房间 {room_id} 不存在")
        return {'valid': False, 'message': '房间不存在'}
    
    state = room.get_state()
    print(f"游戏状态: {state}")
    
    combat = state.get('pending_combat')
    if not combat or not combat['active']:
        print(f"错误: 没有激活的决斗状态")
        return {'valid': False, 'message': '当前没有激活的决斗'}
    
    # 判定身份
    user_side = 'R' if room.player1_id == current_user.id else 'B'
    role = None
    if user_side == combat['attacker']['side']:
        role = 'attacker'
    elif user_side == combat['defender']['side']:
        role = 'defender'
    else:
        print(f"错误: 用户 {current_user.id} 不是决斗参与者")
        return {'valid': False, 'message': '你不是当前决斗的参与者'}
    
    print(f"用户身份: {role} ({user_side})")
    
    if combat[role]['has_rolled']:
        print(f"错误: {role} 已经掷过采了")
        return {'valid': False, 'message': '你已经掷过采了'}
    
    return {
        'valid': True,
        'room': room,
        'state': state,
        'combat': combat,
        'user_side': user_side,
        'role': role
    }

def process_combat_roll(state, user_id, user_side, role, combat):
    """处理决斗抽签的核心逻辑：生成随机数和应用卡牌效果"""
    # 生成基础随机数
    sticks = generate_combat_sticks()
    print(f"生成的采: {sticks}")
    
    # 应用卡牌效果
    card_used = False
    card_type = None
    active_card_type = state.get('active_cards', {}).get(str(user_id))
    print(f"激活的卡牌: {active_card_type}")
    
    if active_card_type:
        card_used = apply_card_effect(state, user_id, active_card_type, sticks, user_side, combat)
        card_type = active_card_type
    
    # 计算数值
    binary_str = "".join(str(x) for x in sticks)
    val = int(binary_str, 2)
    print(f"计算的数值: {val} (二进制: {binary_str})")
    
    return {
        'sticks': sticks,
        'binary_str': binary_str,
        'val': val,
        'card_used': card_used,
        'card_type': card_type
    }

def generate_combat_sticks():
    """生成6个二进制数的随机序列"""
    return [random.randint(0, 1) for _ in range(6)]

def apply_card_effect(state, user_id, card_type, sticks, user_side, combat):
    """应用卡牌效果到随机数序列"""
    user_cards = state['cards'].get(str(user_id), {})
    
    if user_cards.get(card_type, 0) > 0:
        # 应用卡牌效果 (修改 sticks)
        if card_type == 'card_1':   # 第二位1
            sticks[1] = 1
        elif card_type == 'card_2': # 第一位1
            sticks[0] = 1
        elif card_type == 'card_3': # 前二位1
            sticks[0] = 1; sticks[1] = 1
        elif card_type == 'card_4': # 前三位1
            sticks[0] = 1; sticks[1] = 1; sticks[2] = 1
        
        # 扣除库存
        state['cards'][str(user_id)][card_type] -= 1
        
        # 消耗掉激活状态
        del state['active_cards'][str(user_id)]
        
        # 记录消息以便前端展示
        combat['msg'] = f"{'红方' if user_side=='R' else '黑方'} 使用了策略卡！"
        print(f"应用卡牌效果: {card_type}")
        return True
    return False

def update_combat_state(combat, role, combat_data):
    """更新战斗状态记录"""
    combat[role]['sticks'] = combat_data['sticks']
    combat[role]['binary_str'] = combat_data['binary_str']  # 新增：保存二进制字符串
    combat[role]['val'] = combat_data['val']
    combat[role]['has_rolled'] = True
    combat[role]['card_used'] = combat_data['card_used']  # 新增：记录是否使用了卡牌
    combat[role]['card_type'] = combat_data['card_type']  # 新增：记录使用的卡牌类型
    print(f"记录 {role} 的结果: {combat_data['sticks']}, {combat_data['val']}")

def save_and_broadcast_state(room, state, combat_data):
    """保存状态并广播更新"""
    room.set_state(state)
    db.session.commit()
    
    # 广播状态更新，包含详细的战斗数据
    emit('board_update', {
        'state': state,
        'combat_data': combat_data  # 新增：发送详细的战斗数据给前端
    }, room=str(room.id))
    # print(f"广播状态更新")

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

    # 计算高度差
    height_diff = 0
    if 'terrain' in state and 'height' in state['terrain']:
        if 0 <= fr < len(state['terrain']['height']) and 0 <= fc < len(state['terrain']['height'][fr]):
            current_height = state['terrain']['height'][fr][fc]
        else:
            current_height = 0
        if 0 <= tr < len(state['terrain']['height']) and 0 <= tc < len(state['terrain']['height'][tr]):
            target_height = state['terrain']['height'][tr][tc]
        else:
            target_height = 0
        height_diff = current_height - target_height
    
    # --- 1. 调用计算器 (替代了原有的一大坨代码) ---
    atk_power = CombatCalculator.calculate_power(
        piece=attacker_piece, 
        base_val=atk_info['val'], 
        distance=dist, 
        role='attacker', 
        enemy_piece=target_piece,
        position=(fc, fr),
        terrain_types=state.get('terrain_types'),
        terrain=state.get('terrain'),
        height_diff=height_diff
    )
    
    def_power = CombatCalculator.calculate_power(
        piece=target_piece, 
        base_val=def_info['val'], 
        distance=dist, 
        role='defender', 
        enemy_piece=attacker_piece,
        position=(tc, tr),
        terrain_types=state.get('terrain_types'),
        terrain=state.get('terrain'),
        height_diff=-height_diff  # 防守方的高度差是相反的
    )

    # 在 resolve_combat 函数中修改 combat_log 的创建
    combat_log = {
        'attacker': {
            'val': atk_info['val'], 
            'final_power': atk_power, 
            'side': atk_info['side'],
            'binary_str': atk_info.get('binary_str'),  # 新增：二进制原始值
            'card_used': atk_info.get('card_used', False),  # 新增：是否使用了卡牌
            'card_type': atk_info.get('card_type')  # 新增：使用的卡牌类型
        },
        'defender': {
            'val': def_info['val'], 
            'final_power': def_power, 
            'side': def_info['side'],
            'binary_str': def_info.get('binary_str'),  # 新增：二进制原始值
            'card_used': def_info.get('card_used', False),  # 新增：是否使用了卡牌
            'card_type': def_info.get('card_type')  # 新增：使用的卡牌类型
        },
        'distance': dist,
        'winner': None,
        'msg': ''
    }

    # --- 2. 判定胜负 (保持原有逻辑) ---
    
    # 特殊规则：矢的远程狙击 (距离3)
    if attacker_piece['type'] == 'T' and dist == 3:
        if atk_power >= 20:
            combat_log['winner'] = 'attacker'
            combat_log['msg'] = f"远程狙击成功！战力 {atk_power} >= 20"
            
            # 只有狙击成功才吃子
            if target_piece['type'] == 'X':
                state['winner'] = atk_info['side']
                room.status = 'finished'
                
                # 【新增】更新胜利者的获胜数和连续胜利次数
                if atk_info['side'] == 'R':
                    winner_user = User.query.get(room.player1_id)
                    # 更新红方连续胜利次数
                    room.player1_streak += 1
                    room.player2_streak = 0
                else:
                    winner_user = User.query.get(room.player2_id)
                    # 更新黑方连续胜利次数
                    room.player2_streak += 1
                    room.player1_streak = 0
                if winner_user:
                    winner_user.games_won += 1
                
                # 【新增】更新胜利者的获胜数和连续胜利次数
                if atk_info['side'] == 'R':
                    winner_user = User.query.get(room.player1_id)
                    # 更新红方连续胜利次数
                    room.player1_streak += 1
                    room.player2_streak = 0
                else:
                    winner_user = User.query.get(room.player2_id)
                    # 更新黑方连续胜利次数
                    room.player2_streak += 1
                    room.player1_streak = 0
                if winner_user:
                    winner_user.games_won += 1
            
            # 远程击杀后，攻击者跳跃过去
            board[tr][tc] = attacker_piece
            board[fr][fc] = None
            
            # 炮攻击时降低地形高度
            if attacker_piece['type'] == 'P' and 'terrain' in state and 'height' in state['terrain']:
                if 0 <= tr < len(state['terrain']['height']) and 0 <= tc < len(state['terrain']['height'][tr]):
                    current_height = state['terrain']['height'][tr][tc]
                    new_height = max(-1, current_height - 1)
                    state['terrain']['height'][tr][tc] = new_height
                    combat_log['msg'] += f"，地形高度降低至 {new_height}"
            
            # 炮攻击时降低地形高度
            if attacker_piece['type'] == 'P' and 'terrain' in state and 'height' in state['terrain']:
                if 0 <= tr < len(state['terrain']['height']) and 0 <= tc < len(state['terrain']['height'][tr]):
                    current_height = state['terrain']['height'][tr][tc]
                    new_height = max(-1, current_height - 1)
                    state['terrain']['height'][tr][tc] = new_height
                    combat_log['msg'] += f"，地形高度降低至 {new_height}"
            
            # 炮攻击时降低地形高度
            if attacker_piece['type'] == 'P' and 'terrain' in state and 'height' in state['terrain']:
                if 0 <= tr < len(state['terrain']['height']) and 0 <= tc < len(state['terrain']['height'][tr]):
                    current_height = state['terrain']['height'][tr][tc]
                    new_height = max(-1, current_height - 1)
                    state['terrain']['height'][tr][tc] = new_height
                    combat_log['msg'] += f"，地形高度降低至 {new_height}"
        else:
            combat_log['winner'] = 'draw'
            combat_log['msg'] = f"远程被格挡 ({atk_power} < 20)"
            # 棋盘不动
    else:
        # 标准对决
        if atk_power > def_power:
            combat_log['winner'] = 'attacker'
            combat_log['msg'] = f"进攻胜利 ({atk_power} vs {def_power})"
            
            if target_piece['type'] == 'X':
                state['winner'] = atk_info['side']
                room.status = 'finished'
                
                # 【新增】更新胜利者的获胜数和连续胜利次数
                if atk_info['side'] == 'R':
                    winner_user = User.query.get(room.player1_id)
                    # 更新红方连续胜利次数
                    room.player1_streak += 1
                    room.player2_streak = 0
                else:
                    winner_user = User.query.get(room.player2_id)
                    # 更新黑方连续胜利次数
                    room.player2_streak += 1
                    room.player1_streak = 0
                if winner_user:
                    winner_user.games_won += 1
            
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
                
                # 【新增】更新胜利者的获胜数和连续胜利次数
                if def_info['side'] == 'R':
                    winner_user = User.query.get(room.player1_id)
                    # 更新红方连续胜利次数
                    room.player1_streak += 1
                    room.player2_streak = 0
                else:
                    winner_user = User.query.get(room.player2_id)
                    # 更新黑方连续胜利次数
                    room.player2_streak += 1
                    room.player1_streak = 0
                if winner_user:
                    winner_user.games_won += 1

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
    def calculate_power(piece, base_val, distance, role, enemy_piece, position=None, terrain_types=None, terrain=None, height_diff=0):
        """
        计算棋子的最终战力
        :param piece: 己方棋子对象
        :param base_val: 掷采出的基础数值
        :param distance: 战斗距离
        :param role: 'attacker' 或 'defender'
        :param enemy_piece: 对手棋子对象 (用于判断是否有针对性克制)
        :param position: 棋子位置 (x, y)
        :param terrain_types: 地形类型数据
        :param terrain: 地形数据
        :param height_diff: 高度差 (当前格子高度 - 目标格子高度)
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
            multiplier *= CombatCalculator._calc_arrow_bonus(distance, role, height_diff)
        elif p_type == 'S':
            multiplier *= CombatCalculator._calc_soldier_bonus(distance)
        elif p_type == 'P':
            multiplier *= CombatCalculator._calc_cannon_bonus(distance, role, height_diff)
        
        # --- 4. 地形战斗加成 ---
        if position and terrain_types and terrain:
            x, y = position
            if 0 <= y < len(terrain['type']) and 0 <= x < len(terrain['type'][y]):
                terrain_type = terrain['type'][y][x]
                if terrain_type in terrain_types:
                    multiplier *= terrain_types[terrain_type].get('combat_bonus', 1.0)
            
        # 计算结果
        return round(base_val * multiplier, 1)

    @staticmethod
    def _calc_arrow_bonus(distance, role, height_diff=0):
        """处理 '矢' 的距离逻辑"""
        # 计算最佳攻击距离区间
        base_optimal = 2
        optimal_range = base_optimal + max(0, height_diff)
        
        # 确定当前距离对应的倍率
        if distance == base_optimal:
            # 最佳距离
            return 1.1 if role == 'attacker' else 0.9
        elif distance < base_optimal:
            # 距离小于最佳距离，减0.2
            return (1.1 if role == 'attacker' else 0.9) - 0.2
        elif distance == optimal_range:
            # 地形优势的最佳距离
            return 1.1 if role == 'attacker' else 0.9
        elif distance > optimal_range:
            # 距离大于最佳距离，减0.5
            return (1.1 if role == 'attacker' else 0.9) - 0.5
        elif distance > base_optimal and distance < optimal_range:
            # 在基础最佳距离和地形优势最佳距离之间
            return 1.1 if role == 'attacker' else 0.9
        return 1.0

    @staticmethod
    def _calc_soldier_bonus(distance):
        """处理 '散' 的逻辑 (目前标准是1.0，方便以后扩展)"""
        return 1.0
    
    @staticmethod
    def _calc_cannon_bonus(distance, role, height_diff=0):
        """处理 '炮' 的逻辑"""
        # 计算最佳攻击距离区间
        base_optimal = 2
        optimal_range = base_optimal + max(0, height_diff)
        
        # 确定当前距离对应的倍率
        if distance == base_optimal:
            # 最佳距离
            return 1.5
        elif distance < base_optimal:
            # 距离小于最佳距离，减0.2
            return 1.5 - 0.2
        elif distance == optimal_range:
            # 地形优势的最佳距离
            return 1.5
        elif distance > optimal_range:
            # 距离大于最佳距离，减0.5
            return 1.5 - 0.5
        elif distance > base_optimal and distance < optimal_range:
            # 在基础最佳距离和地形优势最佳距离之间
            return 1.5
        return 1.0


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

@socketio.on('adjust_terrain_height')
def handle_adjust_terrain(data):
    """处理地形高度调整请求"""
    room_id = data.get('room_id')
    r = data.get('r')
    c = data.get('c')
    delta = data.get('delta', 0)
    
    room = GameRoom.query.get(room_id)
    if not room or room.status != 'playing':
        return emit('error', {'msg': '房间不存在或游戏已结束'})
    
    state = room.get_state()
    
    # 检查是否是当前用户的回合
    if state['turn'] != current_user.id:
        return emit('error', {'msg': '不是你的回合'})
    
    # 检查是否有足够的步数
    if state.get('steps_left', 0) < 1:
        return emit('error', {'msg': '步数不足'})
    
    # 检查是否在决斗中
    if state.get('pending_combat') and state['pending_combat']['active']:
        return emit('error', {'msg': '正在决斗阶段，无法调整地形'})
    
    # 确保地形数据存在
    if 'terrain' not in state:
        state['terrain'] = {'height': [], 'type': []}
    
    if 'height' not in state['terrain']:
        # 初始化高度数据
        board = state.get('board', [])
        if board:
            height = len(board)
            width = len(board[0]) if height > 0 else 0
            state['terrain']['height'] = [[0 for _ in range(width)] for _ in range(height)]
        else:
            return emit('error', {'msg': '棋盘数据不存在'})
    
    # 调整高度
    height_map = state['terrain']['height']
    if 0 <= r < len(height_map) and 0 <= c < len(height_map[r]):
        new_height = height_map[r][c] + delta
        # 限制高度范围
        new_height = max(-1, min(4, new_height))
        height_map[r][c] = new_height
        
        # 移除工棋子（工棋子消失）
        if state.get('board') and 0 <= r < len(state['board']) and 0 <= c < len(state['board'][r]):
            piece = state['board'][r][c]
            if piece and piece['type'] == 'G':
                state['board'][r][c] = None
        
        # 扣除步数
        state['steps_left'] -= 1
        
        # 检查回合是否结束
        turn_ended = check_turn_end(room, state)
        
        # 保存状态并广播更新
        room.set_state(state)
        db.session.commit()
        emit('board_update', {'state': state, 'turn_ended': turn_ended}, room=str(room.id))
    else:
        emit('error', {'msg': '位置无效'})