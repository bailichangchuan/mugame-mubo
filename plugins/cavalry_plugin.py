PLUGIN_INFO = {
    'name': '骑兵插件',
    'version': '1.0.0',
    'description': '添加骑兵棋子类型'
}

from game_logic.plugin_system import PluginSystem
from game_logic.piece_behavior import PieceBehavior
from typing import Tuple, Optional, Dict, Any


class CavalryPieceBehavior(PieceBehavior):
    """
    骑兵棋子行为实现
    """
    
    def can_move(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int], game_state: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        # 计算曼哈顿距离
        distance = abs(from_pos[0] - to_pos[0]) + abs(from_pos[1] - to_pos[1])
        
        # 骑兵可以移动2格
        if distance > 2:
            return False, "骑兵最多只能移动两格"
        
        # 检查地形是否可通行
        terrain = game_state.get('terrain', {})
        terrain_types = game_state.get('terrain_types', {})
        
        if 'type' in terrain:
            y, x = to_pos
            if 0 <= y < len(terrain['type']) and 0 <= x < len(terrain['type'][y]):
                terrain_type = terrain['type'][y][x]
                if terrain_type in terrain_types:
                    if terrain_types[terrain_type].get('passability', 1) == 0:
                        return False, "该地形不可站立"
        
        return True, None
    
    def calculate_move_cost(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int], game_state: Dict[str, Any]) -> int:
        # 基础移动成本
        move_cost = 1
        
        # 地形移动成本
        terrain = game_state.get('terrain', {})
        terrain_types = game_state.get('terrain_types', {})
        
        if 'type' in terrain:
            y, x = to_pos
            if 0 <= y < len(terrain['type']) and 0 <= x < len(terrain['type'][y]):
                terrain_type = terrain['type'][y][x]
                if terrain_type in terrain_types:
                    move_cost = terrain_types[terrain_type].get('move_cost', 1)
        
        # 骑兵移动消耗减半
        move_cost = max(1, move_cost // 2)
        
        # 高度差成本
        height_cost = 0
        if 'height' in terrain:
            from_y, from_x = from_pos
            to_y, to_x = to_pos
            
            if (0 <= from_y < len(terrain['height']) and 0 <= from_x < len(terrain['height'][from_y]) and
                0 <= to_y < len(terrain['height']) and 0 <= to_x < len(terrain['height'][to_y])):
                from_height = terrain['height'][from_y][from_x]
                to_height = terrain['height'][to_y][to_x]
                height_diff = to_height - from_height
                height_cost = max(0, height_diff)
        
        return move_cost + height_cost
    
    def can_attack(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int], game_state: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        # 计算曼哈顿距离
        distance = abs(from_pos[0] - to_pos[0]) + abs(from_pos[1] - to_pos[1])
        
        # 骑兵可以攻击相邻格子
        if distance != 1:
            return False, "骑兵只能攻击相邻格子"
        
        return True, None
    
    def calculate_attack_power(self, attack_value: int, distance: int, height_diff: int, game_state: Dict[str, Any]) -> float:
        # 基础攻击倍率
        base_multiplier = self.config.get('base_power', 1.2)
        
        # 高度差加成
        height_bonus = 0.1 * max(0, height_diff)
        
        # 骑兵冲锋加成
        charge_bonus = 0.2 if distance == 1 else 0
        
        return attack_value * (base_multiplier + height_bonus + charge_bonus)


def register_plugin(plugin_system: PluginSystem):
    """
    注册插件
    """
    # 注册新的行为类型
    plugin_system.register_behavior_type('cavalry', CavalryPieceBehavior)
    
    # 注册新的棋子类型
    plugin_system.register_piece_type('C', {
        'name': '骑兵',
        'description': '快速移动单位，具有冲锋能力',
        'move_range': 2,
        'combat_range': 1,
        'base_power': 1.2,
        'behavior_type': 'cavalry'
    })
