from sqlalchemy_config import SessionFactory
from sqlalchemy_model import User  # 导入Model模型
with SessionFactory() as session:
    # 创建User实例（相当于创建一条数据）
    user1 = User(username="lisi2", password="123456")
    user2 = User(username="wangwu2", password="654321")
    # 1. 将实例添加到Session（相当于“暂存”数据，未提交到数据库）
    session.add(user1)
    session.add(user2)
    # 提交事务（将暂存的数据提交到数据库，此时才会真正插入数据）
    session.commit()
    # 2. 批量添加（可选）
    session.add_all([user1, user2])
    session.commit()
    # 3. 批量字典添加
    # 准备字典列表，不用创建User对象
    user_dicts = [
        {"username": "sunqi", "password": "123123"},
        {"username": "zhouba", "password": "456456"},
        {"username": "wujiu", "password": "789789"},
    ]
    # 4. 批量插入
    session.bulk_insert_mappings(User, user_dicts)
    session.commit()
    # 5. sqlalchemy2.0语法
    from sqlalchemy import insert
    # 构建insert语句
    stmt = insert(User).values([
        {"username": "zhengshi", "password": "aaa"},
        {"username": "chenshi", "password": "bbb"},
    ])
    # 执行语句
    session.execute(stmt)
    session.commit()
