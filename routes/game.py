import random
import json
from flask_login import current_user
from flask_socketio import emit
from extensions import db, socketio
from config import CARD_CONFIG
from models import GameRoom, User, CombatLog
from game_logic.ai_player import AIPlayer, create_ai_player
from game_logic.piece_manager import PieceManager

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
    if 'piece_types' in state and attacker_type in state['piece_types']:
        attack_type = state['piece_types'][attacker_type].get('attack_type', 'melee')
    else:
        # 后备逻辑：使用硬编码的棋子类型列表
        if attacker_type in ['T', 'P']:
            attack_type = 'ranged'
    
    # 检查是否是移动操作（目标为空）
    if target is None:
        # 移动操作：只限制必须直线移动，不限制距离
        if fr == tr or fc == tc:
            # 检查路径上是否有阻挡
            if not is_path_blocked(board, fr, fc, tr, tc):
                valid_move = True
            else:
                emit('error', {'msg': '路径上有阻挡，无法移动'})
                return
        else:
            emit('error', {'msg': '移动只能直线进行'})
            return
    else:
        # 攻击操作
        if attack_type == 'melee':
            if dist == 1:
                valid_move = True
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
                        # 检查远程攻击路径上的高度差
                        can_attack, error_msg = check_remote_attack_height(state, fr, fc, tr, tc)
                        if not can_attack:
                            emit('error', {'msg': error_msg})
                            return
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
        # 计算移动距离
        move_dist = abs(fr - tr) + abs(fc - tc)
        
        # 检查是否是炮棋子
        is_cannon = attacker['type'] == 'P'
        
        # 炮的特殊处理
        if is_cannon:
            # 检查是否是攻击操作或点击远处空地
            is_cannon_attack = data.get('attack', False) or move_dist > 1
            
            if is_cannon_attack:
                # 检查炮是否已经使用过攻击
                if state.get('has_used_cannon', {}).get(str(current_player_id)):
                    emit('error', {'msg': '炮一回合只能使用一次攻击'})
                    return
                
                # 检查攻击距离和路径
                dist = move_dist
                # 计算最大攻击距离
                max_range = 3
                if 'terrain' in state and 'height' in state['terrain']:
                    current_height = state['terrain']['height'][fr][fc]
                    target_height = state['terrain']['height'][tr][tc]
                    height_diff = current_height - target_height
                    max_range = 3 + height_diff
                    max_range = max(1, max_range)
                
                # 检查攻击距离是否在范围内
                if 1 <= dist <= max_range:
                    # 必须是直线 (同行或同列)
                    if fr == tr or fc == tc:
                        if not is_path_blocked(board, fr, fc, tr, tc):
                            # 检查远程攻击路径上的高度差
                            can_attack, error_msg = check_remote_attack_height(state, fr, fc, tr, tc)
                            if not can_attack:
                                emit('error', {'msg': error_msg})
                                return
                            # 炮攻击空地时，开启战斗状态
                            state['pending_combat'] = {
                                'active': True,
                                'distance': dist, # 记录攻击距离
                                'attacker': {'pos': [fr, fc], 'side': side, 'sticks': None, 'val': None, 'has_rolled': False},
                                'defender': {'pos': [tr, tc], 'side': 'none', 'sticks': None, 'val': None, 'has_rolled': True, 'is_terrain': True}
                            }
                            
                            room.set_state(state)
                            db.session.commit()
                            # 广播状态，前端此时会弹出“决斗面板”
                            emit('board_update', {'state': state}, room=str(room.id))
                        else:
                            emit('error', {'msg': '路径上有阻挡，无法攻击'})
                            return
                    else:
                        emit('error', {'msg': '远程攻击只能直线攻击'})
                        return
                else:
                    emit('error', {'msg': f'攻击距离超出范围 (1-{max_range})'})
                    return
            else:
                # 计算移动范围和成本
                # 获取棋子类型数据
                piece_type = attacker['type']
                piece_move_range = 1  # 默认移动范围
                piece_move_cost = 1  # 默认移动成本
                
                if 'piece_types' in state and piece_type in state['piece_types']:
                    piece_move_range = state['piece_types'][piece_type].get('move_range', 1)
                    piece_move_cost = state['piece_types'][piece_type].get('move_cost', 1)
                
                # 计算移动距离
                move_dist = abs(fr - tr) + abs(fc - tc)
                
                # 检查移动距离是否在棋子的移动范围内
                if move_dist > piece_move_range:
                    emit('error', {'msg': f'移动距离超出范围，最大移动距离为 {piece_move_range}'})
                    return
                
                # 检查路径上是否有阻挡
                if not is_path_blocked(board, fr, fc, tr, tc):
                    # 计算移动成本
                    total_cost = 0
                    
                    # 生成移动路径上的所有格子
                    path = []
                    if fr == tr:  # 同一行
                        step = 1 if tc > fc else -1
                        for c in range(fc + step, tc + step, step):
                            path.append((fr, c))
                    else:  # 同一列
                        step = 1 if tr > fr else -1
                        for r in range(fr + step, tr + step, step):
                            path.append((r, fc))
                    
                    # 计算每个格子的移动成本并检查高度差
                    if 'terrain' in state and 'height' in state['terrain']:
                        # 检查起点和路径上第一个格子的高度差
                        current_height = state['terrain']['height'][fr][fc]
                        
                        for i, (r, c) in enumerate(path):
                            # 检查地形移动成本
                            terrain_move_cost = 1
                            if 'terrain_types' in state and 'terrain' in state:
                                terrain_type = state['terrain']['type'][r][c]
                                if terrain_type in state['terrain_types']:
                                    terrain_move_cost = state['terrain_types'][terrain_type].get('move_cost', 1)
                            
                            # 计算该格子的移动成本（棋子移动成本 * 地形移动成本）
                            cell_cost = piece_move_cost * terrain_move_cost
                            total_cost += cell_cost
                            
                            # 检查当前格子与前一个格子的高度差
                            next_height = state['terrain']['height'][r][c]
                            height_diff = next_height - current_height
                            if abs(height_diff) > 1:
                                emit('error', {'msg': '路径上高度差过大，无法移动'})
                                return
                            
                            # 更新当前高度为下一个格子的高度
                            current_height = next_height
                        
                        # 计算高度移动成本（从起点到终点的总高度差）
                        target_height = state['terrain']['height'][tr][tc]
                        total_height_diff = target_height - state['terrain']['height'][fr][fc]
                        total_cost += total_height_diff
                    else:
                        # 没有高度数据时，只计算地形移动成本
                        for r, c in path:
                            # 检查地形移动成本
                            terrain_move_cost = 1
                            if 'terrain_types' in state and 'terrain' in state:
                                terrain_type = state['terrain']['type'][r][c]
                                if terrain_type in state['terrain_types']:
                                    terrain_move_cost = state['terrain_types'][terrain_type].get('move_cost', 1)
                            
                            # 计算该格子的移动成本（棋子移动成本 * 地形移动成本）
                            cell_cost = piece_move_cost * terrain_move_cost
                            total_cost += cell_cost
                    
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
                else:
                    emit('error', {'msg': '路径上有阻挡，无法移动'})
                    return
        else:
            # 计算移动范围和成本
            # 获取棋子类型数据
            piece_type = attacker['type']
            piece_move_range = 1  # 默认移动范围
            piece_move_cost = 1  # 默认移动成本
            
            if 'piece_types' in state and piece_type in state['piece_types']:
                piece_move_range = state['piece_types'][piece_type].get('move_range', 1)
                piece_move_cost = state['piece_types'][piece_type].get('move_cost', 1)
            
            # 计算移动距离
            move_dist = abs(fr - tr) + abs(fc - tc)
             
            # 检查移动距离是否在棋子的移动范围内
            if move_dist > piece_move_range:
                emit('error', {'msg': f'移动距离超出范围，{piece_type}最大移动距离为 {piece_move_range}'})
                return
            
            # 检查路径上是否有阻挡
            if not is_path_blocked(board, fr, fc, tr, tc):
                # 计算移动成本
                total_cost = 0
                
                # 生成移动路径上的所有格子
                path = []
                if fr == tr:  # 同一行
                    step = 1 if tc > fc else -1
                    for c in range(fc + step, tc + step, step):
                        path.append((fr, c))
                else:  # 同一列
                    step = 1 if tr > fr else -1
                    for r in range(fr + step, tr + step, step):
                        path.append((r, fc))
                
                # 计算每个格子的移动成本并检查高度差
                if 'terrain' in state and 'height' in state['terrain']:
                    # 检查起点和路径上第一个格子的高度差
                    current_height = state['terrain']['height'][fr][fc]
                    
                    for i, (r, c) in enumerate(path):
                        # 检查地形移动成本
                        terrain_move_cost = 1
                        if 'terrain_types' in state and 'terrain' in state:
                            terrain_type = state['terrain']['type'][r][c]
                            if terrain_type in state['terrain_types']:
                                terrain_move_cost = state['terrain_types'][terrain_type].get('move_cost', 1)
                        
                        # 计算该格子的移动成本（棋子移动成本 * 地形移动成本）
                        cell_cost = piece_move_cost * terrain_move_cost
                        total_cost += cell_cost
                        
                        # 检查当前格子与前一个格子的高度差
                        next_height = state['terrain']['height'][r][c]
                        height_diff = next_height - current_height
                        if abs(height_diff) > 1:
                            emit('error', {'msg': '路径上高度差过大，无法移动'})
                            return
                        
                        # 更新当前高度为下一个格子的高度
                        current_height = next_height
                    
                    # 计算高度移动成本（从起点到终点的总高度差）
                    target_height = state['terrain']['height'][tr][tc]
                    total_height_diff = target_height - state['terrain']['height'][fr][fc]
                    total_cost += total_height_diff
                else:
                    # 没有高度数据时，只计算地形移动成本
                    for r, c in path:
                        # 检查地形移动成本
                        terrain_move_cost = 1
                        if 'terrain_types' in state and 'terrain' in state:
                            terrain_type = state['terrain']['type'][r][c]
                            if terrain_type in state['terrain_types']:
                                terrain_move_cost = state['terrain_types'][terrain_type].get('move_cost', 1)
                        
                        # 计算该格子的移动成本（棋子移动成本 * 地形移动成本）
                        cell_cost = piece_move_cost * terrain_move_cost
                        total_cost += cell_cost
                
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
            else:
                emit('error', {'msg': '路径上有阻挡，无法移动'})
                return

    # 情况 B: 移动到己方 (报错)
    elif target['side'] == side:
        emit('error', {'msg': '不能吃己方棋子'})
        return

    # 情况 C: 遭遇战 (修改为：开启决斗状态，暂停结算)
    else:
        # 检查是否是炮棋子的攻击操作
        is_cannon_attack = attacker['type'] == 'P'
        
        if is_cannon_attack:
            # 检查炮是否已经使用过攻击
            if state.get('has_used_cannon', {}).get(str(current_player_id)):
                emit('error', {'msg': '炮一回合只能使用一次攻击'})
                return
        
        # 初始化决斗数据，不进行计算，不扣步数
        state['pending_combat'] = {
            'active': True,
            'distance': dist, # 记录攻击距离
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
    
    # 获取前端传递的k值
    k_value = data.get('k', 0.1)
    
    # 2. 生成随机数和应用卡牌效果
    combat_data = process_combat_roll(state, current_user.id, user_side, role, combat)
    
    # 3. 记录结果到状态
    update_combat_state(combat, role, combat_data)
    
    # 4. 存储k值到战斗状态
    combat['k'] = k_value
    
    # 5. 保存状态并广播更新
    save_and_broadcast_state(room, state, combat_data)
    
    # 5. 检查是否需要结算
    if combat['attacker']['has_rolled'] and combat['defender']['has_rolled']:
        print(f"双方都已掷采，开始结算")
        resolve_combat(room, state)

def validate_combat_roll_request(data):
    """验证决斗抽签请求的有效性"""
    room_id = data.get('room_id')
    # print(f"房间ID: {room_id}")
    
    room = GameRoom.query.get(room_id)
    if not room:
        print(f"错误: 房间 {room_id} 不存在")
        return {'valid': False, 'message': '房间不存在'}
    
    state = room.get_state()
    # print(f"游戏状态: {state}")
    
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
    
    # print(f"用户身份: {role} ({user_side})")
    
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
    # print(f"生成的采: {sticks}")
    
    # 应用卡牌效果
    card_used = False
    card_type = None
    active_card_type = state.get('active_cards', {}).get(str(user_id))
    # print(f"激活的卡牌: {active_card_type}")
    
    if active_card_type:
        card_used = apply_card_effect(state, user_id, active_card_type, sticks, user_side, combat)
        card_type = active_card_type
    
    # 计算数值
    binary_str = "".join(str(x) for x in sticks)
    val = int(binary_str, 2)
    # print(f"计算的数值: {val} (二进制: {binary_str})")
    
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
        # print(f"应用卡牌效果: {card_type}")
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
    # print(f"记录 {role} 的结果: {combat_data['sticks']}, {combat_data['val']}")

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
    # 获取k值，默认为0.1
    k_value = combat.get('k', 0.1)
    
    atk_power = CombatCalculator.calculate_power(
        piece=attacker_piece, 
        base_val=atk_info['val'], 
        distance=dist, 
        role='attacker', 
        enemy_piece=target_piece,
        position=(fc, fr),
        terrain_types=state.get('terrain_types'),
        terrain=state.get('terrain'),
        height_diff=height_diff,
        piece_types=state.get('piece_types'),
        board=board,
        side=atk_info['side'],
        k=k_value
    )
    
    # 检查是否是远程单位攻击近程单位且非临近
    is_ranged_attack = False
    if 'piece_types' in state and attacker_piece['type'] in state['piece_types']:
        is_ranged_attack = state['piece_types'][attacker_piece['type']].get('attack_type') == 'ranged'
    else:
        # 后备逻辑：使用硬编码的棋子类型列表
        is_ranged_attack = attacker_piece['type'] in ['T', 'P']
    
    is_melee_defender = False
    if target_piece:
        if 'piece_types' in state and target_piece['type'] in state['piece_types']:
            is_melee_defender = state['piece_types'][target_piece['type']].get('attack_type') == 'melee'
        else:
            # 后备逻辑：使用硬编码的棋子类型列表
            is_melee_defender = target_piece['type'] in ['S', 'X', 'G']
    is_non_adjacent = dist > 1
    
    # 检查是否是炮攻击地形
    is_cannon_attack_terrain = attacker_piece['type'] == 'P' and def_info.get('is_terrain')
    
    # 计算防守方战力，只有当不是炮攻击地形时才计算
    def_power = 0
    if not is_cannon_attack_terrain and target_piece:
        def_power = CombatCalculator.calculate_power(
            piece=target_piece, 
            base_val=def_info['val'], 
            distance=dist, 
            role='defender', 
            enemy_piece=attacker_piece,
            position=(tc, tr),
            terrain_types=state.get('terrain_types'),
            terrain=state.get('terrain'),
            height_diff=-height_diff,  # 防守方的高度差是相反的
            piece_types=state.get('piece_types'),
            board=board,
            side=def_info['side'],
            k=k_value
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
    
    # 检查是否是炮攻击地形
    is_cannon_attack_terrain = attacker_piece['type'] == 'P' and def_info.get('is_terrain')
    
    if is_cannon_attack_terrain:
        # 炮攻击地形时的处理逻辑
        if atk_power > 30:
            combat_log['winner'] = 'attacker'
            combat_log['msg'] = f"炮攻击成功！战力 {atk_power} > 30"
            
            # 降低目标地块的高度
            if 'terrain' in state and 'height' in state['terrain']:
                if 0 <= tr < len(state['terrain']['height']) and 0 <= tc < len(state['terrain']['height'][tr]):
                    current_height = state['terrain']['height'][tr][tc]
                    new_height = max(-1, current_height - 1)
                    state['terrain']['height'][tr][tc] = new_height
                    combat_log['msg'] += f"，地形高度降低至 {new_height}"
            
            # 如果攻击的是棋子，生成招募牌
            if target_piece:
                # 远程攻击胜利后，直接让对方棋子消失，不进行吃子移动
                board[tr][tc] = None
                
                # 为失败方生成招募牌（只有在棋子损失时）
                # 失败方是防守方（target_piece被击败）
                generate_and_give_recruit_card(room, state, def_info['side'], combat_log)
                
                # # 为失败方生成招募牌（只有在棋子损失时）
                # # 失败方是防守方（target_piece被击败）
                # generate_and_give_recruit_card(room, state, def_info['side'], combat_log)
                
                # # 为失败方生成招募牌（只有在棋子损失时）
                # # 失败方是防守方（target_piece被击败）
                # generate_and_give_recruit_card(room, state, def_info['side'], combat_log)
                
                # # 为失败方生成招募牌（只有在棋子损失时）
                # # 失败方是防守方（target_piece被击败）
                # generate_and_give_recruit_card(room, state, def_info['side'], combat_log)
            
            # 标记炮已经使用过攻击
            if 'has_used_cannon' not in state:
                state['has_used_cannon'] = {}
            state['has_used_cannon'][str(current_user.id)] = True
        else:
            combat_log['winner'] = 'draw'
            combat_log['msg'] = f"炮攻击失败 ({atk_power} <= 30)"
            # 棋盘不动
        
        # 无论攻击成功还是失败，都标记炮已经使用过攻击
        if 'has_used_cannon' not in state:
            state['has_used_cannon'] = {}
        state['has_used_cannon'][str(current_user.id)] = True
    else:
        # 特殊规则：矢的远程狙击 (距离3)
        remote_attack_handled = False
        if attacker_piece['type'] == 'T' and dist == 3:
            remote_attack_handled = True
            if atk_power > def_power and atk_power > 20:
                combat_log['winner'] = 'attacker'
                combat_log['msg'] = f"远程狙击成功！战力 {atk_power} > {def_power} 且 > 20"
                
                # 只有狙击成功才吃子
                if target_piece['type'] == 'X':
                        state['winner'] = atk_info['side']
                        room.status = 'finished'
                        
                        # 更新胜利者的获胜数和连续胜利次数
                        if atk_info['side'] == 'R':
                            winner_user = User.query.get(room.player1_id)
                            # 更新红方连续胜利次数
                            room.player1_streak += 1
                            room.player2_streak = 0
                            room.winner_id = room.player1_id
                        else:
                            winner_user = User.query.get(room.player2_id)
                            # 更新黑方连续胜利次数
                            room.player2_streak += 1
                            room.player1_streak = 0
                            room.winner_id = room.player2_id
                        if winner_user:
                            winner_user.games_won += 1
                
                # 远程攻击胜利后，直接让对方棋子消失，不进行吃子移动
                board[tr][tc] = None
                
                # 为失败方生成招募牌（只有在棋子损失时）
                # 失败方是防守方（target_piece被击败）
                generate_and_give_recruit_card(room, state, def_info['side'], combat_log)
                
                # 为失败方生成招募牌（只有在棋子损失时）
                # 失败方是防守方（target_piece被击败）
                generate_and_give_recruit_card(room, state, def_info['side'], combat_log)
                
                # 为失败方生成招募牌（只有在棋子损失时）
                # 失败方是防守方（target_piece被击败）
                generate_and_give_recruit_card(room, state, def_info['side'], combat_log)
                
                # 炮攻击时降低地形高度
                if attacker_piece['type'] == 'P' and 'terrain' in state and 'height' in state['terrain']:
                    if 0 <= tr < len(state['terrain']['height']) and 0 <= tc < len(state['terrain']['height'][tr]):
                        current_height = state['terrain']['height'][tr][tc]
                        new_height = max(-1, current_height - 1)
                        state['terrain']['height'][tr][tc] = new_height
                        combat_log['msg'] += f"，地形高度降低至 {new_height}"
                        # 标记炮已经使用过攻击
                        if 'has_used_cannon' not in state:
                            state['has_used_cannon'] = {}
                        state['has_used_cannon'][str(current_user.id)] = True
            
            else:
                combat_log['winner'] = 'draw'
                combat_log['msg'] = f"远程被格挡 ({atk_power} < 20)"
                # 棋盘不动
        elif is_ranged_attack and is_melee_defender and is_non_adjacent:
            remote_attack_handled = True
            # 远程单位攻击近程单位且非临近，需要满足特殊条件
            if atk_power > def_power and atk_power > 20:
                combat_log['winner'] = 'attacker'
                combat_log['msg'] = f"远程攻击胜利 ({atk_power} > {def_power} 且 > 20)，满足远程攻击条件"
                
                if target_piece['type'] == 'X':
                    state['winner'] = atk_info['side']
                    room.status = 'finished'
                    
                    # 【新增】更新胜利者的获胜数和连续胜利次数
                    if atk_info['side'] == 'R':
                        winner_user = User.query.get(room.player1_id)
                        # 更新红方连续胜利次数
                        room.player1_streak += 1
                        room.player2_streak = 0
                        room.winner_id = room.player1_id
                    else:
                        winner_user = User.query.get(room.player2_id)
                        # 更新黑方连续胜利次数
                        room.player2_streak += 1
                        room.player1_streak = 0
                        room.winner_id = room.player2_id
                    if winner_user:
                        winner_user.games_won += 1
                
                # 远程攻击胜利后，直接让对方棋子消失，不进行吃子移动
                board[tr][tc] = None
                
                # 为失败方生成招募牌（只有在棋子损失时）
                # 失败方是防守方（target_piece被击败）
                generate_and_give_recruit_card(room, state, def_info['side'], combat_log)
            else:
                combat_log['winner'] = 'draw'
                combat_log['msg'] = f"进攻失败 ({atk_power} vs {def_power})，未满足远程攻击条件"
                # 双方不会有任何变化，远程棋子不会死亡
        else:
            # 只有在没有处理过远程攻击的情况下才执行正常对决的逻辑
            if not remote_attack_handled:
                # 正常对决：近战攻击或远程攻击相邻单位
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
                            room.winner_id = room.player1_id
                        else:
                            winner_user = User.query.get(room.player2_id)
                            # 更新黑方连续胜利次数
                            room.player2_streak += 1
                            room.player1_streak = 0
                            room.winner_id = room.player2_id
                        if winner_user:
                            winner_user.games_won += 1
                    
                    board[tr][tc] = attacker_piece
                    board[fr][fc] = None
                    
                    # 为失败方生成招募牌（只有在棋子损失时）
                    # 失败方是防守方（target_piece被击败）
                    generate_and_give_recruit_card(room, state, def_info['side'], combat_log)
                else:
                    combat_log['winner'] = 'defender'
                    combat_log['msg'] = f"防守反杀 ({def_power} >= {atk_power})"
                    
                    # 进攻方死亡
                    board[fr][fc] = None
                    
                    # 为失败方生成招募牌（只有在棋子损失时）
                    # 失败方是进攻方（attacker_piece被击败）
                    generate_and_give_recruit_card(room, state, atk_info['side'], combat_log)
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
                            room.winner_id = room.player1_id
                        else:
                            winner_user = User.query.get(room.player2_id)
                            # 更新黑方连续胜利次数
                            room.player2_streak += 1
                            room.player1_streak = 0
                            room.winner_id = room.player2_id
                        if winner_user:
                            winner_user.games_won += 1

    # --- 3. 记录战斗日志 ---
    # 获取当前回合数
    turn_number = state.get('turn_number', 1)
    
    # 获取棋子类型
    attacker_piece_type = attacker_piece['type'] if attacker_piece else 'Unknown'
    defender_piece_type = target_piece['type'] if target_piece else 'Terrain'
    
    # 记录战斗日志
    log_combat(room.id, turn_number, atk_info, def_info, combat_log, dist, attacker_piece_type, defender_piece_type)

    # --- 4. 结算收尾 ---
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
    def calculate_power(piece, base_val, distance, role, enemy_piece, position=None, terrain_types=None, terrain=None, height_diff=0, piece_types=None, board=None, side=None, k=0.1):
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
        :param piece_types: 棋子类型数据
        :param board: 棋盘数据
        :param side: 棋子所属阵营
        :param k: 连携系数，默认0.1
        :return: final_power (float)
        """
        p_type = piece['type']
        
        # --- 1. 确定棋子类型 (近战/远程) ---
        if p_type in ['S', 'X', 'G']:
            # 近战棋子
            return CombatCalculator.calculate_melee_power(
                piece=piece, 
                base_val=base_val, 
                distance=distance, 
                role=role, 
                enemy_piece=enemy_piece, 
                position=position, 
                terrain_types=terrain_types, 
                terrain=terrain,
                height_diff=height_diff,
                piece_types=piece_types,
                board=board,
                side=side
            )
        else:
            # 远程棋子
            return CombatCalculator.calculate_ranged_power(
                piece=piece, 
                base_val=base_val, 
                distance=distance, 
                role=role, 
                enemy_piece=enemy_piece, 
                position=position, 
                terrain_types=terrain_types, 
                terrain=terrain,
                height_diff=height_diff,
                piece_types=piece_types,
                board=board,
                side=side
            )

    @staticmethod
    def calculate_melee_power(piece, base_val, distance, role, enemy_piece, position=None, terrain_types=None, terrain=None, height_diff=0, piece_types=None, board=None, side=None, k=0.1):
        """
        计算近战棋子的最终战力
        :param piece: 己方棋子对象
        :param base_val: 掷采出的基础数值
        :param distance: 战斗距离
        :param role: 'attacker' 或 'defender'
        :param enemy_piece: 对手棋子对象 (用于判断是否有针对性克制)
        :param position: 棋子位置 (x, y)
        :param terrain_types: 地形类型数据
        :param terrain: 地形数据
        :param height_diff: 高度差 (当前格子高度 - 目标格子高度)
        :param piece_types: 棋子类型数据
        :param board: 棋盘数据
        :param side: 棋子所属阵营
        :param k: 连携系数，默认0.1
        :return: final_power (float)
        """
        p_type = piece['type']
        multiplier = 1.0

        # --- 1. 连携攻击计算 ---
        if position and board and side and piece_types:
            # 获取当前格子高度
            current_height = 0
            if terrain and 'height' in terrain and position:
                x, y = position
                if 0 <= y < len(terrain['height']) and 0 <= x < len(terrain['height'][y]):
                    current_height = terrain['height'][y][x]
            
            # 获取连携范围（默认为1）
            coop_range = 1
            if piece_types and p_type in piece_types:
                coop_range = piece_types[p_type].get('coop_range', 1)
            
            # 计算连携攻击倍率
            chain_multiplier = CombatCalculator.chainAttack(
                board=board,
                position=position,
                piece_type=p_type,
                coop_range=coop_range,
                role=role,
                current_height=current_height,
                piece_types=piece_types,
                side=side,
                k=k
            )
            multiplier *= chain_multiplier

        # --- 2. 通用规则 (如：枭的全局加成) ---
        if piece_types and p_type in piece_types:
            if 'base_multiplier' in piece_types[p_type]:
                multiplier *= piece_types[p_type]['base_multiplier']
        elif p_type == 'X':
            multiplier *= 1.3  # 后备值
        
        # --- 3. 地形战斗加成 ---
        if position and terrain_types and terrain:
            x, y = position
            if 0 <= y < len(terrain['type']) and 0 <= x < len(terrain['type'][y]):
                terrain_type = terrain['type'][y][x]
                if terrain_type in terrain_types:
                    multiplier *= terrain_types[terrain_type].get('combat_bonus', 1.0)
            
        # 计算结果
        return round(base_val * multiplier, 1)

    @staticmethod
    def calculate_ranged_power(piece, base_val, distance, role, enemy_piece, position=None, terrain_types=None, terrain=None, height_diff=0, piece_types=None, board=None, side=None, k=0.1):
        """
        计算远程棋子的最终战力
        :param piece: 己方棋子对象
        :param base_val: 掷采出的基础数值
        :param distance: 战斗距离
        :param role: 'attacker' 或 'defender'
        :param enemy_piece: 对手棋子对象 (用于判断是否有针对性克制)
        :param position: 棋子位置 (x, y)
        :param terrain_types: 地形类型数据
        :param terrain: 地形数据
        :param height_diff: 高度差 (当前格子高度 - 目标格子高度)
        :param piece_types: 棋子类型数据
        :param board: 棋盘数据
        :param side: 棋子所属阵营
        :param k: 连携系数，默认0.1
        :return: final_power (float)
        """
        p_type = piece['type']
        multiplier = 1.0

        # --- 1. 连携攻击计算 ---
        if position and board and side and piece_types:
            # 获取当前格子高度
            current_height = 0
            if terrain and 'height' in terrain and position:
                x, y = position
                if 0 <= y < len(terrain['height']) and 0 <= x < len(terrain['height'][y]):
                    current_height = terrain['height'][y][x]
            
            # 获取连携范围（默认为1）
            coop_range = 1
            if piece_types and p_type in piece_types:
                coop_range = piece_types[p_type].get('coop_range', 1)
            
            # 计算连携攻击倍率
            chain_multiplier = CombatCalculator.chainAttack(
                board=board,
                position=position,
                piece_type=p_type,
                coop_range=coop_range,
                role=role,
                current_height=current_height,
                piece_types=piece_types,
                side=side,
                k=k
            )
            multiplier *= chain_multiplier

        # --- 2. 通用规则 ---
        if piece_types and p_type in piece_types:
            if 'base_multiplier' in piece_types[p_type]:
                piece_bonus = piece_types[p_type]['base_multiplier']
                multiplier *= piece_bonus
        elif p_type == 'X':
            multiplier *= 1.3  # 后备值
        
        # --- 3. 远程攻击距离和倍率计算 ---
        # 基础攻击/防御倍率
        base_multiplier = 1.0
        if piece_types and p_type in piece_types:
            if role == 'attacker':
                base_multiplier = piece_types[p_type].get('base_power', 1.0)  # 攻击方使用基础攻击力
            else:
                base_multiplier = piece_types[p_type].get('defense_power', 1.0)  # 防御方使用防御倍率
        elif p_type == 'T':
            base_multiplier = 1.2 if role == 'attacker' else 0.8  # 后备值
        elif p_type == 'P':
            base_multiplier = 1.5 if role == 'attacker' else 0.7  # 后备值
        
        # 计算攻击倍率：根据距离和高度差计算远程攻击的倍率调整值
        if role == 'attacker':
            attack_multiplier = CombatCalculator._calc_ranged_multiplier(
                distance=distance,  # 战斗距离（曼哈顿距离）
                base_multiplier=base_multiplier,  # 基础攻击倍率（从数据库或后备值获取）
                height_diff=height_diff  # 高度差（进攻方高度 - 目标高度）
            )
            # 将攻击倍率应用到总倍率上
            multiplier *= attack_multiplier
        else:
            # 防守方直接使用基础防御倍率
            multiplier *= base_multiplier
        
        # --- 4. 地形战斗加成 ---
        # 检查是否有位置信息、地形类型数据和地形数据
        if position and terrain_types and terrain:
            # 提取位置坐标
            x, y = position
            # 检查坐标是否在地形数据的有效范围内
            if 0 <= y < len(terrain['type']) and 0 <= x < len(terrain['type'][y]):
                # 获取该位置的地形类型
                terrain_type = terrain['type'][y][x]
                # 检查该地形类型是否在地形类型数据中
                if terrain_type in terrain_types:
                    terrain_bonus = terrain_types[terrain_type].get('combat_bonus', 1.0)
                    # 应用地形的战斗加成/惩罚（默认为1.0，无加成）
                    multiplier *= terrain_bonus
            
        # 计算结果：将基础值乘以总倍率，并四舍五入到小数点后1位
        final_power = round(base_val * multiplier, 1)
        
        return final_power

    @staticmethod
    def chainAttack(board, position, piece_type, coop_range, role, current_height, piece_types, side, k=0.1):
        """
        计算连携攻击的倍率
        :param board: 棋盘数据
        :param position: 棋子位置 (x, y)
        :param piece_type: 棋子类型
        :param coop_range: 连携范围
        :param role: 'attacker' 或 'defender'
        :param current_height: 棋子所在格子的高度
        :param piece_types: 棋子类型数据
        :param side: 棋子所属阵营
        :param k: 连携系数，默认0.1
        :return: 连携攻击倍率 (float)
        """
        x, y = position
        coop_pieces = []
        
        # 确定检查范围
        start_x = max(0, x - coop_range)
        end_x = min(len(board[0]) - 1, x + coop_range)
        start_y = max(0, y - coop_range)
        end_y = min(len(board) - 1, y + coop_range)
        
        # 遍历范围内的所有格子
        for i in range(start_y, end_y + 1):
            for j in range(start_x, end_x + 1):
                # 跳过自己
                if i == y and j == x:
                    continue
                
                # 检查是否在连携范围内（曼哈顿距离）
                manhattan_distance = abs(i - y) + abs(j - x)
                if manhattan_distance > coop_range:
                    continue
                
                # 检查是否有己方棋子
                piece = board[i][j]
                if piece and piece['side'] == side:
                    # 获取该格子的高度
                    piece_height = 0
                    # 这里需要从地形数据中获取高度，暂时使用0作为默认值
                    
                    # 检查高度差
                    height_diff = abs(current_height - piece_height)
                    if height_diff <= 1:
                        coop_pieces.append(piece)
        
        # 计算连携倍率
        if not coop_pieces:
            # 没有连携棋子时，返回基础倍率
            base_power = 1.0
            if piece_types and piece_type in piece_types:
                if role == 'attacker':
                    base_power = piece_types[piece_type].get('base_power', 1.0)
                else:
                    base_power = piece_types[piece_type].get('defense_power', 1.0)
            return base_power
        
        # 计算连携棋子的倍率总和
        total_coop = 0
        # 统计连携棋子的类型数量T
        unique_types = set()
        for piece in coop_pieces:
            coop_type = piece['type']
            unique_types.add(coop_type)
            if role == 'attacker':
                if piece_types and coop_type in piece_types:
                    total_coop += piece_types[coop_type].get('attack_coop', 1.0)
                else:
                    total_coop += 1.0
            else:  # defender
                if piece_types and coop_type in piece_types:
                    total_coop += piece_types[coop_type].get('defense_coop', 1.0)
                else:
                    total_coop += 1.0
        
        # 计算连携倍率
        number = len(coop_pieces)
        if number == 0:
            return 1.0
        
        # 计算棋子类型数量T
        T = len(unique_types)
        
        # 使用新公式计算连携倍率：Total = (Σx_i) × [1 + k × (N + T - 2)]
        coop_number = total_coop * (1 + k * (number + T - 2))
        
        # 获取基础倍率
        base_power = 1.0
        if piece_types and piece_type in piece_types:
            if role == 'attacker':
                base_power = piece_types[piece_type].get('base_power', 1.0)
            else:
                base_power = piece_types[piece_type].get('defense_power', 1.0)
        
        # 计算最终倍率
        final_multiplier = (base_power + coop_number) / 2
        return final_multiplier

    @staticmethod
    def _calc_ranged_multiplier(distance, base_multiplier, height_diff=0):
        """
        计算远程攻击的倍率
        :param distance: 战斗距离
        :param base_multiplier: 基础攻击倍率
        :param height_diff: 高度差 (当前格子高度 - 目标格子高度)
        :return: multiplier (float)
        """
        # print(f"=== 远程攻击倍率计算开始 ===")
        # print(f"距离: {distance}, 基础倍率: {base_multiplier}, 高度差: {height_diff}")
        
        # 计算标准倍率范围：2 ~ 2+高度差
        standard_range_start = 2
        standard_range_end = 2 + height_diff
        # print(f"标准倍率范围: {standard_range_start} ~ {standard_range_end}")
        
        # 计算最大攻击范围：3+高度差
        max_attack_range = 3 + height_diff
        # print(f"最大攻击范围: {max_attack_range}")
        
        # 高度差加成
        height_bonus = 0.1 * height_diff
        # print(f"高度差加成: {height_bonus}")
        
        # 检查是否超出最大攻击范围
        if distance < 1 or distance > max_attack_range:
            # 超出攻击范围
            # print(f"超出攻击范围，返回 0.0")
            return 0.0
        elif distance == 1:
            # 第一格：基础倍率 - 0.4 + 高度加成
            calc_value = base_multiplier - 0.4 + height_bonus
            result = max(0.1, calc_value)
            # print(f"第一格计算: {base_multiplier} - 0.4 + {height_bonus} = {calc_value}, 取最大值: {result}")
            return result
        elif 2 <= distance <= standard_range_end:
            # 第2到2+高度差区间内：基础倍率 + 高度加成
            result = base_multiplier + height_bonus
            # print(f"中间区间计算: {base_multiplier} + {height_bonus} = {result}")
            return result
        else:
            # 大于2+高度差的格：基础倍率 - 0.7 + 高度加成
            calc_value = base_multiplier - 0.7 + height_bonus
            result = max(0.1, calc_value)
            # print(f"超出区间计算: {base_multiplier} - 0.7 + {height_bonus} = {calc_value}, 取最大值: {result}")
            return result


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
        # 重置炮的攻击使用状态
        if 'has_used_cannon' in state:
            state['has_used_cannon'] = {}
        
        # 增加回合数
        if 'turn_number' not in state:
            state['turn_number'] = 1
        state['turn_number'] += 1
        
        return True
    return False

def get_available_pieces(piece_types, power_threshold, attack_type=None):
    """
    根据条件获取可用的棋子类型
    :param piece_types: 棋子类型字典
    :param power_threshold: 攻击力阈值，True表示大于等于1.5，False表示小于1.5
    :param attack_type: 攻击类型，None表示所有类型，'melee'表示近程，'ranged'表示远程
    :return: 可用棋子类型列表
    """
    available_pieces = []
    for piece_type, piece_info in piece_types.items():
        # 排除枭棋子(X)
        if piece_type == 'X':
            continue
        
        # 检查攻击力阈值
        base_power = piece_info.get('base_power', 1.0)
        if power_threshold:
            if base_power < 1.5:
                continue
        else:
            if base_power >= 1.5:
                continue
        
        # 检查攻击类型
        if attack_type:
            if piece_info.get('attack_type') != attack_type:
                continue
        
        available_pieces.append(piece_type)
    return available_pieces

def select_piece_type(piece_types):
    """
    根据概率选择要招募的棋子类型
    70%概率招募base_power < 1.5的棋子
    30%概率招募base_power >= 1.5的棋子
    在每个类别中，60%概率招募近程攻击棋子，40%招募远程攻击棋子
    :param piece_types: 棋子类型字典
    :return: 选中的棋子类型
    """
    import random
    
    # 第一步：决定招募高攻击力还是低攻击力棋子
    rand1 = random.random()
    power_threshold = rand1 <= 0.3  # 30%概率高攻击力
    
    # 第二步：决定招募近程还是远程攻击棋子
    rand2 = random.random()
    attack_type = 'melee' if rand2 <= 0.6 else 'ranged'  # 60%概率近程
    
    # 获取符合条件的棋子类型
    available_pieces = get_available_pieces(piece_types, power_threshold, attack_type)
    
    # 如果没有符合条件的棋子，尝试放宽攻击类型限制
    if not available_pieces:
        available_pieces = get_available_pieces(piece_types, power_threshold)
    
    # 如果仍然没有符合条件的棋子，尝试放宽攻击力限制
    if not available_pieces:
        power_threshold = not power_threshold
        available_pieces = get_available_pieces(piece_types, power_threshold)
    
    # 如果仍然没有符合条件的棋子，返回默认棋子
    if not available_pieces:
        return 'S'  # 默认返回散棋子
    
    # 随机选择一个棋子类型
    return random.choice(available_pieces)

def use_recruit_card(room, state, user_side, card_type):
    """
    使用招募牌
    :param room: 游戏房间对象
    :param state: 游戏状态
    :param user_side: 用户阵营
    :param card_type: 卡牌类型
    :return: (成功标志, 消息)
    """
    board = state.get('board', [])
    if not board:
        return False, '棋盘数据不存在'
    
    # 获取棋子类型信息
    piece_types = state.get('piece_types', {})
    if not piece_types:
        return False, '棋子类型数据不存在'
    
    # 提取棋子类型
    piece_type = None
    if card_type.startswith('card_recruit_'):
        # 从卡片类型中提取棋子类型，如 card_recruit_S -> S
        piece_type = card_type.split('_')[-1]
        # 验证棋子类型是否存在
        if piece_type not in piece_types:
            piece_type = select_piece_type(piece_types)
    else:
        # 旧类型，使用随机选择
        piece_type = select_piece_type(piece_types)
    
    # 找到己方最后面的空位
    # 红方（R）的最后面是第0行，黑方（B）的最后面是最后一行
    if user_side == 'R':
        # 红方从第0行开始查找
        for c in range(len(board[0])):
            if board[0][c] is None:
                # 在空位生成棋子
                board[0][c] = {
                    'side': user_side,
                    'type': piece_type
                }
                piece_name = piece_types.get(piece_type, {}).get('name', piece_type)
                return True, f'成功招募{piece_name}棋子'
    else:
        # 黑方从最后一行开始查找
        last_row = len(board) - 1
        for c in range(len(board[last_row])):
            if board[last_row][c] is None:
                # 在空位生成棋子
                board[last_row][c] = {
                    'side': user_side,
                    'type': piece_type
                }
                piece_name = piece_types.get(piece_type, {}).get('name', piece_type)
                return True, f'成功招募{piece_name}棋子'
    
    return False, '没有空位可以招募棋子'

def generate_recruit_card(piece_types):
    """
    生成招募牌，返回具体的棋子类型
    :param piece_types: 棋子类型字典
    :return: 卡牌类型字符串
    """
    piece_type = select_piece_type(piece_types)
    return f'card_recruit_{piece_type}'  # 返回具体的招募卡片类型，如 card_recruit_S, card_recruit_G 等

def generate_and_give_recruit_card(room, state, loser_side, combat_log):
    """
    为失败方生成并给予招募牌
    :param room: 游戏房间对象
    :param state: 游戏状态
    :param loser_side: 失败方阵营
    :param combat_log: 战斗日志
    :return: None
    """
    # 获取棋子类型信息
    piece_types = state.get('piece_types', {})
    
    # 生成招募牌
    recruit_card = generate_recruit_card(piece_types)
    
    # 提取棋子类型
    piece_type = recruit_card.split('_')[-1]
    piece_name = piece_types.get(piece_type, {}).get('name', piece_type)
    recruit_card_name = f'招募{piece_name}'
    
    # 确定失败方用户ID
    loser_user_id = room.player1_id if loser_side == 'R' else room.player2_id
    
    # 确保cards字典存在
    if 'cards' not in state:
        state['cards'] = {}
    if str(loser_user_id) not in state['cards']:
        state['cards'][str(loser_user_id)] = {}
    
    # 增加招募牌数量
    state['cards'][str(loser_user_id)][recruit_card] = state['cards'][str(loser_user_id)].get(recruit_card, 0) + 1
    
    # 更新战斗日志
    combat_log['msg'] += f"，失败方获得招募牌: {recruit_card_name}"
    combat_log['recruit_card_gained'] = recruit_card
    combat_log['recruit_card_name'] = recruit_card_name
    combat_log['recruit_card_owner'] = loser_side

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

def check_remote_attack_height(state, fr, fc, tr, tc):
    """
    检查远程攻击路径上的高度差
    如果攻击目标和棋子之间具有高度过高的区块或攻击目标较棋子很高，则无法攻击
    计算公式：目标区块高度（中间区块高度）- 棋子所在格高度 > 2，则无法攻击
    
    参数：
    - state: 游戏状态
    - fr, fc: 攻击者所在行、列
    - tr, tc: 目标所在行、列
    
    返回：
    - (bool, str): (是否可以攻击, 错误信息)
    """
    # 检查是否有地形高度数据
    if 'terrain' not in state or 'height' not in state['terrain']:
        return True, ""
    
    terrain_height = state['terrain']['height']
    
    # 检查坐标是否有效
    if not (0 <= fr < len(terrain_height) and 0 <= fc < len(terrain_height[fr])):
        return True, ""
    if not (0 <= tr < len(terrain_height) and 0 <= tc < len(terrain_height[tr])):
        return True, ""
    
    # 获取攻击者所在格的高度
    attacker_height = terrain_height[fr][fc]
    
    # 检查攻击目标的高度
    target_height = terrain_height[tr][tc]
    if target_height - attacker_height > 2:
        return False, f"目标高度过高，无法攻击！目标高度: {target_height}，攻击者高度: {attacker_height}，高度差: {target_height - attacker_height} > 2"
    
    # 检查路径上的所有中间区块的高度
    if fr == tr: # 同一行
        step = 1 if tc > fc else -1
        for c in range(fc + step, tc, step):
            if 0 <= c < len(terrain_height[fr]):
                mid_height = terrain_height[fr][c]
                if mid_height - attacker_height > 2:
                    return False, f"路径上有高度过高的区块，无法攻击！中间区块高度: {mid_height}，攻击者高度: {attacker_height}，高度差: {mid_height - attacker_height} > 2"
    elif fc == tc: # 同一列
        step = 1 if tr > fr else -1
        for r in range(fr + step, tr, step):
            if 0 <= r < len(terrain_height) and 0 <= fc < len(terrain_height[r]):
                mid_height = terrain_height[r][fc]
                if mid_height - attacker_height > 2:
                    return False, f"路径上有高度过高的区块，无法攻击！中间区块高度: {mid_height}，攻击者高度: {attacker_height}，高度差: {mid_height - attacker_height} > 2"
    
    return True, ""

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
        # 对于招募牌，不需要在战斗阶段使用
        if card_type.startswith('card_recruit_') or card_type == 'card_bad_luck':
            # 招募牌可以在非战斗阶段使用
            pass
        else:
            return emit('error', {'msg': '卡牌仅能在战斗决斗阶段使用'})

    # 2. 确认当前用户在战斗中的身份 (进攻方 or 防守方)
    user_side = 'R' if room.player1_id == current_user.id else 'B'
    
    # 对于招募牌，不需要在战斗中
    if not (card_type.startswith('card_recruit_') or card_type == 'card_bad_luck'):
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

    # 5. 处理招募牌的使用
    if card_type.startswith('card_recruit_') or card_type == 'card_bad_luck':
        # 使用招募牌
        success, msg = use_recruit_card(room, state, user_side, card_type)
        if success:
            # 消耗卡牌
            state['cards'][user_key][card_type] -= 1
            if state['cards'][user_key][card_type] <= 0:
                del state['cards'][user_key][card_type]
            # 保存状态
            room.set_state(state)
            db.session.commit()
            emit('board_update', {'state': state, 'card_used': True, 'msg': msg}, room=str(room.id))
        else:
            emit('error', {'msg': msg})
        return

    # 6. 切换选中状态（仅适用于传统卡牌）
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

# --- 战斗日志记录函数 ---
def log_combat(room_id, turn_number, atk_info, def_info, combat_log, distance, attacker_piece_type, defender_piece_type):
    """
    记录战斗日志到数据库
    
    参数：
    - room_id: 游戏房间ID
    - turn_number: 回合数
    - atk_info: 进攻方信息
    - def_info: 防守方信息
    - combat_log: 战斗日志
    - distance: 攻击距离
    - attacker_piece_type: 进攻方棋子类型
    - defender_piece_type: 防守方棋子类型
    """
    # 获取进攻方和防守方的用户ID
    attacker_id = atk_info.get('user_id')
    defender_id = def_info.get('user_id')
    
    # 如果没有用户ID，则从房间中获取
    room = GameRoom.query.get(room_id)
    if not attacker_id or not defender_id:
        # 根据阵营获取用户ID
        attacker_side = atk_info.get('side', 'R')
        defender_side = def_info.get('side', 'B')
        
        attacker_id = room.player1_id if attacker_side == 'R' else room.player2_id
        defender_id = room.player1_id if defender_side == 'R' else room.player2_id
    
    # 获取抽签结果
    attacker_sticks = atk_info.get('sticks', []) or []
    defender_sticks = def_info.get('sticks', []) or []
    
    # 获取二进制结果
    attacker_binary = atk_info.get('binary_str', '')
    defender_binary = def_info.get('binary_str', '')
    
    # 获取最终战力
    attacker_power = combat_log['attacker']['final_power']
    defender_power = combat_log['defender']['final_power']
    
    # 获取战斗胜利者
    winner = combat_log['winner']
    
    # 获取使用的锦囊牌
    attacker_card = atk_info.get('card_type')
    defender_card = def_info.get('card_type')
    
    # 计算战斗顺序ID（该房间已有的战斗记录数 + 1）
    existing_count = CombatLog.query.filter_by(room_id=room_id).count()
    combat_sequence = existing_count + 1
    
    # 创建战斗日志记录
    combat_log_entry = CombatLog(
        room_id=room_id,
        combat_sequence=combat_sequence,
        turn_number=turn_number,
        attacker_id=attacker_id,
        defender_id=defender_id,
        attacker_sticks=json.dumps(attacker_sticks),
        defender_sticks=json.dumps(defender_sticks),
        attacker_binary=attacker_binary,
        defender_binary=defender_binary,
        attacker_power=attacker_power,
        defender_power=defender_power,
        attacker_piece=attacker_piece_type,
        defender_piece=defender_piece_type,
        attacker_card=attacker_card,
        defender_card=defender_card,
        winner=winner,
        distance=distance
    )
    
    # 保存到数据库
    db.session.add(combat_log_entry)
    # 注意：这里不提交，由调用方统一提交