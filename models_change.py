# 连接到数据库并执行更新
import sqlite3

# 数据库文件路径
db_path = 'instance/game_data.db'

# 连接到SQLite数据库
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 添加map_id列（如果尚不存在）
try:
    cursor.execute('ALTER TABLE combat_log ADD COLUMN map_id INTEGER DEFAULT 1')
    print("成功添加 map_id 列")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("map_id 列已存在，跳过")
    else:
        print(f"添加 map_id 列时出错: {e}")

# 添加player2_streak列（如果尚不存在）
try:
    cursor.execute('ALTER TABLE game_room ADD COLUMN player2_streak INTEGER DEFAULT 0')
    print("成功添加 player2_streak 列")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("player2_streak 列已存在，跳过")
    else:
        print(f"添加 player2_streak 列时出错: {e}")

# 添加player1_streak列（如果尚不存在）
try:
    cursor.execute('ALTER TABLE game_room ADD COLUMN player1_streak INTEGER DEFAULT 0')
    print("成功添加 player1_streak 列")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("player1_streak 列已存在，跳过")
    else:
        print(f"添加 player1_streak 列时出错: {e}")

# 添加combat_sequence列（战斗顺序ID）
try:
    cursor.execute('ALTER TABLE combat_log ADD COLUMN combat_sequence INTEGER DEFAULT 1')
    print("成功添加 combat_sequence 列")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("combat_sequence 列已存在，跳过")
    else:
        print(f"添加 combat_sequence 列时出错: {e}")

# 添加attacker_piece列（进攻方棋子类型）
try:
    cursor.execute('ALTER TABLE combat_log ADD COLUMN attacker_piece VARCHAR(10) DEFAULT "Unknown"')
    print("成功添加 attacker_piece 列")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("attacker_piece 列已存在，跳过")
    else:
        print(f"添加 attacker_piece 列时出错: {e}")

# 添加defender_piece列（防守方棋子类型）
try:
    cursor.execute('ALTER TABLE combat_log ADD COLUMN defender_piece VARCHAR(10) DEFAULT "Unknown"')
    print("成功添加 defender_piece 列")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("defender_piece 列已存在，跳过")
    else:
        print(f"添加 defender_piece 列时出错: {e}")

# 添加attacker_card列（进攻方锦囊牌）
try:
    cursor.execute('ALTER TABLE combat_log ADD COLUMN attacker_card VARCHAR(20)')
    print("成功添加 attacker_card 列")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("attacker_card 列已存在，跳过")
    else:
        print(f"添加 attacker_card 列时出错: {e}")

# 添加attack_coop列（攻击连携倍率）
try:
    cursor.execute('ALTER TABLE Terrain ADD COLUMN picture_url VARCHAR(20)')
    print("成功添加 picture_url 列")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("picture_url 列已存在，跳过")
    else:
        print(f"添加 picture_url 列时出错: {e}")

# 修改piece表的move_cost列为浮点数类型
# 检查piece表是否存在
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='piece';")
piece_table_exists = cursor.fetchone() is not None

if piece_table_exists:
    # 表存在，需要先备份数据、重建表并迁移数据
    # 1. 先删除已存在的备份表
    cursor.execute("DROP TABLE IF EXISTS piece_backup;")
    # 2. 备份原表数据
    cursor.execute("CREATE TABLE piece_backup AS SELECT * FROM piece;")
    
    # 3. 删除原表
    cursor.execute("DROP TABLE piece;")
    
    # 4. 重建表，将 move_cost 改为 FLOAT，并添加其他必要的列
    cursor.execute("""
    CREATE TABLE piece (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        piece_id VARCHAR(50) UNIQUE NOT NULL,
        name VARCHAR(100) NOT NULL,
        description TEXT,
        move_range INTEGER DEFAULT 1,
        combat_range INTEGER DEFAULT 1,
        move_cost FLOAT DEFAULT 1.0,
        base_power FLOAT DEFAULT 1.0,
        defense_power FLOAT DEFAULT 1.0,
        attack_coop FLOAT DEFAULT 1.0,
        defense_coop FLOAT DEFAULT 1.0,
        coop_range INTEGER DEFAULT 1,
        attack_type VARCHAR(20) DEFAULT 'melee',
        piece_picture VARCHAR(20),
        terrain_change BOOLEAN DEFAULT 0
    );
    """)
    
    # 5. 将备份数据迁移回新表
    cursor.execute("""
    INSERT INTO piece (id, piece_id, name, description, move_range, combat_range, move_cost, base_power, defense_power, attack_coop, defense_coop, coop_range, attack_type, piece_picture, terrain_change)
    SELECT 
        id, 
        COALESCE(piece_id, 'unknown'), 
        name, 
        COALESCE(description, ''), 
        COALESCE(move_range, 1), 
        COALESCE(combat_range, 1), 
        COALESCE(move_cost, 1.0), 
        COALESCE(base_power, 1.0), 
        COALESCE(defense_power, 1.0), 
        COALESCE(attack_coop, 1.0), 
        COALESCE(defense_coop, 1.0), 
        COALESCE(coop_range, 1), 
        COALESCE(attack_type, 'melee'), 
        COALESCE(piece_picture, ''), 
        COALESCE(terrain_change, 0)
    FROM piece_backup;
    """)
    
    # 6. 删除备份表
    cursor.execute("DROP TABLE piece_backup;")
    
    print("已将 piece 表的 move_cost 列类型修改为 FLOAT，并更新了表结构")
else:
    # 表不存在，直接创建新表
    cursor.execute("""
    CREATE TABLE piece (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        piece_id VARCHAR(50) UNIQUE NOT NULL,
        name VARCHAR(100) NOT NULL,
        description TEXT,
        move_range INTEGER DEFAULT 1,
        combat_range INTEGER DEFAULT 1,
        move_cost FLOAT DEFAULT 1.0,
        base_power FLOAT DEFAULT 1.0,
        defense_power FLOAT DEFAULT 1.0,
        attack_coop FLOAT DEFAULT 1.0,
        defense_coop FLOAT DEFAULT 1.0,
        coop_range INTEGER DEFAULT 1,
        attack_type VARCHAR(20) DEFAULT 'melee',
        piece_picture VARCHAR(20),
        terrain_change BOOLEAN DEFAULT 0
    );
    """)
    
    print("已创建 piece 表，move_cost 列类型为 FLOAT")
    
    # 添加默认棋子数据
    default_pieces = [
        ('X', '枭', '最高统帅，移动范围小但攻击力强', 1, 1, 1.0, 2.0, 2.0, 1.5, 1.5, 1, 'melee', '', 0),
        ('T', '矢', '远程攻击单位，移动范围中等', 2, 3, 1.0, 1.2, 0.8, 1.2, 0.8, 1, 'ranged', '', 0),
        ('S', '散', '基础步兵单位，移动范围和攻击力均衡', 1, 1, 1.0, 1.0, 1.0, 1.0, 1.0, 1, 'melee', '', 0),
        ('G', '工', '可以调整地形高度的单位', 1, 1, 1.0, 0.8, 0.8, 1.0, 1.0, 1, 'melee', '', 1),
        ('P', '炮', '可以远程攻击的单位', 1, 3, 1.0, 1.5, 0.9, 1.3, 0.9, 1, 'ranged', '', 0)
    ]
    
    cursor.executemany("""
    INSERT INTO piece (piece_id, name, description, move_range, combat_range, move_cost, base_power, defense_power, attack_coop, defense_coop, coop_range, attack_type, piece_picture, terrain_change)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, default_pieces)
    
    print("已添加默认棋子数据")

# 提交更改
conn.commit()

# 关闭连接
conn.close()

print("\n数据库表结构更新完成！")
