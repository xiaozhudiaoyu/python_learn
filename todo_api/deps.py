# Day 11 · Depends 依赖注入：把"取值 + 校验 + 准备资源"从接口函数里抽出来复用。
#
# 一句话说清 Depends 在干什么：
#   参数上写 `x: T = Depends(f)`，FastAPI 就在进接口函数体之前先调用 f()，
#   把 f 的返回值交给 x。f 自己的参数还能再写 Depends —— 于是形成一棵"依赖树"，
#   框架自顶向下解析；同一个请求里，同一个依赖默认只执行一次（结果缓存）。
#
# 补上 main.py 那张"参数取值来源"规则表的最后一行：
#   · 名字在路径 {x} 里          → 路径参数      （Day 9）
#   · 标量且不在路径里           → 查询参数      （Day 9）
#   · 类型是 Pydantic 模型       → 请求体 body   （Day 10）
#   · 注解包了 Depends / Security → 框架调用依赖函数注入（Day 11，本文件）
#
# 为什么值得用它：
#   1) 复用：分页、当前用户这类参数会在几十个接口里重复，抽成依赖只写一份；
#   2) 分层：接口层不再关心"怎么连库、怎么解 token"，只接收处理好的成品；
#   3) 可替换：测试时 app.dependency_overrides[f] = 假的 就能整体换掉，不碰业务代码
#      （本仓库见根目录 run_day11_demo.py 第 6 段演示）；
#   4) 文档免费：依赖里声明的 Query / Header 会自动出现在 /docs。
#
# 本文件为什么单独存在：
#   依赖是"跨接口复用"的东西，和 schemas.py 一样属于公共层；
#   将来接 SQLAlchemy（第三阶段），这里的 fake 资源就会换成真正的 Session 依赖。

import logging
from collections.abc import Iterator
from time import perf_counter
from typing import Annotated, Literal

from fastapi import Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

logger = logging.getLogger("todo_api.deps")


# ── ① 普通依赖：把"一对查询参数"收敛成"一个语义对象" ────────────────────
class Pagination(BaseModel):
    """分页参数集合。接口里拿到的就是这一个对象，而不是散落的 limit / offset。"""

    limit: int = Field(description="本页条数")
    offset: int = Field(description="跳过多少条", ge=0)

    def as_slice(self) -> slice:
        """给内存列表切片用；接了数据库后这里会变成 SQLAlchemy 的 .limit().offset()。"""
        return slice(self.offset, self.offset + self.limit)


def pagination_params(
    limit: Annotated[int, Query(ge=1, le=100, description="本页条数，1~100")] = 10,
    offset: Annotated[int, Query(ge=0, description="跳过多少条")] = 0,
) -> Pagination:
    """依赖函数本身就是一个普通函数：FastAPI 照样按【查询参数】给它取值并校验。

    校验失败（比如 limit=999）直接返回 422，根本不会进接口函数体 ——
    和 Day 10 的请求体校验是同一套机制，因为背后都是 Pydantic。
    """
    return Pagination(limit=limit, offset=offset)


# 别名：接口里只写 `page: PaginationDep`，规则要改（比如上限从 100 改 50）只改这一处。
# 用 Annotated 而不是 `page: Pagination = Depends(pagination_params)`，
# 是为了让"类型"和"来源"写在同一处：类型检查器能看到它是 Pagination，Pydantic/文档也认它。
PaginationDep = Annotated[Pagination, Depends(pagination_params)]


# ── ② 依赖嵌套：依赖的参数还是依赖 ────────────────────────────────────
SortOrder = Literal["asc", "desc"]  # 用 Literal → 非法值自动 422，不用自己写 if


class PageQuery(BaseModel):
    """一次翻页请求的完整语义：分页 + 排序。"""

    pagination: Pagination
    order: SortOrder


def page_query(
    page: PaginationDep,
    order: Annotated[SortOrder, Query(description="排序方向")] = "asc",
) -> PageQuery:
    """page 这个参数的值，来自另一个依赖的返回值 —— 这就是"依赖树"。

    解析顺序：FastAPI 先跑到底层的 pagination_params（取 limit/offset 并校验），
    再把它产出的 Pagination 交给本函数，最后把 PageQuery 注入接口。
    接口函数只看到最终的 PageQuery，完全不知道中间经过了几层。
    """
    return PageQuery(pagination=page, order=order)


PageQueryDep = Annotated[PageQuery, Depends(page_query)]


# ── ③ yield 依赖：需要"用完释放"的资源 ────────────────────────────────
class FakeSession:
    """模拟需要成对管理的资源（第三阶段就是 SQLAlchemy Session / 数据库连接）。"""

    _next_id = 0

    def __init__(self) -> None:
        FakeSession._next_id += 1
        self.id = FakeSession._next_id
        self.note: str | None = None
        self.closed = False

    def close(self) -> None:
        self.closed = True
        logger.info("FakeSession#%s 已释放", self.id)


# 保留最近几个会话对象，好让接口能回看"上一次请求的资源是否已被释放"（可见的收尾证据）
_SESSION_HISTORY: list[FakeSession] = []


def fake_session(
    note: Annotated[str | None, Query(description="随便传点东西，验证它确实是依赖取的")] = None,
) -> Iterator[FakeSession]:
    """生成器依赖：yield 之前 = 进接口函数之前；yield 之后 = 响应发出之前。

    关键在 try/finally：接口函数里 raise HTTPException、甚至抛未捕获异常，
    finally 照样执行，资源不会泄漏 —— 这就是它比"在函数体里手动 close"可靠的地方。
    yield 出来的值（这里是 session）就是注入给接口的参数值。
    """
    session = FakeSession()
    session.note = note
    _SESSION_HISTORY.append(session)
    del _SESSION_HISTORY[:-5]  # 只留最近 5 个，防止这个演示列表无限增长
    try:
        yield session
    finally:
        session.close()


SessionDep = Annotated[FakeSession, Depends(fake_session)]


def recent_sessions() -> list[FakeSession]:
    """内部历史列表的只读快照，给演示接口回看"上一次的资源是否已释放"用。"""
    return list(_SESSION_HISTORY)


def request_timer(request: Request) -> Iterator[None]:
    """纯观测型 yield 依赖：不往接口注入任何值（返回 None），只统一记一行耗时。

    这种"只要副作用、不要返回值"的依赖，适合挂到 dependencies=[...] 上：
    app 级 / router 级 / 单个接口级三种挂法，本仓库分别见 main.py、
    routers/depends_demo.py 的 /guarded。

    局限（先记住，后面 Day 会用到）：yield 之后拿不到"响应体"，也改不了状态码；
    要统一改写响应，那是中间件（Starlette）的活。
    """
    started = perf_counter()
    try:
        yield
    finally:
        cost_ms = (perf_counter() - started) * 1000
        logger.info(
            "%s %s -> 耗时 %.2f ms", request.method, request.url.path, cost_ms
        )


# ── ④ 登录态依赖：两层串联，顺便看清 401 / 403 的分工 ───────────────────
class CurrentUser(BaseModel):
    """当前登录用户（第三阶段会变成数据库里的 User 表记录）。"""

    id: int
    name: str
    is_admin: bool = False


def api_token(
    x_token: Annotated[str | None, Header(alias="X-Token")] = None,
) -> str:
    """第一层：只负责"把原始凭证取出来"，不认识用户。

    拆这么细的好处：将来把 X-Token 换成 JWT / OAuth2，只改这个函数，
    下面所有依赖 get_current_user 的接口一行都不用动。
    （注：Header 默认会把参数名 x_token 映射成请求头 x-token，这里用 alias 显式写成 X-Token。）
    """
    if x_token is None:
        # 连身份都没确认 → 401 Unauthorized（语义是"未认证"，不是"没权限"）
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少 X-Token 请求头",
            headers={"WWW-Authenticate": "Token"},
        )
    return x_token


TokenDep = Annotated[str, Depends(api_token)]

# 假数据：token -> (id, 姓名, 是否管理员)。真实项目里这一步是查库 + 校验签名。
_FAKE_USERS_BY_TOKEN: dict[str, tuple[int, str, bool]] = {
    "tok-001": (1, "张三", True),
    "tok-002": (2, "李四", False),
}


def get_current_user(token: TokenDep, request: Request) -> CurrentUser:
    """第二层：凭证 -> 用户。顺便用 request.state 计数，验证"同一请求只解析一次"。"""
    request.state.token_lookups = getattr(request.state, "token_lookups", 0) + 1

    found = _FAKE_USERS_BY_TOKEN.get(token)
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Token 无效或已过期",
            headers={"WWW-Authenticate": "Token"},
        )
    user_id, name, is_admin = found
    return CurrentUser(id=user_id, name=name, is_admin=is_admin)


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def require_admin(user: CurrentUserDep) -> CurrentUser:
    """第三层：用户 -> 权限。身份是好的、只是不允许做这件事 → 403 Forbidden。

    401 = "你是谁我都不知道"，403 = "我知道你是谁，但你不能进"，别混用。
    它复用了 get_current_user 的返回值（同一请求内不会重复查库）。
    """
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员身份")
    return user


AdminDep = Annotated[CurrentUser, Depends(require_admin)]


def get_optional_user(
    x_token: Annotated[str | None, Header(alias="X-Token")] = None,
) -> CurrentUser | None:
    """"可选登录"变体：游客也给过，登录后展示个性化内容。

    注意它没有复用 api_token，而是自己读了一遍 Header ——
    因为依赖函数是在进接口之前就被调用的，它一旦 raise 401 就直接返回错误了，
    在接口函数里 try/except 是拦不住的。想要"软校验"，就得单独写一个不抛错的依赖。
    """
    found = _FAKE_USERS_BY_TOKEN.get(x_token or "")
    if found is None:
        return None
    user_id, name, is_admin = found
    return CurrentUser(id=user_id, name=name, is_admin=is_admin)


OptionalUserDep = Annotated[CurrentUser | None, Depends(get_optional_user)]


# ── ⑤ 只拦不注入：给 dependencies=[...] 用的"守卫型"依赖 ────────────────
def require_client_tag(
    x_client: Annotated[str | None, Header(alias="X-Client")] = None,
) -> None:
    """返回 None 的依赖：作用只是"过不了就拦下"，不给接口注入任何东西。

    接口签名里不必出现它的参数；被拦截时客户端拿到 400。
    """
    if x_client is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="缺少 X-Client 请求头（用于区分调用方：web / app / script）",
        )
