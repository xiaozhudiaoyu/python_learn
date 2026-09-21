# 路由模块：/api/users —— 用户接口（Day 20 · 数据库版）。
#
# 起步版（Day 9）这里是一份写死的 _FAKE_USERS 内存列表，只有一个 GET 用来
# 演示"查询参数"。Day 20 综合练习把它升级成真正的数据库版：
#   · 数据读写下沉到 service 层（service.create_user / list_users / ...）；
#   · 补全 CRUD 四类操作（新增 / 查询 / 修改 / 删除）；
#   · 每个接口靠 Depends(get_session) 拿数据库会话。
# 分层调用链和 todos.py 完全一致：router → service → dao → ORM。
#
# ── 一个必须知道的接口契约变化 ────────────────────────────────────────
# 起步版返回的字段是 {"id", "name"}，但 ORM 的 User 表里那一列叫 username
# （见 day15_orm/models.py），数据库版统一成 {"id", "username", "email"}。
# 这不是笔误而是有意为之：接口字段应当对齐真实数据模型，"name" 是假数据时期
# 的临时叫法。main.py 的 tags 早就标注 users "接数据库后会大改"，即指此处。

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from todo_api import service
from todo_api.db import get_session
from todo_api.schemas import ErrorOut, UserCreate, UserOut, UserUpdate

# 定义本模块的路由：统一前缀 /api/users；tags 会在 Swagger 文档里作为分组标题显示。
router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("")
def list_users(
    limit: int = 10,
    session: Session = Depends(get_session),
) -> list[UserOut]:
    """返回用户列表，演示【查询参数】与默认值（Day 9 的教学点，原样保留）。

    取值规则：limit 不在路径 {..} 里、且是标量(int)，FastAPI 便按"查询参数"取值，
    于是 /api/users?limit=2 → limit=2；默认值 =10 表示"可选"，不传就用 10。
    想加范围校验：from fastapi import Query，写 limit: int = Query(default=10, ge=1, le=100)。

    Day 20 的变化只在函数体：原来是对内存 _FAKE_USERS 做切片 [:limit]，
    现在是 service.list_users(session, limit=limit) —— limit 下推成 SQL 的 LIMIT 子句，
    由数据库只捞前 N 行，而不是把全表读进内存再切。数据量大时差别很明显。
    """
    return service.list_users(session, limit=limit)


@router.get(
    "/{user_id}",
    responses={404: {"model": ErrorOut, "description": "用户不存在（统一错误结构，见 /docs）"}},
)
def get_user(user_id: int, session: Session = Depends(get_session)) -> UserOut:
    """按编号返回单个用户：/api/users/2。

    路径参数 user_id 的取值/校验规则和 todos.py 的 todo_id 一模一样。
    404 由 service 层抛 UserNotFoundError，exceptions.py 的 handler 统一翻译成
    {code, message, details} 结构，router 里不写一处错误处理。
    """
    return service.get_user(session, user_id)


@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"model": ErrorOut, "description": "用户名已存在（与服务器当前状态冲突）"},
        422: {"model": ErrorOut, "description": "请求体没通过校验（统一后的自定义结构）"},
    },
)
def create_user(
    payload: UserCreate,
    response: Response,
    session: Session = Depends(get_session),
) -> UserOut:
    """新增用户。客户端 POST 一段 JSON，FastAPI 用 UserCreate 校验后交给 payload。

    参数取值规则（对照 main.py 顶部那张表）：
      · payload: UserCreate          → 类型是 Pydantic 模型 → 从请求体取值；
      · response: Response           → 框架注入，用来回写 Location 头；
      · session: Session = Depends() → 框架注入，一个请求一个 Session。

    与 create_todo 同一套路：id 由数据库自增列生成；username 撞名的 409 判断
    下沉到 service 层；Location 头从 service 返回的 UserOut 里拿 id —— 拿到的
    已经是 Schema 对象，created.id 是个普通 int，不会因 session 关闭而失效。
    """
    created = service.create_user(session, payload)
    response.headers["Location"] = f"/api/users/{created.id}"
    return created


@router.patch(
    "/{user_id}",
    response_model=UserOut,
    responses={
        400: {"model": ErrorOut, "description": "请求体里没有任何要改的字段"},
        404: {"model": ErrorOut, "description": "用户不存在"},
        409: {"model": ErrorOut, "description": "新用户名和别的用户重复"},
    },
)
def update_user(
    user_id: int,
    payload: UserUpdate,
    session: Session = Depends(get_session),
) -> UserOut:
    """部分更新（PATCH）：可改 username / email，至少给一个字段。

    三类错误（400/404/409）全部由 service 层 raise，router 不写一处 if：
      · 400 —— payload 一个字段都没传（exclude_unset 后为空）；
      · 404 —— user_id 不存在；
      · 409 —— 新 username 和别的用户重复（改自己其他字段不会误撞，service 排除了自己）。
    email 传 null 表示清空邮箱（ORM 列可空）。
    """
    return service.update_user(session, user_id, payload)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorOut, "description": "用户不存在"}},
)
def delete_user(user_id: int, session: Session = Depends(get_session)) -> None:
    """删除用户，成功返回 204 No Content。

    删用户不会丢待办：owner_id 外键设了 ondelete="SET NULL"，MySQL 自动把该用户
    名下 todos 的 owner_id 置 NULL，待办变"无主"保留（详见 service.delete_user 注释）。
    幂等性：同一个 id 再 DELETE 一次会变成 404（已不存在）。
    """
    service.delete_user(session, user_id)
