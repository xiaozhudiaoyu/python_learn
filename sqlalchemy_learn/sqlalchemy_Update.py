from sqlalchemy_config import SessionFactory
from sqlalchemy_model import User  # 导入Model模型

with SessionFactory() as session:
    # 1. 单条数据更新
    user = session.query(User).filter(User.username == "zhangsan").first()
    if user:
        user.password = "new_password123"  # 修改密码（对应 UPDATE user SET password = 'new_password123'）
        session.commit()  # 提交更新
        print(f'{user=}')

    # 2. 批量更新（高效，对应 MySQL 的 UPDATE ... WHERE ...）
    # 将所有用户名以 "w" 开头的用户密码更新为 "common_password"
    session.query(User).filter(User.username.like("w%")).update({"password": "common_password"})
    session.commit()

    # 3. sqlalchemy2.0语法
    from sqlalchemy import update

    # 构建 update 语句
    stmt = update(User).where(User.username.like("w%")).values(
        password='sqlalchemy2.0_password'
    )
    # 执行语句
    session.execute(stmt)
    session.commit()