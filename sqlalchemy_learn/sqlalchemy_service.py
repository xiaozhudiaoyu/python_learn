from sqlalchemy_config import SessionFactory
from sqlalchemy_model import User  # 导入Model模型

##基础查询
with SessionFactory() as session:
    # 1. 查询所有数据（返回列表，对应 MySQL 的 SELECT * FROM user）
    all_users = session.query(User).all()
    for user in all_users:
        print("=" * 74)
        print(user)

    # 2. 查询单条数据（根据主键，对应 MySQL 的 SELECT * FROM user WHERE id = 1，不存在则返回None）
    user_by_id = session.get(User, 9)  # 1 是 id 值
    print("=" * 74)
    print(f'{user_by_id=}')

    # 3. 查询单条数据（不存在则返回 None，对应 MySQL 的 SELECT * FROM user  LIMIT 1）
    user_by_name = session.query(User).first()
    print("=" * 74)
    print(f'{user_by_name=}')

    # 4. 查指定字段数据
    # 默认.query(User)会查询User的所有字段 可以使用User.字段控制查询字段
    all_users = session.query(User.id, User.username, User.create_time).all()
    for user in all_users:
        print("=" * 74)
        print(user)


##条件查询
with SessionFactory() as session:
    # 1. 等于（==），对应 MySQL 的 WHERE username = 'zhangsan'
    user1 = session.query(User).filter(User.username == "zhangsan").first()
    print("=" * 74)
    print(f'{user1=}')
    # 2. 不等于（!=），对应 MySQL 的 WHERE username != 'zhangsan'
    user2 = session.query(User).filter(User.username != "zhangsan").all()
    print("=" * 74)
    print(f'{user2=}')
    # 3. 模糊查询（like），对应 MySQL 的 WHERE username LIKE '%a%'
    user3 = session.query(User).filter(User.username.like("%a%")).all()
    print("=" * 74)
    print(f'{user3=}')
    # 4. 范围查询（in_），对应 MySQL 的 WHERE id IN (1,2,3)
    user4 = session.query(User).filter(User.id.in_([1, 2, 3])).all()
    print("=" * 74)
    print(f'{user4=}')
    # 5. 大于（>）、小于（<）、大于等于（>=）、小于等于（<=）
    user5 = session.query(User).filter(User.id > 2).all()  # 对应 WHERE id > 2
    print("=" * 74)
    print(f'{user5=}')
    # 6. 多条件查询（and_ / or_），对应 MySQL 的 AND / OR
    from sqlalchemy import and_, or_

    # 对应 WHERE id > 1 AND username LIKE 'w%'
    user6 = session.query(User).filter(and_(User.id > 1, User.username.like("w%"))).first()
    print("=" * 74)
    print(f'{user6=}')
    # 对应 WHERE username='zhangsan' AND password='123456'
    user7 = session.query(User).filter_by(username='zhangsan', password='123456').first()
    print("=" * 74)
    print(f'{user7=}')
    # 对应 WHERE id = 1 OR username LIKE 'w%'
    user8 = session.query(User).filter(or_(User.id == 1, User.username.like("w%"))).all()
    print("=" * 74)
    print(f'{user8=}')


##排序、分页查询
with SessionFactory() as session:
    # 1. 排序（order_by）：对应 MySQL 的 ORDER BY
    users_asc = session.query(User).order_by(User.id).all()  # 按 id 升序（默认），对应 ORDER BY id ASC
    users_desc = session.query(User).order_by(User.id.desc()).all()  # 按 id 降序，对应 ORDER BY id DESC
    print("=" * 74)
    print(f'{users_asc=}')
    print(f'{users_desc=}')
    # 2. 分页（limit + offset）：对应 MySQL 的 LIMIT 和 OFFSET，适合分页查询
    page = 2  # 第 2 页
    page_size = 2  # 每页 2 条数据
    # 对应 SELECT * FROM user ORDER BY id LIMIT 2 OFFSET 2
    users_page = session.query(User).order_by(User.id).limit(page_size).offset((page - 1) * page_size).all()
    print("=" * 74)
    print(f'{users_page=}')
    # 3. 统计数量（count）：对应 MySQL 的 COUNT(*)
    user_count = session.query(User).filter(User.username.like("%u%")).count()
    print("=" * 74)
    print(f"{user_count=}")


##分组查询
# func 是数据库聚合函数的入口，它属于 sqlalchemy 本身，不在 sqlalchemy_config 里
from sqlalchemy import func, select
from sqlalchemy_model import Account
with SessionFactory() as session:
    # 1.简单分组查询
    # 因为聚合函数是数据库提供的函数 所以需要导入func
    # 默认query(Account)查询所有列 聚合查询只能查询分组列与聚合函数所以
    # 所以需要查询指定列
    group1 = session.query(Account.age, func.count(Account.id)).group_by(Account.age).all()
    print("=" * 74)
    print(group1)
    # 聚合比较特殊 不会返回对应的对象 所以默认以元组返回
    # 如果想以字典形式返回需要使用新版2.0 API然后使用.mappings()
    stmt = select(
        Account.age,
        func.count(Account.id).label("count")
    ).group_by(Account.age)
    group2 = session.execute(stmt).mappings().all()
    print("=" * 74)
    print(group2)

    # 2.having分组筛选
    # 可以直接使用having()进行分组的筛选
    group3 = session.query(Account.age, func.count(Account.id)).group_by(Account.age).having(
        func.count(Account.id) > 1).all()
    print("=" * 74)
    print(group3)
    stmt = select(
        Account.age,
        func.count(Account.id).label("count")
    ).group_by(Account.age).having(func.count(Account.id) > 1)
    group4 = session.execute(stmt).mappings().all()
    print("=" * 74)
    print(group4)