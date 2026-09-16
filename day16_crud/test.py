from sqlalchemy import func, select

from day15_orm import (
    Todo,
    User,
    get_engine,
    get_session_factory,
    init_models,
    masked_url,
    session_scope,
)
from day16_crud import (
    create_todo,
    create_user,
    delete_todo,
    delete_user,
    get_todo,
    get_user,
    get_user_by_username,
    list_todos,
    list_users,
    set_todo_done,
    update_user_email,
)

engine = get_engine()

stmt = select(User).where(User.username.like("%alice%"))

with session_scope(engine) as session:

    # 1️⃣ Row 元组（Core 风格）
    rows = session.execute(stmt).all()
    print(rows)

    # 2️⃣ 字典（适合 JSON / API）
    rows = session.execute(stmt).mappings().all()
    print(rows)

    # 3️⃣ ORM 对象列表（最常用）
    users = session.scalars(stmt).all()
    print(users)

    # 4️⃣ 单个 ORM 对象
    user = session.scalars(stmt).first()
    print(user)

    # 5️⃣ 强制唯一（0 条或多条都会抛异常）
    user = session.scalars(stmt).one()
    print(user)

    # 6️⃣ 单个标量值
    username = session.scalar(
        select(User.username).where(User.id == 1)
    )
    print(username)

    

with session_scope(engine) as session:
    stmt = select(User).where(User.username.like("%alice%"))

    stale_users = list[User](session.scalars(stmt).all())
    # 单个对象，无需 list()
    stale_user = session.scalars(stmt).first()
    # print(f"{stale_users}")
    # print(f"{stale_user}")

    print("=" * 74)
    print(f"{   session.execute(stmt)   }")
    print(f"{   session.execute(stmt).all()   }")
    print(f"{   session.execute(stmt).first()   }")
    print("=" * 74)
    print(f"{   session.execute(stmt).mappings()   }")
    print(f"{   session.execute(stmt).mappings().all()   }")
    print(f"{   session.execute(stmt).mappings().first()   }")
    print("=" * 74)
    print(f"{   session.execute(stmt).scalars()   }")
    print(f"{   session.execute(stmt).scalars().all()   }")
    print(f"{   session.execute(stmt).scalars().first()   }")
    print("=" * 74)
    print(f"{   session.scalar(stmt)   }")
    print("=" * 74)
    print(f"{   session.scalars(stmt)   }")
    print(f"{   session.scalars(stmt).all()   }")
    print(f"{   session.scalars(stmt).first()   }")
    print(f"{   list[User](session.scalars(stmt).all())   }")
    print(f"{   session.scalars(stmt).one()   }")



def execute():
    with session_scope(engine) as session:
        return session.execute(stmt)

def scalars():
    with session_scope(engine) as session:
        return session.scalars(stmt)

def scalar():
    with session_scope(engine) as session:
        return session.scalar(stmt)
    


print("=" * 74)
print(f"{   scalar()   }")
print(f"{   scalars()   }")
print(f"{   execute()   }")
