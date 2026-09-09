# Day 12 · 错误场景集锦：/api/errors —— 把各类错误一次演全，专门用来在 Swagger 里点。
#
# 正式接口（/api/todos）里的错误都是"顺手遇到"的；这里几个接口是"故意出错"的教学样本，
# 每个各代表 exceptions.py 里的一条路：领域异常 / 旧写法 HTTPException / 依赖里的 401 / 真 bug。
#
# 两种写法对照着看，才能体会 Day 12 的价值：
#   旧：接口里 raise HTTPException(status_code=404, detail="...")   → 响应体是 {"detail": "..."}
#   新：接口里 raise TodoNotFoundError(todo_id)                     → 状态码、错误码、结构全由框架侧决定
#   业务代码从"懂 HTTP"变成"只懂业务"，将来换 GraphQL / RPC，业务层几乎不用改。

from typing import Any

from fastapi import APIRouter, HTTPException, status

from todo_api.deps import CurrentUserDep
from todo_api.exceptions import TodoConflictError
from todo_api.schemas import ErrorOut

router = APIRouter(prefix="/api/errors", tags=["Day12 · 异常与错误响应"])


@router.get(
    "/bug",
    responses={
        500: {"model": ErrorOut, "description": "服务端 bug（兜底 handler 的统一结构，不含堆栈）"}
    },
)
def raise_bug() -> dict[str, Any]:
    """【兜底 500】故意写一行会崩的代码，看 exceptions.py 里第 ④ 个 handler 的效果。

    跑起来会看到：状态码 500，响应体 {"code": "internal_error", "message": "...", "details": []}，
    客户端拿不到任何堆栈、文件名、变量值；而服务端日志里 traceback 一条不少。
    这一条差别的意义：出错时对外"不泄露实现细节"是安全要求，不是风格偏好。
    """
    return {"结果": int("这行代码永远不会执行，因为字符串转不成整数")}


@router.get("/legacy")
def legacy_style() -> dict[str, Any]:
    """【旧写法对照】仍然 raise HTTPException，但出口已经是统一结构了。

      /api/errors/legacy           → 418，code="http_418"，结构和其它错误一致
      POST /api/errors/legacy      → 405，框架自己抛的错也被同一个 handler 兜住了
    也就是说：老代码不用一次性改完，先统一出口，再逐步换成领域异常。
    """
    raise HTTPException(status_code=status.HTTP_418_IM_A_TEAPOT, detail="旧写法：接口里直接抛 HTTPException")


@router.get("/conflict")
def conflict_style() -> dict[str, Any]:
    """【领域异常】409：不用先造出重复数据，也能演示冲突错误的完整响应。

    正式接口 /api/todos 的 POST 里就是同一句 raise，这里单独拎出来方便看结构。
    """
    raise TodoConflictError("学习 HTTP 基础")


@router.get("/needs-token")
def needs_token(user: CurrentUserDep) -> dict[str, Any]:
    """【依赖里的错误】复用 Day 11 的登录态依赖：无 X-Token → 401。

    重点不在 401 本身，而在于：依赖函数里抛的异常，接口代码没写一行 try/except，
    照样被同一个 handler 加工成统一结构，而且 WWW-Authenticate 响应头被完整保留
    （handler 里那句 headers=getattr(exc, "headers", None) 就是为这一刻准备的）。
    """
    return {"说明": f"能到这里说明依赖校验通过，当前用户 {user.name}"}
