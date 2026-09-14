# 模块：engine 与 session（Day 15 · SQLAlchemy 2 基础）。
#
# SQLAlchemy 里有两个必须分清的对象，初学者最容易混：
#
#   Engine  —— "连接池 + 方言"，代表与数据库的【通道】。
#              整个进程建一个就够，它是线程安全的，内部维护着一池子连接。
#              不要每来一个请求就 create_engine()，那等于每次重新握手，慢且会耗尽连接数。
#
#   Session —— "一次工作单元（Unit of Work）"，代表一段【业务对话】。
#              它跟踪你改了哪些对象、该发什么 SQL、什么时候提交。
#              不是线程安全的，一个请求 / 一个线程用一个，用完就关。
#
# 一句话记忆：Engine 是自来水厂和管道，Session 是你家水龙头。
# 管道全程只有一套，水龙头用完要关。

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .db_config import build_url, masked_url
from .models import Base


def get_engine(*, echo: bool = False) -> Engine:
    """创建 Engine。

    echo=True 是学习期最有用的开关：它把 SQLAlchemy 生成的每一条 SQL
    都原样打印到控制台，你能亲眼看到 ORM 到底替你写了什么。
    生产环境要关掉，否则日志会被 SQL 淹没，还会泄露数据。

    pool_pre_ping=True —— 连接从池里取出来之前先" ping "一下确认还活着。
      为什么 MySQL 特别需要它：MySQL 的 wait_timeout 默认 8 小时，
      空闲超时的连接会被【服务端】单方面掐断，而客户端的连接池并不知道。
      下次取出来用时就会撞上 "MySQL server has gone away"。
      开了 pre_ping，坏连接会被丢弃重建，代价是每次取连接多一个极轻量的探测。

    pool_recycle=3600 —— 存活超过 1 小时的连接主动回收重建，是上面那道保险的第二层。
    """
    return create_engine(
        build_url(),
        echo=echo,
        pool_pre_ping=True,
        pool_recycle=3600,
    )


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    """把 Engine 绑到一个 session 工厂上，之后每次调用工厂就得到一个 Session。

    为什么要有"工厂"这一层，而不是直接 Session(engine)？
      因为 session 的配置（expire_on_commit、autoflush 等）应该只写一次。
      工厂记住了这些配置，各处要 session 时统一向它要，不会各写各的。
      Day 19 接 FastAPI 时，这个工厂就会被塞进 Depends 里按请求发放 session。

    expire_on_commit=False 是个很实用的选择：
      默认 True 时，commit 之后所有对象属性会"过期"，再访问就会触发一次新的 SELECT；
      如果那时 session 已经关了，就直接抛 DetachedInstanceError。
      设成 False 后，commit 之后照样能读对象属性 ——
      接口里"先 commit 再把对象序列化成响应"这种写法必须靠它。

    autoflush=False：
      默认 True 时，每次查询前 SQLAlchemy 会先把待处理的改动偷偷 flush 到数据库，
      时序不好预判。关掉之后，写入时机完全由你显式控制（flush / commit），
      学习阶段更容易看清"哪一步真的发了 SQL"。
    """
    return sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
        autoflush=False,
    )


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    """把"开 session → 提交 / 回滚 → 关闭"这套固定动作包成一个 with 块。

    为什么要包这一层？因为忘记 close 或忘记 rollback 是最常见的两类事故：
      忘记 close   → 连接不归还池子，跑一会儿就 "QueuePool limit ... overflow"；
      忘记 rollback → 出错的事务挂在连接上，这条连接被还回池子后，
                      下一个使用者会莫名继承一个半死的事务。

    写成 with 之后，无论正常结束还是抛异常，finally 里的 close 一定执行。
    注意这里的 except 分支 rollback 之后要 raise 把异常继续往外抛 ——
    吞掉异常会让调用方以为成功了，那比报错危险得多。
    """
    session = get_session_factory(engine)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_models(engine: Engine) -> None:
    """建表：把 Base.metadata 里的全部"图纸"翻译成 CREATE TABLE 并执行。

    checkfirst=True（也是默认值，这里显式写出来强调）表示建之前先查
    information_schema，表已存在就【跳过】。所以：
      · 这个函数可以反复执行，不会报 "Table already exists"；
      · 但它也【不会】修改已存在的表 —— 你给模型加了字段，再跑一次是没用的，
        旧表原样不动。想同步结构变更，要么手工 ALTER，要么等 Day 18 用 Alembic。
        这正是 Alembic 存在的理由：create_all 只管"从无到有"，管不了"从旧到新"。

    它同样【不会】删表。删表要显式调用 Base.metadata.drop_all()，
    那属于破坏性操作，本模块故意不提供封装，避免被顺手调用。
    """
    Base.metadata.create_all(engine, checkfirst=True)


def existing_tables(engine: Engine) -> list[str]:
    """返回数据库里当前实际存在的表名列表。

    用的是 SQLAlchemy 的 inspect() 反射能力：它直接去问数据库
    "你现在有哪些表"，而不是读 Python 里的模型定义。
    这个区别很关键 —— 拿它和 Base.metadata.tables 的键对比，
    就能发现"模型里有、库里没有"或"库里有、模型里没有"的漂移。
    """
    table_names: list[str] = list(inspect(engine).get_table_names())
    return table_names


__all__ = [
    "get_engine",
    "get_session_factory",
    "session_scope",
    "init_models",
    "existing_tables",
    "masked_url",
]
