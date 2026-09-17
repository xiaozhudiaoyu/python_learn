# 模块：关联关系 + 分页 DAO（Day 17）。
#
# 在 Day 16 的基础上，增加三类能力：
#   1. 一对多关联操作（Todo ↔ User）：创建时指定 owner、按 owner 查询、双向导航
#   2. 多对多关联操作（Todo ↔ Tag）：打标签、按标签查 Todo、解除关联
#   3. 分页查询（limit/offset + total count）
#
# 与 Day 16 dao.py 同一套设计约定：
#   · DAO 函数接收 Session，但绝不 commit —— 事务边界由调用方掌控；
#   · flush 只在"需要拿到数据库生成的值"时才调（如自增 id）。

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from day15_orm import Tag, Todo, User


# ─────────────────────────────────────────────────────────────────────────
# 一对多：Todo ↔ User
# ─────────────────────────────────────────────────────────────────────────


def create_todo_with_owner(
    session: Session, content: str, owner_id: int, *, done: bool = False
) -> Todo:
    """新增一条待办并关联到指定用户，返回已拿到 id 的 Todo。不 commit。

    owner_id 直接传整数而不是 User 对象 —— 这是"面向外键"的写法，
    适合已经知道 id 的场景（比如从 HTTP 请求里拿到的 user_id）。
    如果你想"面向关系"地写，也可以：todo.owner = user_obj，效果相同。
    """
    todo = Todo(content=content, done=done, owner_id=owner_id)
    session.add(todo)
    session.flush()
    return todo


def list_todos_by_owner(session: Session, owner_id: int) -> list[Todo]:
    """查某个用户名下的全部待办，按 id 升序。

    这是"用外键列做条件过滤"—— 最朴素的关联查询方式。
    和 user.todos（relationship 导航）效果相同，区别在于：
      · select + where → 你自己写 SQL 条件，灵活度高（可加排序/过滤/分页）；
      · user.todos    → ORM 替你生成 SQL，写起来短，但加条件不如 select 直观。
    两种方式都会用到，看场景选。
    """
    stmt = select(Todo).where(Todo.owner_id == owner_id).order_by(Todo.id)
    return list(session.scalars(stmt).all())


def get_user_with_todos(session: Session, user_id: int) -> User | None:
    """查用户，同时【预加载】他的 todos 列表（急加载 / eager loading）。

    selectinload(User.todos) 的效果：
      1. 先发 SELECT * FROM users WHERE id = ?（拿到 User）
      2. 再发 SELECT * FROM todos WHERE owner_id IN (?)（一次拿回所有关联 Todo）
    总共 2 条 SQL，不管你有多少个 user —— 这就解决了 N+1 问题。

    对比"懒加载"（默认行为）：
      访问 user.todos 时才触发第 2 条 SQL。如果你在循环里逐个访问 100 个 user 的
      todos，就会发出 1 + 100 = 101 条 SQL（经典的 N+1）。selectinload 把它压成 2 条。

    为什么叫 "selectin" 而不是 "join"？
      selectinload = 用第二条 SELECT ... WHERE ... IN (...) 来加载（适合一对多）；
      joinedload  = 用 JOIN 一条 SQL 搞定（适合多对一 / 一对一）。
      一对多用 JOIN 会导致"行膨胀"（笛卡尔积），所以一对多推荐 selectinload。
    """
    stmt = (
        select(User)
        .options(selectinload(User.todos))
        .where(User.id == user_id)
    )
    return session.scalars(stmt).first()


def get_todo_with_owner(session: Session, todo_id: int) -> Todo | None:
    """查单条待办，同时预加载它的 owner（急加载）。

    这里用 selectinload 也可以，但因为"多对一"只有一条结果，
    joinedload 更直观（一条 SQL 用 LEFT JOIN 搞定）。
    不过为了统一写法、避免混用，这里也用 selectinload —— 它同样有效，
    只是多了一条 SQL（SELECT * FROM users WHERE id IN (?)）。
    """
    stmt = (
        select(Todo)
        .options(selectinload(Todo.owner))
        .where(Todo.id == todo_id)
    )
    return session.scalars(stmt).first()


# ─────────────────────────────────────────────────────────────────────────
# 多对多：Todo ↔ Tag
# ─────────────────────────────────────────────────────────────────────────


def create_tag(session: Session, name: str) -> Tag:
    """新增一个标签，返回已拿到 id 的 Tag。不 commit。"""
    tag = Tag(name=name)
    session.add(tag)
    session.flush()
    return tag


def get_or_create_tag(session: Session, name: str) -> Tag:
    """按 name 查标签，存在就返回，不存在就新建。

    这种"get_or_create"模式在实际项目里非常常见（比如用户选标签时，
    已有标签直接关联、新标签先创建再关联），避免唯一约束报错。
    """
    stmt = select(Tag).where(Tag.name == name)
    tag = session.scalars(stmt).first()
    if tag is not None:
        return tag
    return create_tag(session, name)


def add_tags_to_todo(session: Session, todo_id: int, tag_names: list[str]) -> Todo | None:
    """给一条待办打上多个标签（按名称），返回操作后的 Todo；Todo 不存在返回 None。

    内部演示了 relationship 的列表操作：todo.tags.append(tag) / extend(tags)。
    SQLAlchemy 会自动在 flush 时往中间表 todo_tags 插入对应行。
    如果标签已存在（重复 append），SQLAlchemy 不会重复插入（它内部做了去重），
    但为了代码清晰，这里先判断 `tag not in todo.tags`。
    """
    todo = session.get(Todo, todo_id)
    if todo is None:
        return None
    for name in tag_names:
        tag = get_or_create_tag(session, name)
        if tag not in todo.tags:
            todo.tags.append(tag)
    session.flush()
    return todo


def remove_tag_from_todo(session: Session, todo_id: int, tag_name: str) -> bool:
    """解除一条待办与某个标签的关联。成功返回 True，未找到返回 False。

    todo.tags.remove(tag) → SQLAlchemy 在 flush 时从中间表 DELETE 对应行。
    注意这只断开关联，不删除 Tag 本身（标签可能还贴在别的 Todo 上）。
    """
    todo = session.get(Todo, todo_id)
    if todo is None:
        return False
    tag = session.scalars(select(Tag).where(Tag.name == tag_name)).first()
    if tag is None or tag not in todo.tags:
        return False
    todo.tags.remove(tag)
    session.flush()
    return True


def list_todos_by_tag(session: Session, tag_name: str) -> list[Todo]:
    """查所有带某个标签的待办（通过中间表 JOIN）。

    SQL 等价于：
      SELECT todos.* FROM todos
      JOIN todo_tags ON todos.id = todo_tags.todo_id
      JOIN tags ON tags.id = todo_tags.tag_id
      WHERE tags.name = ?

    在 SQLAlchemy 2.0 里用 select().join() 显式写出来，
    join 的第一个参数是要 JOIN 的模型/表，第二个是 ON 条件。
    但因为 relationship 已经声明了 secondary，SQLAlchemy 能自动推断 JOIN 条件，
    所以简写为 .join(Todo.tags).where(Tag.name == tag_name) 也行。
    这里用显式写法，让你看清"到底 JOIN 了什么"。
    """
    stmt = (
        select(Todo)
        .join(Todo.tags)
        .where(Tag.name == tag_name)
        .order_by(Todo.id)
    )
    return list(session.scalars(stmt).all())


def get_todo_with_tags(session: Session, todo_id: int) -> Todo | None:
    """查单条待办，同时预加载其 tags 列表（解决多对多的 N+1）。"""
    stmt = (
        select(Todo)
        .options(selectinload(Todo.tags))
        .where(Todo.id == todo_id)
    )
    return session.scalars(stmt).first()


# ─────────────────────────────────────────────────────────────────────────
# 分页查询（limit / offset）
# ─────────────────────────────────────────────────────────────────────────


def count_todos(
    session: Session,
    *,
    owner_id: int | None = None,
    done: bool | None = None,
) -> int:
    """统计满足条件的待办总数（用于分页时返回 total）。

    SELECT count(*) FROM todos WHERE ...
    这条 SQL 很轻量（不传输行数据），但如果表很大且 WHERE 条件没索引，
    全表扫描也会慢 —— 生产环境要考虑加索引或缓存 total。
    """
    stmt = select(func.count()).select_from(Todo)
    if owner_id is not None:
        stmt = stmt.where(Todo.owner_id == owner_id)
    if done is not None:
        stmt = stmt.where(Todo.done == done)
    return int(session.scalar(stmt) or 0)


def list_todos_paginated(
    session: Session,
    *,
    page: int = 1,
    page_size: int = 10,
    owner_id: int | None = None,
    done: bool | None = None,
    with_owner: bool = False,
) -> tuple[list[Todo], int]:
    """分页查询待办，返回 (当前页数据列表, 总条数)。

    分页的核心就是 LIMIT + OFFSET：
      · page_size → LIMIT（每页多少条）
      · (page - 1) * page_size → OFFSET（跳过前面多少条）

    例如 page=3, page_size=10 → LIMIT 10 OFFSET 20（跳过前 20 条，取第 21~30 条）。

    total 是额外一条 count(*) 查询 —— 前端需要它来计算"共几页"。
    两条 SQL 不在同一个原子快照里，理论上可能不一致（count 之后、取数据之前有人插入），
    但在学习场景和绝大多数业务里这不是问题。真要强一致就用窗口函数 COUNT(*) OVER()。

    with_owner=True 时顺带预加载 owner，避免返回结果后逐个懒加载产生 N+1。
    """
    # 1) 总数
    total = count_todos(session, owner_id=owner_id, done=done)

    # 2) 当前页数据
    stmt = select(Todo)
    if owner_id is not None:
        stmt = stmt.where(Todo.owner_id == owner_id)
    if done is not None:
        stmt = stmt.where(Todo.done == done)
    if with_owner:
        stmt = stmt.options(selectinload(Todo.owner))
    stmt = stmt.order_by(Todo.id)
    stmt = stmt.limit(page_size).offset((page - 1) * page_size)

    items = list(session.scalars(stmt).all())
    return items, total


__all__ = [
    "create_todo_with_owner",
    "list_todos_by_owner",
    "get_user_with_todos",
    "get_todo_with_owner",
    "create_tag",
    "get_or_create_tag",
    "add_tags_to_todo",
    "remove_tag_from_todo",
    "list_todos_by_tag",
    "get_todo_with_tags",
    "count_todos",
    "list_todos_paginated",
]
