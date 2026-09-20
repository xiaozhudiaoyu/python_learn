# 模块：业务服务层（Day 19 · 接口模型 vs ORM 模型分离）。
#
# 这是"分离"最关键的一层。它夹在 router（HTTP 层）和 dao（数据访问层）中间，
# 负责三件事：
#   1. **事务边界**：dao 层不 commit（Day 16 立的规矩），由 service 显式 commit / rollback；
#   2. **业务规则**：409 内容重复、400 空更新、404 不存在 —— 这些判断不属于 dao（它只管存取），
#      也不属于 router（它只管收发 HTTP），只能落在 service；
#   3. **ORM ↔ Schema 转换**：dao 返回的是 SQLAlchemy 的 Todo 对象（ORM 模型），
#      router 需要的是 Pydantic 的 TaskOut（接口模型）。转换点就在这里，
#      绝不让 ORM 对象越过 service 层跑到 router 里去。
#
# ── 为什么 ORM 对象不能直接给 router？（Day 19 的核心问题）──────────────────
#   · ORM 对象"活着"依赖 Session：session 关了之后再访问属性会抛 DetachedInstanceError；
#     router 返回时 FastAPI 才做序列化，那时 session 可能已经被 get_session 依赖关掉了。
#   · ORM 对象上有 relationship（owner、tags），FastAPI 序列化时会触发懒加载，
#     在错误的时机发一堆意料之外的 SELECT，甚至因为 session 已关而报错。
#   · ORM 字段和接口字段是"多对少"的关系：Todo 有 priority/created_at/owner_id，
#     但 TaskOut 只暴露 id/content/done。让 ORM 对象直接出去，等于把内部结构泄露给客户端。
#   · 最要命的是"耦合"：一旦 router 依赖了 ORM 的字段名，将来数据库改列名，
#     接口契约就跟着变。Schema 层就是那道"防火墙"。
#
# ── 转换靠什么？─────────────────────────────────────────────────────────
# Pydantic v2 的 ConfigDict(from_attributes=True)（v1 时代叫 orm_mode=True）。
# 打开这个开关后，TaskOut.model_validate(todo_orm_obj) 会去"按属性名读"而不是"按 dict 键读"，
# 于是可以直接把 ORM 对象喂进去，不必先手动转 dict。
# 这就是学习指南里说的"ORM → dict → Pydantic"的现代写法：中间那步 dict 被 Pydantic 吃掉了。

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from day15_orm import Todo
from day16_crud import dao
from todo_api.exceptions import NothingToUpdateError, TodoConflictError, TodoNotFoundError
from todo_api.schemas import TaskCreate, TaskOut, TaskUpdate

logger = logging.getLogger("todo_api.service")


# ── 内部小工具：ORM → Schema ─────────────────────────────────────────────
# 抽成一个函数而不是每处都写 TaskOut.model_validate(todo)，是为了：
#   · 转换逻辑只有一份，将来 TaskOut 加字段、或者要做字段脱敏，只改这里；
#   · 函数名 _to_out 明确表达"这是内部转换"，前缀下划线告诉外部别 import。
def _to_out(todo: Todo) -> TaskOut:
    """把 ORM 的 Todo 对象转成接口层的 TaskOut。

    依赖 TaskOut 上的 model_config = ConfigDict(from_attributes=True)（Day 19 新加）。
    没有那个开关，model_validate 只认 dict / 类 dict 对象，喂 ORM 对象会直接报错。
    """
    return TaskOut.model_validate(todo)


# ── 内部小工具：内容重复检查（409）───────────────────────────────────────
# 为什么不在数据库层给 content 加 unique 索引？（对照 day15_orm/models.py 的注释）
#   · username 重复是"数据完整性"问题，任何情况都不允许 → 数据库约束；
#   · content  重复是"当前 API 的业务选择"，将来可能放开     → 应用层逻辑。
# 应用层检查的代价：挡不住极端并发（两个请求同时查到"没重复"然后都插入）。
# 学习项目可以接受；真要严格，得在数据库层加唯一索引，然后 catch IntegrityError 翻译成 409。
def _assert_content_not_taken(session: Session, content: str, *, exclude_id: int | None = None) -> None:
    """检查 content 是否已被占用；占用则抛 TodoConflictError。

    exclude_id 用于 PATCH：改自己的 content 时，要排除"和自己重名"这种伪冲突。
    """
    stmt = select(Todo.id).where(Todo.content == content)
    if exclude_id is not None:
        stmt = stmt.where(Todo.id != exclude_id)
    # .first() 返回 None 或一个 id；我们只关心"有没有"，不关心具体是哪条。
    if session.scalars(stmt).first() is not None:
        raise TodoConflictError(content)


# ── 对外接口：CRUD ───────────────────────────────────────────────────────
# 命名刻意与 dao 层错开一层语义：
#   dao.create_todo(session, content, done)  → 面向"数据库操作"，参数是零散字段；
#   service.create_todo(session, payload)    → 面向"业务用例"，参数是接口的请求体模型。
# 这样 router 调 service 时直接把手里的 TaskCreate 传进来，不用自己拆字段。

def create_todo(session: Session, payload: TaskCreate) -> TaskOut:
    """新增一条待办。成功返回 TaskOut，内容重复抛 TodoConflictError（→ 409）。

    事务边界：本函数内部 commit。出错时 rollback 再把异常抛出去，
    让上层（router → FastAPI 异常 handler）翻译成 HTTP 响应。
    """
    try:
        _assert_content_not_taken(session, payload.content)
        todo = dao.create_todo(session, content=payload.content, done=payload.done)
        session.commit()
    except Exception:
        session.rollback()
        raise
    # commit 之后 todo 对象仍然可读属性，靠的是 day15_orm/database.py 里
    # sessionmaker 配的 expire_on_commit=False。如果是默认的 True，
    # 这里访问 todo.id 会触发一次新的 SELECT —— 而 session 可能已经准备关了，
    # 时序稍微不对就抛 DetachedInstanceError。这是"先 commit 再序列化"必须知道的坑。
    return _to_out(todo)


def list_todos(session: Session, *, done: bool | None = None) -> list[TaskOut]:
    """列出待办，可按完成状态过滤。只读操作，不需要 commit。

    注意：只读事务在 SQLAlchemy 里其实也开着（默认 autocommit=False），
    但因为没有写入，session.close() 时会自动 rollback（等于"什么都不做"），
    所以这里不必显式 commit。get_session 依赖的 finally 会负责 close。
    """
    todos = dao.list_todos(session, done=done)
    return [_to_out(t) for t in todos]


def get_todo(session: Session, todo_id: int) -> TaskOut:
    """按 id 查单条；不存在抛 TodoNotFoundError（→ 404）。"""
    todo = dao.get_todo(session, todo_id)
    if todo is None:
        raise TodoNotFoundError(todo_id)
    return _to_out(todo)


def update_todo(session: Session, todo_id: int, payload: TaskUpdate) -> TaskOut:
    """部分更新（PATCH 语义）。

    三类错误：
      · 400 NothingToUpdateError —— 请求体里一个字段都没传；
      · 404 TodoNotFoundError    —— id 不存在；
      · 409 TodoConflictError    —— 新 content 和别的任务重名。
    """
    # exclude_unset=True 是 PATCH 的关键：只拿"客户端真正传了"的字段，
    # 默认值（None）不算传过。这样 {"done": false} 和 {} 才能区分开。
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        # 400 的判断放在最前面：连 id 都不用查，省一次数据库往返。
        raise NothingToUpdateError(sorted(TaskUpdate.model_fields))

    try:
        # 先查存在性：dao.update_todo 对不存在的 id 返回 None，
        # 但那时它已经 flush 过一次（虽然什么都没改），事务状态不干净。
        # 提前用 get_todo 拦一道，逻辑更清晰。
        existing = dao.get_todo(session, todo_id)
        if existing is None:
            raise TodoNotFoundError(todo_id)

        # 只有当客户端真的要改 content、且新值和旧值不同时，才做重复检查。
        # 否则"把 done 从 false 改成 true"这种请求也会被无谓地查一次 content。
        new_content = fields.get("content")
        if new_content is not None and new_content != existing.content:
            _assert_content_not_taken(session, str(new_content), exclude_id=todo_id)

        updated = dao.update_todo(session, todo_id, fields)
        # updated 理论上不会是 None（上面已经确认存在），但类型检查器不知道，
        # 这里显式断言一下，让 Pyright 推断出 updated 是 Todo 而不是 Todo | None。
        assert updated is not None, "existing 已确认存在，update_todo 不应返回 None"
        session.commit()
    except Exception:
        session.rollback()
        raise
    return _to_out(updated)


def delete_todo(session: Session, todo_id: int) -> None:
    """按 id 删；不存在抛 TodoNotFoundError（→ 404）。成功返回 None（router 会转成 204）。"""
    try:
        deleted = dao.delete_todo(session, todo_id)
        if not deleted:
            raise TodoNotFoundError(todo_id)
        session.commit()
    except Exception:
        session.rollback()
        raise


def reset_todos(session: Session) -> list[TaskOut]:
    """清空 todos 表，返回空列表。

    Day 19 语义调整：内存版的 reset 是"恢复初始 3 条种子数据"，
    接数据库后如果照搬，会跟 user/tag 的外键关系打架（删 todo 时 tag 关联表也得清）。
    简化为"清空所有 todo"，语义诚实、破坏面最小。
    需要种子数据请走 Alembic 迁移或独立的 seed 脚本，不混在接口里。

    注意：这里用 delete() 批量语句而不是逐条 session.delete(obj)，
    因为后者在数据量大时会慢得离谱（N 次 DELETE + N 次 ORM 状态维护）。
    """
    from sqlalchemy import delete as sa_delete

    try:
        # todo_tags 关联表设了 ondelete="CASCADE"（见 day15_orm/models.py），
        # 数据库会自动清掉对应的关联行，不需要 ORM 层先手动解除关系。
        session.execute(sa_delete(Todo))
        session.commit()
    except Exception:
        session.rollback()
        raise
    logger.info("reset_todos：已清空 todos 表")
    return []


__all__ = [
    "create_todo",
    "list_todos",
    "get_todo",
    "update_todo",
    "delete_todo",
    "reset_todos",
]
