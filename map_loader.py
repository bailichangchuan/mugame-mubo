import json
import os
from extensions import db
from models import Map

class MapLoader:
    """
    地图加载器类，用于读取和解析地图数据
    """
    
    @staticmethod
    def load_map(map_name="default_map"):
        """
        加载指定名称的地图
        
        Args:
            map_name (str): 地图名称
            
        Returns:
            dict: 解析后的地图数据
            
        Raises:
            FileNotFoundError: 地图不存在
            ValueError: 地图数据格式错误
        """
        from models import Piece
        
        # 首先尝试从数据库加载
        map_obj = Map.query.filter_by(name=map_name).first()
        
        if map_obj:
            map_data = map_obj.get_data()
            
            # 从数据库加载最新的棋子类型数据
            piece_types = {}
            pieces = Piece.query.all()
            for piece in pieces:
                piece_types[piece.piece_id] = {
                    "name": piece.name,
                    "description": piece.description,
                    "move_range": piece.move_range,
                    "combat_range": piece.combat_range,
                    "base_power": piece.base_power,
                    "attack_type": piece.attack_type,
                    "move_cost": piece.move_cost,
                    "defense_power": piece.defense_power,
                    "attack_coop": piece.attack_coop,
                    "defense_coop": piece.defense_coop,
                    "coop_range": piece.coop_range,
                    "piece_picture": piece.piece_picture,
                    "terrain_change": piece.terrain_change
                }
            
            # 更新地图数据中的棋子类型
            map_data['piece_types'] = piece_types
            
            # 验证地图数据格式
            MapLoader._validate_map_data(map_data)
            return map_data
        
        # 如果数据库中不存在，尝试从文件系统加载
        map_path = os.path.join('maps', f'{map_name}.json')
        
        if not os.path.exists(map_path):
            raise FileNotFoundError(f"地图不存在: {map_name}")
        
        with open(map_path, 'r', encoding='utf-8') as f:
            map_data = json.load(f)
        
        # 从数据库加载最新的棋子类型数据
        piece_types = {}
        pieces = Piece.query.all()
        for piece in pieces:
            piece_types[piece.piece_id] = {
                "name": piece.name,
                "description": piece.description,
                "move_range": piece.move_range,
                "combat_range": piece.combat_range,
                "base_power": piece.base_power,
                "attack_type": piece.attack_type,
                "move_cost": piece.move_cost,
                "defense_power": piece.defense_power,
                "attack_coop": piece.attack_coop,
                "defense_coop": piece.defense_coop,
                "coop_range": piece.coop_range,
                "piece_picture": piece.piece_picture,
                "terrain_change": piece.terrain_change
            }
        
        # 更新地图数据中的棋子类型
        map_data['piece_types'] = piece_types
        
        # 验证地图数据格式
        MapLoader._validate_map_data(map_data)
        
        # 将文件系统中的地图导入到数据库
        MapLoader.import_map_from_file(map_name, map_data)
        
        return map_data
    
    @staticmethod
    def _validate_map_data(map_data):
        """
        验证地图数据格式是否正确
        
        Args:
            map_data (dict): 地图数据
            
        Raises:
            ValueError: 地图数据格式错误
        """
        required_fields = ['map_info', 'terrain_types', 'piece_types', 'terrain', 'initial_pieces']
        
        for field in required_fields:
            if field not in map_data:
                raise ValueError(f"地图数据缺少必要字段: {field}")
        
        # 验证地图尺寸
        width = map_data['map_info'].get('width')
        height = map_data['map_info'].get('height')
        
        if not (isinstance(width, int) and isinstance(height, int)):
            raise ValueError("地图尺寸必须为整数")
        
        if width <= 0 or height <= 0:
            raise ValueError("地图尺寸必须为正数")
        
        # 验证地形数据
        terrain_type = map_data['terrain'].get('type')
        if not isinstance(terrain_type, list):
            raise ValueError("地形类型数据必须为列表")
        
        if len(terrain_type) != height:
            raise ValueError(f"地形行数必须等于地图高度 ({height})")
        
        for row in terrain_type:
            if not isinstance(row, list) or len(row) != width:
                raise ValueError(f"每行地形数据长度必须等于地图宽度 ({width})")
        
        # 验证初始棋子数据
        initial_pieces = map_data['initial_pieces']
        if not isinstance(initial_pieces, dict):
            raise ValueError("初始棋子数据必须为字典")
        
        # 验证红黑双方棋子
        for side in ['R', 'B']:
            if side not in initial_pieces:
                raise ValueError(f"缺少{side}方初始棋子数据")
            
            if not isinstance(initial_pieces[side], list):
                raise ValueError(f"{side}方初始棋子数据必须为列表")
    
    @staticmethod
    def get_available_maps():
        """
        获取所有可用的地图列表
        
        Returns:
            list: 地图名称列表
        """
        # 从数据库获取地图列表
        maps = Map.query.all()
        available_maps = []
        
        for map_obj in maps:
            available_maps.append(map_obj.name)
        
        # 如果数据库中没有地图，尝试从文件系统加载
        if not available_maps:
            maps_dir = 'maps'
            if os.path.exists(maps_dir):
                for file_name in os.listdir(maps_dir):
                    if file_name.endswith('.json'):
                        map_name = file_name[:-5]  # 移除.json扩展名
                        available_maps.append(map_name)
                        # 导入到数据库
                        try:
                            map_path = os.path.join('maps', file_name)
                            with open(map_path, 'r', encoding='utf-8') as f:
                                map_data = json.load(f)
                            MapLoader.import_map_from_file(map_name, map_data)
                        except Exception as e:
                            print(f"导入地图 {map_name} 失败: {e}")
        
        return available_maps
    
    @staticmethod
    def create_empty_map(width=8, height=8, name="new_map"):
        """
        创建一个空的地图模板
        
        Args:
            width (int): 地图宽度
            height (int): 地图高度
            name (str): 地图名称
            
        Returns:
            dict: 空地图数据
        """
        from models import Terrain, Piece
        
        # 从数据库加载地形类型
        terrain_types = {}
        terrains = Terrain.query.all()
        for terrain in terrains:
            terrain_types[terrain.terrain_id] = {
                "name": terrain.name,
                "description": terrain.description,
                "passability": terrain.passability,
                "move_cost": terrain.move_cost,
                "combat_bonus": terrain.combat_bonus,
                "color": terrain.color
            }
        
        # 从数据库加载棋子类型
        piece_types = {}
        pieces = Piece.query.all()
        for piece in pieces:
            piece_types[piece.piece_id] = {
                "name": piece.name,
                "description": piece.description,
                "move_range": piece.move_range,
                "combat_range": piece.combat_range,
                "base_power": piece.base_power,
                "attack_type": piece.attack_type,
                "move_cost": piece.move_cost,
                "defense_power": piece.defense_power,
                "attack_coop": piece.attack_coop,
                "defense_coop": piece.defense_coop,
                "coop_range": piece.coop_range,
                "piece_picture": piece.piece_picture,
                "terrain_change": piece.terrain_change
            }
        
        # 确保至少有一个地形类型
        if not terrain_types:
            terrain_types["plain"] = {
                "name": "平原",
                "passability": 1,
                "move_cost": 1,
                "combat_bonus": 1.0
            }
        
        # 确保至少有一个棋子类型
        if not piece_types:
            piece_types["S"] = {
                "name": "散兵",
                "description": "基础步兵单位",
                "move_range": 1,
                "combat_range": 1,
                "base_power": 1.0
            }
        
        empty_map = {
            "map_info": {
                "name": name,
                "description": f"{width}x{height}空白战场",
                "width": width,
                "height": height
            },
            "terrain_types": terrain_types,
            "piece_types": piece_types,
            "terrain": {
                "type": [["plain" for _ in range(width)] for _ in range(height)],
                "height": [[0 for _ in range(width)] for _ in range(height)]
            },
            "initial_pieces": {
                "R": [],
                "B": []
            }
        }
        
        return empty_map
    
    @staticmethod
    def save_map(map_data, map_name, created_by=None):
        """
        保存地图数据到数据库
        
        Args:
            map_data (dict): 地图数据
            map_name (str): 地图名称
            created_by (int): 创建者ID
        """
        # 验证地图数据
        MapLoader._validate_map_data(map_data)
        
        # 检查地图是否已存在
        map_obj = Map.query.filter_by(name=map_name).first()
        
        if map_obj:
            # 更新现有地图
            map_obj.display_name = map_data['map_info']['name']
            map_obj.description = map_data['map_info']['description']
            map_obj.width = map_data['map_info']['width']
            map_obj.height = map_data['map_info']['height']
            map_obj.set_data(map_data)
            if created_by:
                map_obj.created_by = created_by
        else:
            # 创建新地图
            map_obj = Map(
                name=map_name,
                display_name=map_data['map_info']['name'],
                description=map_data['map_info']['description'],
                width=map_data['map_info']['width'],
                height=map_data['map_info']['height'],
                created_by=created_by
            )
            map_obj.set_data(map_data)
            db.session.add(map_obj)
        
        db.session.commit()
    
    @staticmethod
    def import_map_from_file(map_name, map_data, created_by=None):
        """
        从文件导入地图到数据库
        
        Args:
            map_name (str): 地图名称
            map_data (dict): 地图数据
            created_by (int): 创建者ID
        """
        # 检查地图是否已存在
        existing_map = Map.query.filter_by(name=map_name).first()
        if existing_map:
            return  # 地图已存在，跳过导入
        
        # 创建新地图
        map_obj = Map(
            name=map_name,
            display_name=map_data['map_info']['name'],
            description=map_data['map_info']['description'],
            width=map_data['map_info']['width'],
            height=map_data['map_info']['height'],
            created_by=created_by
        )
        map_obj.set_data(map_data)
        db.session.add(map_obj)
        db.session.commit()
    
    @staticmethod
    def get_map_by_id(map_id):
        """
        根据ID获取地图
        
        Args:
            map_id (int): 地图ID
            
        Returns:
            dict: 地图数据
        """
        map_obj = Map.query.get(map_id)
        if not map_obj:
            raise FileNotFoundError(f"地图不存在: ID={map_id}")
        
        return map_obj.get_data()
    
    @staticmethod
    def get_map_object(map_name):
        """
        根据名称获取地图对象
        
        Args:
            map_name (str): 地图名称
            
        Returns:
            Map: 地图对象
        """
        return Map.query.filter_by(name=map_name).first()

class MapData:
    """
    地图数据类，提供对地图数据的便捷访问
    """
    
    def __init__(self, map_data):
        self._map_data = map_data
        self._map_info = map_data['map_info']
        self._terrain_types = map_data['terrain_types']
        self._piece_types = map_data['piece_types']
        self._terrain = map_data['terrain']
        self._initial_pieces = map_data['initial_pieces']
    
    @property
    def name(self):
        return self._map_info['name']
    
    @property
    def description(self):
        return self._map_info['description']
    
    @property
    def width(self):
        return self._map_info['width']
    
    @property
    def height(self):
        return self._map_info['height']
    
    def get_terrain_at(self, x, y):
        """
        获取指定位置的地形类型
        
        Args:
            x (int): 横坐标
            y (int): 纵坐标
            
        Returns:
            str: 地形类型
        """
        if 0 <= y < self.height and 0 <= x < self.width:
            return self._terrain['type'][y][x]
        return None
    
    def get_terrain_info(self, terrain_type):
        """
        获取地形类型的详细信息
        
        Args:
            terrain_type (str): 地形类型
            
        Returns:
            dict: 地形信息
        """
        return self._terrain_types.get(terrain_type, {})
    
    def get_piece_info(self, piece_type):
        """
        获取棋子类型的详细信息
        
        Args:
            piece_type (str): 棋子类型
            
        Returns:
            dict: 棋子信息
        """
        return self._piece_types.get(piece_type, {})
    
    def get_initial_pieces(self, side):
        """
        获取指定方的初始棋子
        
        Args:
            side (str): 阵营，'R'或'B'
            
        Returns:
            list: 初始棋子列表
        """
        return self._initial_pieces.get(side, [])
    
    def is_passable(self, x, y):
        """
        检查指定位置是否可通行
        
        Args:
            x (int): 横坐标
            y (int): 纵坐标
            
        Returns:
            bool: 是否可通行
        """
        terrain_type = self.get_terrain_at(x, y)
        if not terrain_type:
            return False
        
        terrain_info = self.get_terrain_info(terrain_type)
        return terrain_info.get('passability', 0) == 1
    
    def get_move_cost(self, x, y):
        """
        获取指定位置的移动成本
        
        Args:
            x (int): 横坐标
            y (int): 纵坐标
            
        Returns:
            int: 移动成本
        """
        terrain_type = self.get_terrain_at(x, y)
        if not terrain_type:
            return 999
        
        terrain_info = self.get_terrain_info(terrain_type)
        return terrain_info.get('move_cost', 1)
    
    def get_combat_bonus(self, x, y):
        """
        获取指定位置的战斗加成
        
        Args:
            x (int): 横坐标
            y (int): 纵坐标
            
        Returns:
            float: 战斗加成系数
        """
        terrain_type = self.get_terrain_at(x, y)
        if not terrain_type:
            return 1.0
        
        terrain_info = self.get_terrain_info(terrain_type)
        return terrain_info.get('combat_bonus', 1.0)