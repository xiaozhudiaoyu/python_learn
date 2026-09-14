from sqlalchemy_config import SessionFactory
from sqlalchemy_model import User #导入Model模型
from sqlalchemy import delete
with SessionFactory() as session:
    # 1. 单条数据删除
    user = session.query(User).filter(User.username == "wangwu").first()
    if user:
        session.delete(user)  # 对应 DELETE FROM user WHERE username = 'wangwu'
        session.commit()
 
    # 2. 批量删除（对应 MySQL 的 DELETE ... WHERE ...）
    # 删除所有 id > 3 的用户
    session.query(User).filter(User.id > 3).delete()
    session.commit()
    # 3. sqlalchemy2.0语法
    from sqlalchemy import delete
    # 构建 delete 语句
    stmt = delete(User).where(User.id > 18)
    # 执行语句
    session.execute(stmt)
    session.commit()