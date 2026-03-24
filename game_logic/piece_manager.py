from typing import Dict, Any, Optional, Tuple
from .piece_behavior import PieceBehaviorFactory, PieceBehavior


class PieceManager:
    """
    棋子管理器，负责管理所有棋子的行为
    """
    
    def __init__(self, piece_types: Dict[str, Dict[str, Any]]):
        """
        初始化棋子管理器
        
        Args:
            piece_types: 棋子类型配置
        """
        self.piece_types = piece_types
        self.behaviors: Dict[str, PieceBehavior] = {}
        self._initialize_behaviors()
    
    def _initialize_behaviors(self):
        """
        初始化所有棋子行为
        """
        for piece_type, config in self.piece_types.items():
            # 确保配置包含类型信息
            config['type'] = piece_type
            # 创建行为实例
            behavior = PieceBehaviorFactory.create_behavior(config)
            self.behaviors[piece_type] = behavior
    
    def register_piece_type(self, piece_type: str, config: Dict[str, Any]):
        """
        注册新的棋子类型
        
        Args:
            piece_type: 棋子类型
            config: 棋子配置
        """
        config['type'] = piece_type
        behavior = PieceBehaviorFactory.create_behavior(config)
        self.behaviors[piece_type] = behavior
        self.piece_types[piece_type] = config
    
    def get_piece_behavior(self, piece_type: str) -> Optional[PieceBehavior]:
        """
        获取棋子行为实例
        
        Args:
            piece_type: 棋子类型
            
        Returns:
            Optional[PieceBehavior]: 棋子行为实例
        """
        return self.behaviors.get(piece_type)
    
    def can_move(self, piece: Dict[str, Any], from_pos: Tuple[int, int], to_pos: Tuple[int, int], game_state: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        检查棋子是否可以移动到目标位置
        
        Args:
            piece: 棋子对象
            from_pos: 起始位置 (x, y)
            to_pos: 目标位置 (x, y)
            game_state: 游戏状态
            
        Returns:
            Tuple[bool, Optional[str]]: (是否可以移动, 错误信息)
        """
        piece_type = piece.get('type')
        behavior = self.get_piece_behavior(piece_type)
        
        if not behavior:
            return False, f"未知棋子类型: {piece_type}"
        
        return behavior.can_move(from_pos, to_pos, game_state)
    
    def calculate_move_cost(self, piece: Dict[str, Any], from_pos: Tuple[int, int], to_pos: Tuple[int, int], game_state: Dict[str, Any]) -> int:
        """
        计算移动成本
        
        Args:
            piece: 棋子对象
            from_pos: 起始位置 (x, y)
            to_pos: 目标位置 (x, y)
            game_state: 游戏状态
            
        Returns:
            int: 移动成本
        """
        piece_type = piece.get('type')
        behavior = self.get_piece_behavior(piece_type)
        
        if not behavior:
            return 1  # 默认移动成本
        
        return behavior.calculate_move_cost(from_pos, to_pos, game_state)
    
    def can_attack(self, piece: Dict[str, Any], from_pos: Tuple[int, int], to_pos: Tuple[int, int], game_state: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        检查棋子是否可以攻击目标位置
        
        Args:
            piece: 棋子对象
            from_pos: 起始位置 (x, y)
            to_pos: 目标位置 (x, y)
            game_state: 游戏状态
            
        Returns:
            Tuple[bool, Optional[str]]: (是否可以攻击, 错误信息)
        """
        piece_type = piece.get('type')
        behavior = self.get_piece_behavior(piece_type)
        
        if not behavior:
            return False, f"未知棋子类型: {piece_type}"
        
        return behavior.can_attack(from_pos, to_pos, game_state)
    
    def calculate_attack_power(self, piece: Dict[str, Any], attack_value: int, distance: int, height_diff: int, game_state: Dict[str, Any]) -> float:
        """
        计算攻击威力
        
        Args:
            piece: 棋子对象
            attack_value: 基础攻击值
            distance: 攻击距离
            height_diff: 高度差
            game_state: 游戏状态
            
        Returns:
            float: 最终攻击威力
        """
        piece_type = piece.get('type')
        behavior = self.get_piece_behavior(piece_type)
        
        if not behavior:
            return attack_value  # 默认攻击威力
        
        return behavior.calculate_attack_power(attack_value, distance, height_diff, game_state)
    
    def get_piece_config(self, piece_type: str) -> Optional[Dict[str, Any]]:
        """
        获取棋子配置
        
        Args:
            piece_type: 棋子类型
            
        Returns:
            Optional[Dict[str, Any]]: 棋子配置
        """
        return self.piece_types.get(piece_type)
    
    def get_all_piece_types(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有棋子类型配置
        
        Returns:
            Dict[str, Dict[str, Any]]: 所有棋子类型配置
        """
        return self.piece_types
