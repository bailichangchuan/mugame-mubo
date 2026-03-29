"""
AI玩家模块
提供AI决策逻辑，用于自动控制游戏中的棋子
"""

import random
from typing import Dict, Any, List, Tuple, Optional
from .piece_manager import PieceManager


class AIPlayer:
    """
    AI玩家类，负责分析游戏状态并做出决策
    """
    
    def __init__(self, piece_manager: PieceManager, difficulty: str = 'medium'):
        """
        初始化AI玩家
        
        Args:
            piece_manager: 棋子管理器
            difficulty: 难度级别 ('easy', 'medium', 'hard')
        """
        self.piece_manager = piece_manager
        self.difficulty = difficulty
        self.ai_side = 'B'  # AI默认控制黑方
    
    def set_side(self, side: str):
        """
        设置AI控制的阵营
        
        Args:
            side: 阵营 ('R' 或 'B')
        """
        self.ai_side = side
    
    def analyze_board(self, game_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析棋盘状态
        
        Args:
            game_state: 游戏状态
            
        Returns:
            Dict[str, Any]: 分析结果
        """
        board = game_state.get('board', [])
        if not board:
            return {'pieces': [], 'enemies': [], 'empty_spaces': []}
        
        ai_pieces = []
        enemy_pieces = []
        empty_spaces = []
        
        # 遍历棋盘，找出AI的棋子、敌方棋子和空格
        for y in range(len(board)):
            for x in range(len(board[y])):
                piece = board[y][x]
                if piece:
                    if piece.get('side') == self.ai_side:
                        ai_pieces.append({'pos': (x, y), 'piece': piece})
                    else:
                        enemy_pieces.append({'pos': (x, y), 'piece': piece})
                else:
                    empty_spaces.append((x, y))
        
        return {
            'ai_pieces': ai_pieces,
            'enemy_pieces': enemy_pieces,
            'empty_spaces': empty_spaces
        }
    
    def evaluate_move(self, piece: Dict[str, Any], from_pos: Tuple[int, int], 
                     to_pos: Tuple[int, int], game_state: Dict[str, Any]) -> float:
        """
        评估移动的价值
        
        Args:
            piece: 棋子对象
            from_pos: 起始位置
            to_pos: 目标位置
            game_state: 游戏状态
            
        Returns:
            float: 移动价值分数
        """
        score = 0.0
        
        # 检查是否可以移动
        can_move, error = self.piece_manager.can_move(
            piece, from_pos, to_pos, game_state
        )
        
        if not can_move:
            return -1000.0
        
        # 检查是否可以攻击
        can_attack, _ = self.piece_manager.can_attack(
            piece, from_pos, to_pos, game_state
        )
        
        if can_attack:
            # 如果可以攻击，增加分数
            score += 50.0
            
            # 检查目标是否是敌方棋子
            board = game_state.get('board', [])
            target = board[to_pos[1]][to_pos[0]] if board else None
            if target and target.get('side') != self.ai_side:
                # 攻击敌方棋子，增加分数
                score += 100.0
                
                # 如果目标是枭，增加更多分数
                if target.get('type') == 'X':
                    score += 500.0
        
        # 根据难度调整分数
        if self.difficulty == 'easy':
            score *= 0.5
        elif self.difficulty == 'hard':
            score *= 1.5
        
        # 添加一些随机性
        score += random.uniform(-10.0, 10.0)
        
        return score
    
    def get_best_move(self, game_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        获取最佳移动
        
        Args:
            game_state: 游戏状态
            
        Returns:
            Optional[Dict[str, Any]]: 最佳移动信息，如果没有找到则返回None
        """
        analysis = self.analyze_board(game_state)
        ai_pieces = analysis['ai_pieces']
        
        if not ai_pieces:
            return None
        
        best_move = None
        best_score = -float('inf')
        
        # 遍历所有AI棋子
        for piece_info in ai_pieces:
            from_pos = piece_info['pos']
            piece = piece_info['piece']
            
            # 获取棋子的移动范围
            piece_type = piece.get('type')
            piece_config = self.piece_manager.get_piece_config(piece_type)
            move_range = piece_config.get('move_range', 1) if piece_config else 1
            
            # 生成所有可能的移动
            possible_moves = self._generate_possible_moves(
                from_pos, move_range, game_state
            )
            
            # 评估每个可能的移动
            for to_pos in possible_moves:
                score = self.evaluate_move(piece, from_pos, to_pos, game_state)
                
                if score > best_score:
                    best_score = score
                    best_move = {
                        'from_pos': from_pos,
                        'to_pos': to_pos,
                        'piece': piece,
                        'score': score
                    }
        
        return best_move
    
    def _generate_possible_moves(self, from_pos: Tuple[int, int], 
                                move_range: int, game_state: Dict[str, Any]) -> List[Tuple[int, int]]:
        """
        生成所有可能的移动位置
        
        Args:
            from_pos: 起始位置
            move_range: 移动范围
            game_state: 游戏状态
            
        Returns:
            List[Tuple[int, int]]: 可能的移动位置列表
        """
        board = game_state.get('board', [])
        if not board:
            return []
        
        height = len(board)
        width = len(board[0]) if height > 0 else 0
        
        x, y = from_pos
        possible_moves = []
        
        # 生成所有在移动范围内的位置
        for dy in range(-move_range, move_range + 1):
            for dx in range(-move_range, move_range + 1):
                # 跳过当前位置
                if dx == 0 and dy == 0:
                    continue
                
                # 计算曼哈顿距离
                distance = abs(dx) + abs(dy)
                if distance > move_range:
                    continue
                
                # 计算目标位置
                to_x, to_y = x + dx, y + dy
                
                # 检查是否在棋盘范围内
                if 0 <= to_x < width and 0 <= to_y < height:
                    possible_moves.append((to_x, to_y))
        
        return possible_moves
    
    def decide_combat_action(self, combat_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        决定战斗中的行动
        
        Args:
            combat_state: 战斗状态
            
        Returns:
            Dict[str, Any]: 战斗行动
        """
        # 简单的战斗决策：总是掷采
        return {
            'action': 'roll',
            'message': 'AI掷采'
        }
    
    def decide_card_usage(self, game_state: Dict[str, Any]) -> Optional[str]:
        """
        决定是否使用卡牌
        
        Args:
            game_state: 游戏状态
            
        Returns:
            Optional[str]: 要使用的卡牌类型，如果不使用则返回None
        """
        # 简单的卡牌使用决策：随机决定是否使用卡牌
        cards = game_state.get('cards', {}).get(str(self.ai_side), {})
        
        if not cards:
            return None
        
        # 随机决定是否使用卡牌
        if random.random() < 0.3:  # 30%的概率使用卡牌
            available_cards = [card_type for card_type, count in cards.items() if count > 0]
            if available_cards:
                return random.choice(available_cards)
        
        return None


class AIStrategy:
    """
    AI策略类，提供不同的决策策略
    """
    
    @staticmethod
    def aggressive_strategy(ai_player: AIPlayer, game_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        激进策略：优先攻击敌方棋子
        
        Args:
            ai_player: AI玩家实例
            game_state: 游戏状态
            
        Returns:
            Optional[Dict[str, Any]]: 最佳移动
        """
        analysis = ai_player.analyze_board(game_state)
        ai_pieces = analysis['ai_pieces']
        enemy_pieces = analysis['enemy_pieces']
        
        if not ai_pieces or not enemy_pieces:
            return ai_player.get_best_move(game_state)
        
        best_move = None
        best_score = -float('inf')
        
        # 遍历所有AI棋子
        for piece_info in ai_pieces:
            from_pos = piece_info['pos']
            piece = piece_info['piece']
            
            # 优先考虑攻击移动
            for enemy_info in enemy_pieces:
                to_pos = enemy_info['pos']
                
                # 检查是否可以攻击
                can_attack, _ = ai_player.piece_manager.can_attack(
                    piece, from_pos, to_pos, game_state
                )
                
                if can_attack:
                    # 评估攻击价值
                    score = ai_player.evaluate_move(piece, from_pos, to_pos, game_state)
                    
                    # 如果目标是枭，大幅增加分数
                    target = enemy_info['piece']
                    if target.get('type') == 'X':
                        score += 1000.0
                    
                    if score > best_score:
                        best_score = score
                        best_move = {
                            'from_pos': from_pos,
                            'to_pos': to_pos,
                            'piece': piece,
                            'score': score
                        }
        
        # 如果没有找到攻击移动，使用默认策略
        if not best_move:
            return ai_player.get_best_move(game_state)
        
        return best_move
    
    @staticmethod
    def defensive_strategy(ai_player: AIPlayer, game_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        防守策略：优先保护枭
        
        Args:
            ai_player: AI玩家实例
            game_state: 游戏状态
            
        Returns:
            Optional[Dict[str, Any]]: 最佳移动
        """
        analysis = ai_player.analyze_board(game_state)
        ai_pieces = analysis['ai_pieces']
        
        if not ai_pieces:
            return ai_player.get_best_move(game_state)
        
        # 找到枭的位置
        xiao_pos = None
        for piece_info in ai_pieces:
            if piece_info['piece'].get('type') == 'X':
                xiao_pos = piece_info['pos']
                break
        
        if not xiao_pos:
            return ai_player.get_best_move(game_state)
        
        best_move = None
        best_score = -float('inf')
        
        # 遍历所有AI棋子（除了枭）
        for piece_info in ai_pieces:
            if piece_info['piece'].get('type') == 'X':
                continue
            
            from_pos = piece_info['pos']
            piece = piece_info['piece']
            
            # 获取棋子的移动范围
            piece_type = piece.get('type')
            piece_config = ai_player.piece_manager.get_piece_config(piece_type)
            move_range = piece_config.get('move_range', 1) if piece_config else 1
            
            # 生成所有可能的移动
            possible_moves = ai_player._generate_possible_moves(
                from_pos, move_range, game_state
            )
            
            # 评估每个可能的移动
            for to_pos in possible_moves:
                # 检查是否可以移动
                can_move, _ = ai_player.piece_manager.can_move(
                    piece, from_pos, to_pos, game_state
                )
                
                if not can_move:
                    continue
                
                # 计算与枭的距离
                distance_to_xiao = abs(to_pos[0] - xiao_pos[0]) + abs(to_pos[1] - xiao_pos[1])
                
                # 鼓励靠近枭的移动
                score = 100.0 - distance_to_xiao * 10.0
                
                # 随机性
                score += random.uniform(-5.0, 5.0)
                
                if score > best_score:
                    best_score = score
                    best_move = {
                        'from_pos': from_pos,
                        'to_pos': to_pos,
                        'piece': piece,
                        'score': score
                    }
        
        # 如果没有找到合适的移动，使用默认策略
        if not best_move:
            return ai_player.get_best_move(game_state)
        
        return best_move


def create_ai_player(piece_manager: PieceManager, difficulty: str = 'medium') -> AIPlayer:
    """
    创建AI玩家实例
    
    Args:
        piece_manager: 棋子管理器
        difficulty: 难度级别
        
    Returns:
        AIPlayer: AI玩家实例
    """
    return AIPlayer(piece_manager, difficulty)