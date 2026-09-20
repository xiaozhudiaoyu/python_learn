# 模块：数据库会话（Day 19 · 接口模型 vs ORM 模型分离）。
#
# 这个文件解决一件事：**HTTP 请求怎么拿到一个 SQLAlchemy Session**。
# 与 Day 15 的 day15_orm/database.py 是"上下两层"关系：
#   database.py  提供 get_engine / get_session_factory / session_scope —— 通用工具，任何脚本都能用；
#   这里（db.py）把上面的工具"绑到 FastAPI 的请求生命周期上"—— 一个请求一个 Session。
#
# 为什么要单独一个文件、而不是让 router 直接调 day15_orm.database？
#   · 分层清晰：day15_orm 是"数据库层"、todo_api 是"接口层"，接口层封装自己的入口，
#     将来换 DB 或换连接池策略，只动这一个文件，router/service 一行都不用改；
#   · FastAPI 的依赖注入需要一个"零参数、返回 Session"的可调用对象，
#     day15_orm.database.session_scope 是 contextmanager（用 with 打开），
#     签名不匹配 Depends 的用法，必须在这里适配一次。
#
# ── 全局 Engine 单例 ──────────────────────────────────────────────────────
# day15_orm/database.py 里说得很清楚：Engine 全进程一个就够、线程安全、内含连接池。
# 那"单例"具体怎么落？两种常见写法：
#   (A) 模块级直接 engine = get_engine()  —— import 时就建，简单粗暴；
#   (B) 懒加载：模块级只放一个 None，第一次调用时才建、之后复用。
# 这里选 (B)，理由：
#   · import todo_api.main 时如果 MySQL 没起，(A) 会让整个应用启动直接崩，
#     连 /docs 都打不开，调试很难受；(B) 只会在真正处理请求时才连库；
#   · 单元测试里可以 monkeypatch 掉 _engine，注入一个 SQLite 内存库，
#     (A) 就做不到（模块级变量在 import 时已经绑定了）。

from collections.abc import Iterator
from typing import Optional

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from day15_orm import get_engine, get_session_factory

# 模块级"单例槽位"。前缀下划线表示"这是内部状态，别从外部直接读写"，
# 外部要用请调 get_db_engine() / get_session()。
_engine: Optional[Engine] = None
_session_factory = None


def get_db_engine(*, echo: bool = False) -> Engine:
    """返回全局唯一的 Engine。第一次调用时创建、之后直接复用。

    echo 参数只在"第一次创建"时生效——后续调用即使传 echo=True 也不会改变已建 Engine 的行为。
    这是懒加载单例的一个小陷阱，学习期够用了；生产环境如果需要动态开关 echo，
    应该改用 logging 配置而不是重建 Engine。
    """
    global _engine
    if _engine is None:
        _engine = get_engine(echo=echo)
    return _engine


def get_db_session_factory():
    """返回全局唯一的 sessionmaker。第一次调用时创建、之后直接复用。

    单独抽出来是因为 service 层或者脚本里可能需要"手动开一个 session"，
    不走 HTTP 请求的依赖注入路径（比如启动时的 init_models、种子数据脚本）。
    """
    global _session_factory
    if _session_factory is None:
        _session_factory = session_factory_from_engine(get_db_engine())
    return _session_factory


def session_factory_from_engine(engine: Engine):
    """把 day15_orm 的 get_session_factory 再包一层，只是为了让上面的懒加载写得整齐。"""
    return get_session_factory(engine)


# ── FastAPI 依赖：一个请求一个 Session ─────────────────────────────────────
# 用法（在 router 里）：
#     from todo_api.db import get_session
#     @router.get("/api/todos")
#     def list_todos(session: Session = Depends(get_session)):
#         ...
#
# 为什么用 yield 而不是 return？（Day 11 讲过 yield 依赖，这里是它的经典用例）
#   · return 版本：函数返回 Session 后，FastAPI 处理完请求就没人管这个 Session 了，
#     close() 得靠调用方在每个 router 里手写 try/finally —— 写 10 个接口就要写 10 遍；
#   · yield 版本：yield 之前 = "请求开始前的准备"，yield 之后 = "请求结束后的清理"，
#     无论请求处理是成功、抛异常、还是被客户端取消，finally 里的 close 一定执行。
#     这就是"资源型依赖"的标准写法。
#
# ── 事务边界谁负责？───────────────────────────────────────────────────────
# 这里【故意不】在 yield 之后写 commit / rollback。原因：
#   · commit 是"业务决定"，应该由 service 层显式控制 —— 一个请求里可能连着做
#     "改邮箱 + 加待办"两件事，必须一起成功或一起失败，commit 只能写在最后；
#   · 如果 get_session 在请求结束时自动 commit，service 层里任何"查完直接返回"
#     的只读操作都会被误 commit，白白浪费一次事务开销；
#   · rollback 只作为"兜底"：service 层没 commit 就抛异常了，说明事务已经脏了，
#     这里帮它 rollback 一次，避免连接归还池子时带着半死事务。
#
# 一句话总结：get_session 只管"发水龙头、关水龙头"，不管"水放多少、什么时候放"。

def get_session() -> Iterator[Session]:
    """FastAPI 依赖：按请求发放 Session，请求结束时自动关闭。

    返回类型写成 Iterator[Session] 而不是 Session —— 因为这是个生成器函数，
    yield 出去的值才是 Session。FastAPI 看到返回类型是 Iterator/Generator，
    就知道要用 yield 依赖的协议来处理它。
    """
    factory = get_db_session_factory()
    session = factory()
    try:
        yield session
    except Exception:
        # 兜底 rollback：service 层如果已经 rollback 过了，再调一次是无害的
        # （SQLAlchemy 的 rollback 是幂等的）。
        session.rollback()
        raise
    finally:
        # close() 把连接归还连接池，不是真的断开数据库连接。
        # 忘了 close 的后果：连接不归还，跑一会儿就 "QueuePool limit ... overflow"。
        session.close()


__all__ = [
    "get_db_engine",
    "get_db_session_factory",
    "get_session",
]
