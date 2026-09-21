# 模块：DAO（Data Access Object，数据访问对象）—— Day 16 · CRUD + Session 生命周期。
#
# DAO 是一层"把数据库读写包起来"的函数集合。业务代码只调 create_user / list_todos
# 这些语义明确的函数，不必自己写 select()、session.add()、session.commit()。
# 好处和 Day 15 把连接串收进 db_config.py 是一个道理：把"怎么存"关进一个抽屉，
# 将来改存储细节（换查询方式、加缓存）只动这一层，调用方一行都不用改。
#
# ── 本层最重要的一条设计约定：DAO 函数【接收 Session，但绝不 commit】──────────
#   为什么不在每个函数里 commit？因为那样一来，"改邮箱 + 加一条待办"就被切成
#   两个各自独立提交的事务，中途出错会留下"改了一半"的脏数据。
#   正确做法是：事务边界由【调用方】掌握 —— 调用方用 Day 15 的 session_scope
#   开一个事务，在里面连着调好几个 DAO 函数，最后由 session_scope 统一 commit
#   或（出错时）rollback。要么全成、要么全不成，这就是"事务边界理解"的落点。
#
#   一句话：DAO 负责"在事务里干活"，session_scope 负责"何时收工（提交/回滚）"。
#
# ── 关于 flush ────────────────────────────────────────────────────────────
#   新增类函数里会调 session.flush()：它把 INSERT 发给数据库、拿回自增 id，
#   但【不提交】事务。这正是 models.py 第 62 行埋的伏笔——id 由数据库生成，
#   flush 之后才读得到。flush 只保证"这个事务内"能拿到 id 和看到改动，
#   别的连接要等到 commit 才看得见（Day 16 demo 第 7 段专门验证这一点）。

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

# 模型与会话工厂都来自 Day 15 的包：Day 16 只在它之上加数据访问层，
# 不重新定义 User / Todo（Day 17 还要给同一批模型加外键，模型只此一份）。
from day15_orm import Todo, User

# ─────────────────────────────────────────────────────────────────────────
# User 的 CRUD
# ─────────────────────────────────────────────────────────────────────────


def create_user(session: Session, username: str, email: str | None = None) -> User:
    """新增一个用户，返回【已拿到自增 id】的 User 对象。不 commit。

    email 默认 None：对应 models.py 里 Mapped[str | None] 的可空列，
    不传就是 NULL，和 Day 15 demo 第 7a 段的行为一致。
    """
    user = User(username=username, email=email)
    session.add(user)          # add 只是把对象交给 session 托管，此刻还没发 SQL
    session.flush()            # flush 才真正发 INSERT，并把数据库生成的 id 回填到 user.id
    return user


def get_user(session: Session, user_id: int) -> User | None:
    """按主键查单个用户；查不到返回 None。

    用 session.get() 而不是 select().where(id==...)：get 是主键专用捷径，
    它先查 session 的身份映射（identity map）——同一个事务里已经加载过的对象
    直接返回缓存、连 SQL 都不发；没命中才发 SELECT ... WHERE id = ?。
    """
    return session.get(User, user_id)


def get_user_by_username(session: Session, username: str) -> User | None:
    """按唯一列 username 查单个用户；查不到返回 None。

    username 上有唯一索引（Day 15 建的），所以最多一条，用 first() 取即可。
    session.scalars(stmt) 把结果的每一行取第 0 列（这里就是 User 对象本身），
    比 session.execute(stmt).scalars() 少写一层，是 2.0 查 ORM 对象的常用入口。
    """
    stmt = select(User).where(User.username == username)
    return session.scalars(stmt).first()


def list_users(session: Session, limit: int | None = None) -> list[User]:
    """列出用户，按 id 升序（保证每次顺序稳定，方便断言与查看）。

    Day 20 新增可选 limit：传整数则只取前 N 条（SQL LIMIT 子句），
    传 None（默认）列全部。默认值 None 保证既有调用 list_users(session)
    不受影响（run_day16_demo.py / day16_crud/test.py 都是单参数调用）。
    limit 下推到 SQL 而不是查全表再切片，数据量大时才不会白白捞一堆行。
    """
    stmt = select(User).order_by(User.id)
    if limit is not None:
        stmt = stmt.limit(limit)
    # .all() 返回的是 Sequence，包一层 list() 得到确定的 list[User]，对类型检查器更友好。
    return list(session.scalars(stmt).all())


def update_user_email(session: Session, user_id: int, email: str | None) -> User | None:
    """改用户邮箱，返回改后的对象；用户不存在返回 None。不 commit。

    ORM 的"改"就是这么朴素：拿到被 session 跟踪的对象，直接改它的属性。
    session 内部记着"这个对象脏了"，等 flush / commit 时自动算出差异、生成
    UPDATE users SET email=? WHERE id=?。你不用手写 UPDATE，也不用告诉它改了哪列。
    同样的套路适用于任何字段——这里只挑 email 做示范。
    """
    user = session.get(User, user_id)
    if user is None:
        return None
    user.email = email
    session.flush()            # 让 UPDATE 立刻发出（也可留到 commit 时再发，这里为看清时序）
    return user


# ── Day 20 新增：用户通用字段更新 ─────────────────────────────────
# update_user_email 只能改 email 一列，接口层的 PATCH 需要"传什么改什么"，
# 所以补一个通用版，与 Day 19 的 update_todo 同一套路、同一约定：
#   · 接收 Session、不 commit（事务边界归调用方）；
#   · 不存在返回 None，让 service 层翻译成 404；
#   · fields 来自 Pydantic model_dump(exclude_unset=True)，合法性已在上层校验。
# username 的唯一性由 service 层提前检查（409），数据库唯一索引兜底。
def update_user(session: Session, user_id: int, fields: dict[str, Any]) -> User | None:
    """按 id 更新用户任意字段：改成功返回对象，不存在返回 None。不 commit。"""
    user = session.get(User, user_id)
    if user is None:
        return None
    for key, value in fields.items():
        setattr(user, key, value)
    session.flush()
    return user


def delete_user(session: Session, user_id: int) -> bool:
    """按 id 删用户：删掉返回 True，本来就不存在返回 False。不 commit。

    返回 bool 而不是对象，是因为删除成功后对象即将失效，把它交出去容易被误用。
    "不存在返回 False"是一种幂等设计：重复删同一个 id 不会报错，调用方据返回值判断即可。
    """
    user = session.get(User, user_id)
    if user is None:
        return False
    session.delete(user)       # 标记为待删除
    session.flush()            # 发出 DELETE
    return True


# ─────────────────────────────────────────────────────────────────────────
# Todo 的 CRUD
# ─────────────────────────────────────────────────────────────────────────


def create_todo(session: Session, content: str, done: bool = False) -> Todo:
    """新增一条待办，返回已拿到自增 id 的 Todo。不 commit。

    done 默认 False，与 models.py 里 done 列的 default=False 一致；
    这里显式给参数，是为了 demo 能直接建一条"已完成"的待办来做条件过滤对比。
    """
    todo = Todo(content=content, done=done)
    session.add(todo)
    session.flush()
    return todo


def get_todo(session: Session, todo_id: int) -> Todo | None:
    """按主键查单条待办；查不到返回 None。"""
    return session.get(Todo, todo_id)


def list_todos(session: Session, done: bool | None = None) -> list[Todo]:
    """列出待办，按 id 升序。

    done 传 True / False → 只列该完成状态的（条件过滤）；传 None → 列全部。
    这就是"查询（列表 / 条件过滤）"：过滤无非是按需往 select 上挂一个 where。
    注意 done 是布尔列，`done is not None` 的判断不能省——因为 done=False 也是
    合法的过滤值，若写成 `if done:` 就把"查未完成"和"不过滤"混为一谈了。
    """
    stmt = select(Todo)
    if done is not None:
        stmt = stmt.where(Todo.done == done)
    stmt = stmt.order_by(Todo.id)
    return list(session.scalars(stmt).all())


def set_todo_done(session: Session, todo_id: int, done: bool = True) -> Todo | None:
    """把某条待办标记为完成 / 未完成，返回改后的对象；不存在返回 None。不 commit。"""
    todo = session.get(Todo, todo_id)
    if todo is None:
        return None
    todo.done = done
    session.flush()
    return todo


# ── Day 19 新增：通用字段更新 ─────────────────────────────────────────────
# set_todo_done 只能改 done 一列，接口层的 PATCH 需要"客户端传什么就改什么"，
# 所以补一个通用版。设计上保持与 set_todo_done 一致的约定：
#   · 接收 Session、不 commit（事务边界归调用方）；
#   · 不存在返回 None，让 service 层把它翻译成 404；
#   · flush 一次，让 UPDATE 立刻发到数据库（便于日志观察与后续查询看到新值）。
#
# fields 由调用方从 Pydantic 的 model_dump(exclude_unset=True) 得到 ——
# "字段合法性"（类型、长度、必填）已经在上层 Schema 校验过，DAO 层不重复做，
# 只负责把值 setattr 到 ORM 对象上。这是分层的意义：每层只管自己那摊事。
def update_todo(session: Session, todo_id: int, fields: dict[str, Any]) -> Todo | None:
    """按 id 更新任意字段：改成功返回对象，不存在返回 None。不 commit。

    fields 为空 dict 时也会走一遍 setattr 循环（等于什么都不改）+ flush，
    这种"空更新"应该在 service 层提前拦掉（返回 400），DAO 层不判断业务语义。
    """
    todo = session.get(Todo, todo_id)
    if todo is None:
        return None
    for key, value in fields.items():
        setattr(todo, key, value)
    session.flush()
    return todo


def delete_todo(session: Session, todo_id: int) -> bool:
    """按 id 删待办：删掉返回 True，不存在返回 False。不 commit。"""
    todo = session.get(Todo, todo_id)
    if todo is None:
        return False
    session.delete(todo)
    session.flush()
    return True


__all__ = [
    "create_user",
    "get_user",
    "get_user_by_username",
    "list_users",
    "update_user_email",
    "update_user",
    "delete_user",
    "create_todo",
    "get_todo",
    "list_todos",
    "set_todo_done",
    "update_todo",
    "delete_todo",
]
