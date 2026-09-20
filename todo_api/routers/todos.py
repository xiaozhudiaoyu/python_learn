# 路由模块：/api/todos —— 待办清单接口（Day 19 · 数据库版）。
#
# 与起步版（内存 list）最大的区别：数据读写全部下沉到 service 层，
# 这个文件只剩下"接收 HTTP 请求 → 调 service → 返回 Schema"三件事。
# 通读一遍你会发现每个函数体都短得离谱 —— 这正是分层的意义：
# router 薄到"换个数据库也不用动它"，业务复杂度被 service / dao 吸收掉了。
#
# ── Day 19 的三层调用链 ─────────────────────────────────────────────────
#   HTTP 请求
#     ↓
#   router（本文件）     只管：取参数、调 service、回响应。不碰 ORM、不碰事务。
#     ↓
#   service.py           只管：业务规则（409/400/404）、事务边界、ORM ↔ Schema 转换。
#     ↓
#   day16_crud.dao       只管：select / insert / update / delete。不含业务判断、不 commit。
#     ↓
#   day15_orm.models     只管：表结构映射。
#
# ── Session 从哪来？─────────────────────────────────────────────────────
# 每个接口签名里多了一个 `session: Session = Depends(get_session)`。
# 这是 Day 11 讲过的依赖注入：FastAPI 看到 Depends(get_session)，
# 会在调用本函数【之前】先执行 get_session（一个 yield 生成器），
# 把 yield 出来的 Session 对象塞进 session 参数；
# 本函数返回【之后】，FastAPI 再回到 get_session 的 yield 之后那段，
# 执行 finally 里的 session.close()。一个请求一个 Session，自动借自动还。
#
# 注意 session 参数【不是】客户端要传的字段 —— Swagger 文档里不会多出
# 一个叫 session 的表单输入框。FastAPI 认得 Session 这个类型 + Depends 的组合，
# 知道它是"框架注入"而不是"请求参数"（对照 main.py 顶部的参数取值规则表）。

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from todo_api import service
from todo_api.db import get_session
from todo_api.schemas import ErrorOut, TaskCreate, TaskOut, TaskUpdate

# 定义本模块的路由：统一前缀 /api/todos；tags 会在 Swagger 文档里作为分组标题显示。
router = APIRouter(prefix="/api/todos", tags=["todos"])


@router.get("")
def list_todos(
    done: bool | None = None,
    session: Session = Depends(get_session),
) -> list[TaskOut]:
    """返回全部任务，可按完成状态过滤。

    Day 13 的查询参数 done 原样保留：
      · 不传        → 返回全部
      · ?done=true  → 只返回已完成的
      · ?done=false → 只返回未完成的

    Day 19 的变化只在函数体：原来是对内存 list 做列表推导，
    现在是一行 service.list_todos(session, done=done)。
    返回类型 list[TaskOut] 没变 —— 对客户端来说，接口契约完全兼容，
    前端代码一行都不用改。这就是"分离"带来的好处：内部重构不外溢。
    """
    return service.list_todos(session, done=done)


@router.post(
    "/reset",
    response_model=list[TaskOut],
    status_code=status.HTTP_200_OK,
)
def reset_todos(session: Session = Depends(get_session)) -> list[TaskOut]:
    """清空 todos 表，返回空列表。

    Day 19 语义调整（与内存版的区别）：
      内存版是"恢复初始 3 条种子数据"；数据库版改成"清空所有 todo"。
      原因：数据库里 todo 可能已经和 user/tag 建立了关联，
      硬塞回固定种子数据会和外键关系打架；清空调用方自己再 POST 几条更诚实。
      需要种子数据请走 Alembic 迁移或独立的 seed 脚本，不混在接口里。

    为什么用 POST 而不是 GET？（这条没变）
      重置会修改服务器状态（幂等但非安全），GET 语义上不该有副作用；
      POST 表示"执行一个动作"，符合 REST 对"非 CRUD 操作"的常见处理方式。
    """
    return service.reset_todos(session)


@router.get(
    "/{todo_id}",
    responses={404: {"model": ErrorOut, "description": "任务不存在（统一错误结构，见 /docs）"}},
)
def get_todo(todo_id: int, session: Session = Depends(get_session)) -> TaskOut:
    """按编号返回单个任务：/api/todos/2。

    路径参数 todo_id 的取值/校验/文档生成规则和起步版完全一样（见 main.py 顶部说明），
    Day 19 只是把"在内存 list 里 for 循环找"换成了"service 调 dao 调 session.get"。
    404 的处理也没变：service 层抛 TodoNotFoundError，由 exceptions.py 的 handler
    统一翻译成 {code, message, details} 结构 —— router 里一行错误处理都不用写。
    """
    return service.get_todo(session, todo_id)


@router.post(
    "",
    response_model=TaskOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"model": ErrorOut, "description": "内容已存在（与服务器当前状态冲突）"},
        422: {"model": ErrorOut, "description": "请求体没通过校验（统一后的自定义结构）"},
    },
)
def create_todo(
    payload: TaskCreate,
    response: Response,
    session: Session = Depends(get_session),
) -> TaskOut:
    """新增任务。客户端 POST 一段 JSON，FastAPI 用 TaskCreate 校验后交给 payload。

    参数取值规则（对照 main.py 顶部那张表）：
      · payload: TaskCreate          → 类型是 Pydantic 模型 → 从请求体取值；
      · response: Response           → 框架注入，用来回写 Location 头；
      · session: Session = Depends() → 框架注入，一个请求一个 Session。
    三个参数来源各不相同，但函数签名里并排写着，FastAPI 靠"类型 + 默认值"自动分辨。

    Day 19 的变化：
      · 不再自己算 new_id（内存版是 max(id)+1），id 由数据库自增列生成；
      · 不再自己检查重名，409 判断下沉到 service 层；
      · Location 头照写，但 id 从 service 返回的 TaskOut 里拿 ——
        注意这里拿到的已经是 Schema 对象而不是 ORM 对象，created.id 就是个普通 int，
        不会因为 session 关闭而失效。这正是"分离"在细节处的体现。
    """
    created = service.create_todo(session, payload)
    response.headers["Location"] = f"/api/todos/{created.id}"
    return created


@router.patch(
    "/{todo_id}",
    response_model=TaskOut,
    responses={
        400: {"model": ErrorOut, "description": "请求体里没有任何要改的字段"},
        404: {"model": ErrorOut, "description": "任务不存在"},
        409: {"model": ErrorOut, "description": "新内容和别的任务重名"},
    },
)
def update_todo(
    todo_id: int,
    payload: TaskUpdate,
    session: Session = Depends(get_session),
) -> TaskOut:
    """部分更新（PATCH）。

    三类错误（400/404/409）全部由 service 层 raise，router 不写一处 if：
      · 400 —— payload 一个字段都没传（exclude_unset 后为空）；
      · 404 —— todo_id 不存在；
      · 409 —— 新 content 和别的任务重名。
    起步版里这些判断散落在函数体各处，现在集中到 service，router 只剩一行调用。
    将来要加"优先级不能超出范围"之类的新规则，也只动 service，router 不碰。
    """
    return service.update_todo(session, todo_id, payload)


@router.delete(
    "/{todo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorOut, "description": "任务不存在"}},
)
def delete_todo(todo_id: int, session: Session = Depends(get_session)) -> None:
    """删除任务，成功返回 204 No Content。

    204 的三条细节（与起步版一致）：
      · 不写 response_model，函数返回 None，只发一个空 body；
      · 204 语义上不允许带响应体，成功与否看状态行，不能靠解析 JSON；
      · 前端拿到 204 应该直接刷新列表，而不是尝试 JSON.parse("")。
    幂等性：同一个 id 再 DELETE 一次会变成 404（已不存在）。
    """
    service.delete_todo(session, todo_id)
