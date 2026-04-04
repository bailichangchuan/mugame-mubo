from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple


class PieceBehavior(ABC):
    """
    棋子行为的抽象基类，定义所有棋子必须实现的方法
    """
    
    def __init__(self, piece_config: Dict[str, Any]):
        """
        初始化棋子行为
        
        Args:
            piece_config: 棋子配置信息
        """
        self.config = piece_config
        self.piece_type = piece_config.get('type')
    
    @abstractmethod
    def can_move(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int], game_state: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        检查棋子是否可以移动到目标位置
        
        Args:
            from_pos: 起始位置 (x, y)
            to_pos: 目标位置 (x, y)
            game_state: 游戏状态
            
        Returns:
            Tuple[bool, Optional[str]]: (是否可以移动, 错误信息)
        """
        pass
    
    @abstractmethod
    def calculate_move_cost(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int], game_state: Dict[str, Any]) -> int:
        """
        计算移动成本
        
        Args:
            from_pos: 起始位置 (x, y)
            to_pos: 目标位置 (x, y)
            game_state: 游戏状态
            
        Returns:
            int: 移动成本
        """
        pass
    
    @abstractmethod
    def can_attack(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int], game_state: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        检查棋子是否可以攻击目标位置
        
        Args:
            from_pos: 起始位置 (x, y)
            to_pos: 目标位置 (x, y)
            game_state: 游戏状态
            
        Returns:
            Tuple[bool, Optional[str]]: (是否可以攻击, 错误信息)
        """
        pass
    
    @abstractmethod
    def calculate_attack_power(self, attack_value: int, distance: int, height_diff: int, game_state: Dict[str, Any]) -> float:
        """
        计算攻击威力
        
        Args:
            attack_value: 基础攻击值
            distance: 攻击距离
            height_diff: 高度差
            game_state: 游戏状态
            
        Returns:
            float: 最终攻击威力
        """
        pass


class MeleePieceBehavior(PieceBehavior):
    """
    近战棋子行为实现
    """
    
    def can_move(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int], game_state: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
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
        
        # 近战棋子只能攻击相邻格子
        if distance != 1:
            return False, "近战棋子只能攻击相邻格子"
        
        return True, None
    
    def calculate_attack_power(self, attack_value: int, distance: int, height_diff: int, game_state: Dict[str, Any]) -> float:
        # 基础攻击倍率
        base_multiplier = self.config.get('base_power', 1.0)
        
        # 高度差加成
        height_bonus = 0.1 * max(0, height_diff)
        
        return attack_value * (base_multiplier + height_bonus)


class RangedPieceBehavior(PieceBehavior):
    """
    远程棋子行为实现
    """
    
    def can_move(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int], game_state: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
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
        
        # 检查是否是直线攻击
        if from_pos[0] != to_pos[0] and from_pos[1] != to_pos[1]:
            return False, "远程攻击只能直线攻击"
        
        # 计算最大攻击范围
        max_range = self.config.get('combat_range', 3)
        
        # 高度差影响攻击范围
        terrain = game_state.get('terrain', {})
        if 'height' in terrain:
            from_y, from_x = from_pos
            to_y, to_x = to_pos
            
            if (0 <= from_y < len(terrain['height']) and 0 <= from_x < len(terrain['height'][from_y]) and
                0 <= to_y < len(terrain['height']) and 0 <= to_x < len(terrain['height'][to_y])):
                from_height = terrain['height'][from_y][from_x]
                to_height = terrain['height'][to_y][to_x]
                height_diff = from_height - to_height
                max_range += height_diff
        
        max_range = max(1, max_range)
        
        if distance < 1 or distance > max_range:
            return False, f"攻击距离超出范围 (1-{max_range})"
        
        # 检查路径是否被阻挡
        board = game_state.get('board', [])
        if self._is_path_blocked(board, from_pos, to_pos):
            return False, "路径上有阻挡，无法攻击"
        
        return True, None
    
    def calculate_attack_power(self, attack_value: int, distance: int, height_diff: int, game_state: Dict[str, Any]) -> float:
        # 基础攻击倍率
        base_multiplier = self.config.get('base_power', 1.0)
        
        # 计算标准倍率范围
        standard_range_start = 2
        standard_range_end = 2 + max(0, height_diff)
        
        # 高度差加成
        height_bonus = 0.1 * max(0, height_diff)
        
        # 根据距离计算攻击倍率
        if distance == 1:
            # 第一格：基础倍率 - 0.4 + 高度加成
            attack_multiplier = base_multiplier - 0.4 + height_bonus
        elif 2 <= distance <= standard_range_end:
            # 中间区间：基础倍率 + 高度加成
            attack_multiplier = base_multiplier + height_bonus
        else:
            # 远距离：基础倍率 - 0.7 + 高度加成
            attack_multiplier = base_multiplier - 0.7 + height_bonus
        
        # 确保攻击倍率不为负
        attack_multiplier = max(0.1, attack_multiplier)
        
        return attack_value * attack_multiplier
    
    def _is_path_blocked(self, board: list, from_pos: Tuple[int, int], to_pos: Tuple[int, int]) -> bool:
        """
        检查攻击路径是否被阻挡
        """
        from_y, from_x = from_pos
        to_y, to_x = to_pos
        
        # 水平攻击
        if from_y == to_y:
            start_x = min(from_x, to_x) + 1
            end_x = max(from_x, to_x)
            for x in range(start_x, end_x):
                if board[from_y][x] is not None:
                    return True
        # 垂直攻击
        elif from_x == to_x:
            start_y = min(from_y, to_y) + 1
            end_y = max(from_y, to_y)
            for y in range(start_y, end_y):
                if board[y][from_x] is not None:
                    return True
        
        return False


class CannonPieceBehavior(RangedPieceBehavior):
    """
    炮棋子行为实现
    """
    
    def can_move(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int], game_state: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
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
        
        # 炮移动消耗两倍
        move_cost *= 2
        
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
        # 检查炮是否已经使用过攻击
        current_player_id = game_state.get('turn')
        if game_state.get('has_used_cannon', {}).get(str(current_player_id)):
            return False, "炮一回合只能使用一次攻击"
        
        # 使用父类的攻击检查
        return super().can_attack(from_pos, to_pos, game_state)
    
    def calculate_attack_power(self, attack_value: int, distance: int, height_diff: int, game_state: Dict[str, Any]) -> float:
        # 炮的攻击计算
        base_multiplier = self.config.get('base_power', 1.5)
        
        # 高度差加成
        height_bonus = 0.1 * max(0, height_diff)
        
        # 距离影响
        if distance == 1:
            attack_multiplier = base_multiplier - 0.4 + height_bonus
        else:
            attack_multiplier = base_multiplier + height_bonus
        
        return attack_value * attack_multiplier


class PieceBehaviorFactory:
    """
    棋子行为工厂类，根据棋子类型创建对应的行为实例
    """
    
    _behavior_classes = {
        'melee': MeleePieceBehavior,
        'ranged': RangedPieceBehavior,
        'cannon': CannonPieceBehavior
    }
    
    @classmethod
    def register_behavior(cls, behavior_type: str, behavior_class: type):
        """
        注册新的棋子行为类型
        
        Args:
            behavior_type: 行为类型名称
            behavior_class: 行为类
        """
        cls._behavior_classes[behavior_type] = behavior_class
    
    @classmethod
    def create_behavior(cls, piece_config: Dict[str, Any]) -> PieceBehavior:
        """
        创建棋子行为实例
        
        Args:
            piece_config: 棋子配置信息
            
        Returns:
            PieceBehavior: 棋子行为实例
        """
        # 根据棋子类型确定行为类型
        piece_type = piece_config.get('type')
        behavior_type = piece_config.get('behavior_type')
        
        # 默认行为类型
        if not behavior_type:
            if piece_type in ['S', 'X', 'G']:
                behavior_type = 'melee'
            elif piece_type in ['T']:
                behavior_type = 'ranged'
            elif piece_type in ['P']:
                behavior_type = 'cannon'
            else:
                behavior_type = 'melee'
        
        # 创建行为实例
        behavior_class = cls._behavior_classes.get(behavior_type, MeleePieceBehavior)
        return behavior_class(piece_config)
