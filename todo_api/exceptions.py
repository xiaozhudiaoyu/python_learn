# Day 12 · 异常处理：把"出错"也变成接口契约的一部分。
#
# 为什么用 raise，而不是 return 一个错误 dict？
#   1) 正常路径不被打断：函数体里只在出事的地方多一行 raise，不用层层 if 判断上一步成没成；
#   2) 错误结构只写一遍：所有接口共用这里的一个 handler，前端面对的错误格式是统一的；
#   3) 状态码集中管理：领域异常类自带 status_code，业务代码不用到处写 404 / 409；
#   4) 依赖里抛的异常也走这条路：Day 11 的 api_token 里 raise HTTPException，
#      最终也是被这里的 handler 加工后才发出去的 —— 一处改动，全站生效。
#
# FastAPI 的错误其实分三条路，所以要配三个 handler（本文件就这三块）：
#   ① RequestValidationError → 参数/请求体没过 Pydantic 校验（默认就是 422）
#   ② HTTPException         → 明确的 HTTP 语义错误；含路由不存在时的 404、方法不对时的 405
#   ③ 其余 Exception         → 程序 bug，兜底成 500，绝不把堆栈泄露给客户端
#   另加一类：④ 我们自己的 AppError（业务/领域异常），单独注册，语义最清楚。
#
# 派发规则：按"异常类型 → 最近的已注册 handler"匹配（沿继承链找），
# 所以注册 Starlette 的 HTTPException 就能同时兜住 FastAPI.HTTPException（它是子类），
# 也和"每个接口自己 try/except 再拼 JSON"彻底说再见。

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("todo_api.exceptions")


# ── ④ 领域异常：业务层只管抛，不用懂 HTTP ────────────────────────────
class AppError(Exception):
    """业务异常基类。子类只需声明三个类属性，报错信息就自带语义。"""

    status_code: int = status.HTTP_400_BAD_REQUEST  # 该错误对应的 HTTP 状态码
    code: str = "app_error"                         # 稳定的机器可读错误码（给前端判断用）
    default_message: str = "请求无法被处理"          # 没传 message 时用的兜底文案

    def __init__(
        self,
        message: str | None = None,
        details: list[dict[str, str]] | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.details = details or []
        super().__init__(self.message)


class TodoNotFoundError(AppError):
    """404：资源不存在。把 id 拼进文案，比"not found"对调试友好得多。"""

    status_code = status.HTTP_404_NOT_FOUND
    code = "todo_not_found"
    default_message = "任务不存在"

    def __init__(self, todo_id: int) -> None:
        super().__init__(
            f"没有找到编号为 {todo_id} 的任务",
            details=[{"field": "path.todo_id", "type": "not_found", "message": f"{todo_id} 不在数据中"}],
        )


class TodoConflictError(AppError):
    """409：请求本身合法，但和现有数据冲突（这里演示"内容重复"）。

    409 vs 422 的区别是高频疑问：
      422 = 这串 JSON 本身就不合格式（超长、缺字段），换成谁都会失败；
      409 = 格式没问题，只是和当前服务器状态打架（重名、已被占用），换个时机可能就成功了。
    """

    status_code = status.HTTP_409_CONFLICT
    code = "todo_conflict"
    default_message = "与已有数据冲突"

    def __init__(self, content: str) -> None:
        super().__init__(
            f"已存在同名任务：{content}",
            details=[{"field": "body.content", "type": "duplicate", "message": "内容重复，换一个或先删掉旧的"}],
        )


class NothingToUpdateError(AppError):
    """400：PATCH 传了空对象（什么都没要改）。

    这类"参数格式没错、但业务上没意义"的输入，用 400 比硬凑 422 更贴切。
    """

    status_code = status.HTTP_400_BAD_REQUEST
    code = "nothing_to_update"

    def __init__(self, allowed: list[str]) -> None:
        super().__init__(
            "PATCH 请求体里至少要有一个字段",
            details=[{"field": "body", "type": "empty", "message": f"可更新字段：{', '.join(allowed)}"}],
        )


# ── Day 20 新增：User 实体的领域异常 ──────────────────────────────
# 与 Todo 异常同一套机制（继承 AppError，自带 status_code/code），
# 不复用 TodoNotFoundError 是因为错误码与文案都是"任务"语境，
# 用在用户身上会误导前端（code 是给程序判断的，必须语义准确）。
class UserNotFoundError(AppError):
    """404：用户不存在。"""

    status_code = status.HTTP_404_NOT_FOUND
    code = "user_not_found"
    default_message = "用户不存在"

    def __init__(self, user_id: int) -> None:
        super().__init__(
            f"没有找到编号为 {user_id} 的用户",
            details=[{"field": "path.user_id", "type": "not_found", "message": f"{user_id} 不在数据中"}],
        )


class UserConflictError(AppError):
    """409：用户名已存在（username 列有数据库唯一索引，见 day15_orm/models.py）。

    与 TodoConflictError 的区别：username 重复是"数据完整性"问题，
    数据库层建了唯一索引兜底；应用层这道检查只是为了返回友好的 409
    而不是难看的 500（IntegrityError）。两层都要有，职责不同。
    """

    status_code = status.HTTP_409_CONFLICT
    code = "user_conflict"
    default_message = "用户名已存在"

    def __init__(self, username: str) -> None:
        super().__init__(
            f"用户名已被占用：{username}",
            details=[{"field": "body.username", "type": "duplicate", "message": "换一个用户名"}],
        )


# HTTPException 的状态码 → 机器可读码。没列出来的自动退化成 http_418 这种形式。
_HTTP_CODE_MAP: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "bad_request",
    status.HTTP_401_UNAUTHORIZED: "unauthorized",
    status.HTTP_403_FORBIDDEN: "forbidden",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
    status.HTTP_409_CONFLICT: "conflict",
    status.HTTP_422_UNPROCESSABLE_CONTENT: "unprocessable_entity",
}


def _field_name(loc: tuple[Any, ...], err_type: str) -> str:
    """把 ("body", "contnet") 这种元组翻译成前端能直接用的字段路径。

    两条经验：
      · 第一个元素永远是 body/query/path/header 这种"位置"，对前端没用，去掉；
      · type=json_invalid 时 Starlette 会在末尾塞一个"出错处的字符偏移量"（整数），
        它不是数组下标，展示成 body[37] 反而误导，归到 body 更诚实。
      · 真正的数组下标（如 items.2.name 里的 2）保留，写成 items[2].name。
    """
    parts: list[Any] = list(loc[1:] or loc[:1])
    if err_type == "json_invalid" and parts and isinstance(parts[-1], int):
        parts = parts[:-1] or ["body"]
    rendered = "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in parts)
    return rendered.lstrip(".") or "body"


def _error_json(
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, str]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """四个 handler 共用的出口：保证所有错误的 JSON 形状都是 schemas.ErrorOut 那一套。"""
    return JSONResponse(
        status_code=status_code,
        content={"code": code, "message": message, "details": details or []},
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """在 main.py 里调用一次，全站错误处理就位。

    为什么写成函数、而不是直接在模块里写 @app.exception_handler？
      app 对象在 main.py 里才创建；写成函数能让"错误策略"独立成块，
      将来加子应用 / 换 app 实例，一句话就能复用同一套处理。
    """

    # ── ① 校验错误（422）：框架默认结构对前端不友好，这里定制 ──────────
    @app.exception_handler(RequestValidationError)
    async def on_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        """把 Pydantic 的报错翻译成 {field, type, message} 列表。

        默认结构长这样：[{"loc": ["query", "limit"], "msg": "...", "ctx": {...}, "type": "..."}]
        三个问题：loc 是数组、多了 "body"/"query" 这种噪音前缀、还带一个可能塞了 Python
        异常对象的 ctx 字段（既没必要也可能序列化炸掉）。这里统一削平成前端能直接用的形状。
        """
        details = [
            {
                "field": _field_name(err.get("loc", ()), str(err.get("type", ""))),
                "type": str(err.get("type", "invalid")),
                "message": str(err.get("msg", "取值不合法")),
            }
            for err in exc.errors()
        ]
        logger.info("校验失败 %s %s -> %s", request.method, request.url.path, details)
        return _error_json(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "validation_error",
            f"{len(details)} 处参数不符合要求，详见 details",
            details,
        )

    # ── ② HTTPException（含框架自己抛的 404 / 405）─────────────────────
    @app.exception_handler(StarletteHTTPException)
    async def on_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """兼容旧写法：代码里 raise HTTPException 照样能用，只是出口统一了。

        注意 exc.headers 必须回传，否则 Day 11 那个 401 的 WWW-Authenticate 头会丢掉
        —— 客户端据此判断该弹登录框还是该提示权限不足，丢了就是行为退化。
        """
        return _error_json(
            exc.status_code,
            _HTTP_CODE_MAP.get(exc.status_code, f"http_{exc.status_code}"),
            str(exc.detail),
            headers=getattr(exc, "headers", None),
        )

    # ── ③ 领域异常：把我们自己抛的 AppError 翻译成 HTTP 响应 ───────────
    @app.exception_handler(AppError)
    async def on_app_error(request: Request, exc: AppError) -> JSONResponse:
        logger.info("业务异常 %s %s -> %s", request.method, request.url.path, exc.code)
        return _error_json(exc.status_code, exc.code, exc.message, exc.details)

    # ── ④ 兜底：程序 bug（500），宁可含糊也不能泄露 ────────────────────
    @app.exception_handler(Exception)
    async def on_unhandled(request: Request, exc: Exception) -> JSONResponse:
        """没被上面三类接住的异常都到这。真实项目这里要：记完整堆栈 + 报警 + 返回 trace id。

        两条必须知道的细节：
          1) 响应会正常发给客户端，但 Starlette 处理完仍会把原异常继续往上抛给服务器，
             所以 uvicorn 控制台照样会打印 traceback —— 那是给开发看的，不是泄露。
          2) 只有 debug=False（默认）才走这个 handler；uvicorn 开 --debug 时，
             客户端会直接收到 HTML 版堆栈页面。本地排错方便，线上绝对不能开。
        """
        logger.exception("未处理异常 %s %s", request.method, request.url.path)
        return _error_json(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_error",
            "服务端内部错误，已记录日志（客户端信息到此为止，堆栈不外泄）",
        )
