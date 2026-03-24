import sqlite3

# 连接到SQLite数据库
db_path = 'instance/game_data.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 检查piece表的结构
print("=== piece表结构 ===")
cursor.execute("PRAGMA table_info(piece);")
columns = cursor.fetchall()
for column in columns:
    print(f"{column[1]}: {column[2]}")

# 检查piece表中的数据
print("\n=== piece表数据 ===")
cursor.execute("SELECT piece_id, name, move_cost FROM piece;")
data = cursor.fetchall()
for row in data:
    print(f"{row[0]} - {row[1]}: {row[2]} (类型: {type(row[2])})")

# 尝试插入一个带有浮点数move_cost的记录
print("\n=== 测试插入浮点数 ===")
try:
    cursor.execute("INSERT INTO piece (piece_id, name, move_cost) VALUES (?, ?, ?)", ('TEST', '测试棋子', 0.5))
    conn.commit()
    print("插入成功")
    
    # 检查插入的数据
    cursor.execute("SELECT piece_id, name, move_cost FROM piece WHERE piece_id = 'TEST';")
    test_data = cursor.fetchone()
    print(f"测试数据: {test_data[0]} - {test_data[1]}: {test_data[2]} (类型: {type(test_data[2])})")
    
    # 删除测试数据
    cursor.execute("DELETE FROM piece WHERE piece_id = 'TEST';")
    conn.commit()
except Exception as e:
    print(f"插入失败: {e}")

# 关闭连接
conn.close()
