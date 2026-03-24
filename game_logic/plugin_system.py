import os
import importlib.util
from typing import Dict, Any, List, Optional
from .piece_behavior import PieceBehavior, PieceBehaviorFactory
from .piece_manager import PieceManager


class PluginSystem:
    """
    插件系统，支持动态加载和管理棋子插件
    """
    
    def __init__(self, piece_manager: PieceManager):
        """
        初始化插件系统
        
        Args:
            piece_manager: 棋子管理器
        """
        self.piece_manager = piece_manager
        self.plugins: List[Dict[str, Any]] = []
        self.plugin_dirs: List[str] = []
    
    def add_plugin_directory(self, plugin_dir: str):
        """
        添加插件目录
        
        Args:
            plugin_dir: 插件目录路径
        """
        if os.path.exists(plugin_dir) and plugin_dir not in self.plugin_dirs:
            self.plugin_dirs.append(plugin_dir)
    
    def load_plugins(self):
        """
        加载所有插件
        """
        for plugin_dir in self.plugin_dirs:
            self._load_plugins_from_directory(plugin_dir)
    
    def _load_plugins_from_directory(self, plugin_dir: str):
        """
        从目录加载插件
        
        Args:
            plugin_dir: 插件目录路径
        """
        for file_name in os.listdir(plugin_dir):
            if file_name.endswith('.py') and not file_name.startswith('_'):
                plugin_path = os.path.join(plugin_dir, file_name)
                self._load_plugin(plugin_path)
    
    def _load_plugin(self, plugin_path: str):
        """
        加载单个插件
        
        Args:
            plugin_path: 插件文件路径
        """
        try:
            # 导入插件模块
            module_name = os.path.basename(plugin_path)[:-3]
            spec = importlib.util.spec_from_file_location(module_name, plugin_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # 检查插件是否包含必要的属性
                if hasattr(module, 'PLUGIN_INFO') and hasattr(module, 'register_plugin'):
                    plugin_info = module.PLUGIN_INFO
                    # 注册插件
                    module.register_plugin(self)
                    self.plugins.append({
                        'name': plugin_info.get('name'),
                        'version': plugin_info.get('version'),
                        'path': plugin_path
                    })
                    print(f"插件加载成功: {plugin_info.get('name')}")
        except Exception as e:
            print(f"插件加载失败: {plugin_path}, 错误: {e}")
    
    def register_piece_type(self, piece_type: str, config: Dict[str, Any]):
        """
        注册新的棋子类型
        
        Args:
            piece_type: 棋子类型
            config: 棋子配置
        """
        self.piece_manager.register_piece_type(piece_type, config)
    
    def register_behavior_type(self, behavior_type: str, behavior_class: type):
        """
        注册新的行为类型
        
        Args:
            behavior_type: 行为类型名称
            behavior_class: 行为类
        """
        PieceBehaviorFactory.register_behavior(behavior_type, behavior_class)
    
    def get_loaded_plugins(self) -> List[Dict[str, Any]]:
        """
        获取已加载的插件
        
        Returns:
            List[Dict[str, Any]]: 已加载的插件列表
        """
        return self.plugins
    
    def reload_plugins(self):
        """
        重新加载所有插件
        """
        self.plugins.clear()
        self.load_plugins()


# 插件示例结构
example_plugin = """
PLUGIN_INFO = {
    'name': '示例棋子插件',
    'version': '1.0.0',
    'description': '添加新的棋子类型'
}

from game_logic.plugin_system import PluginSystem
from game_logic.piece_behavior import PieceBehavior


class NewPieceBehavior(PieceBehavior):
    """
    新棋子行为实现
    """
    
    def can_move(self, from_pos, to_pos, game_state):
        # 实现移动逻辑
        pass
    
    def calculate_move_cost(self, from_pos, to_pos, game_state):
        # 实现移动成本计算
        pass
    
    def can_attack(self, from_pos, to_pos, game_state):
        # 实现攻击逻辑
        pass
    
    def calculate_attack_power(self, attack_value, distance, height_diff, game_state):
        # 实现攻击威力计算
        pass


def register_plugin(plugin_system: PluginSystem):
    """
    注册插件
    """
    # 注册新的行为类型
    plugin_system.register_behavior_type('new_behavior', NewPieceBehavior)
    
    # 注册新的棋子类型
    plugin_system.register_piece_type('N', {
        'name': '新棋子',
        'description': '示例新棋子',
        'move_range': 1,
        'combat_range': 2,
        'base_power': 1.2,
        'behavior_type': 'new_behavior'
    })
"""
