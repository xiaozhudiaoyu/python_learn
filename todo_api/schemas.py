# Pydantic 数据模型层：定义接口"收什么、发什么"的结构与校验规则。
#
# 为什么单独一个文件、且叫 schemas 不叫 models？
#   · 与"路由文件"分开是 FastAPI 的常见分层：schemas 只管"数据长什么样"，routers 只管"收发请求"；
#   · 第三阶段 SQLAlchemy 的"数据库模型"通常占用 models.py 这个名字，这里用 schemas.py 避免混淆。
#
# 与你第一阶段写的 "todolist pydantic.py" 是同一套 BaseModel 语法，
# 区别只是：这次由 FastAPI 在【运行时】自动调用它来校验请求 / 序列化响应。

from pydantic import BaseModel, ConfigDict, Field


class TaskCreate(BaseModel):
    """POST /api/todos 的【请求体】模型：客户端提交的 JSON 要满足这个结构。

    校验规则直接写在字段上，非法输入 FastAPI 会自动返回 422，业务代码里不用写一句 if。
    """

    content: str = Field(min_length=1, max_length=200, description="任务内容，1~200 字，不能为空")
    done: bool = Field(default=False, description="是否已完成，默认未完成")


class TaskOut(BaseModel):
    """响应体模型：接口返回给客户端的结构。

    路由上写 response_model=TaskOut 后，FastAPI 会按此模型序列化返回值，
    顺带把模型里没有的字段过滤掉，并在 /docs 里展示出来。
    """

    id: int
    content: str
    done: bool


# ── Day 12 新增：PATCH 的请求体 + 统一错误响应结构 ─────────────────────
class TaskUpdate(BaseModel):
    """PATCH /api/todos/{id} 的【请求体】：两个字段都可选，但至少要给一个。

    为什么用 None 而不用 False 当 done 的默认值？
      PATCH 是"部分更新"，必须分清"没传"和"传了 false"：
      默认 None = 没传 → 不改；传 false = 明确要改成未完成。
      靠 payload.model_dump(exclude_unset=True) 才能拿到"客户端真正传了哪些字段"。

    extra="forbid"：客户端多传一个拼错名字的字段（如 contnet）直接 422，
      不然是被静默丢弃的——这类"默默吃掉错误"的坑比报错更难查。
      （POST 的 TaskCreate 保持原样没动，等你想统一时再一起改。）
    """

    model_config = ConfigDict(extra="forbid")

    content: str | None = Field(default=None, min_length=1, max_length=200, description="新的任务内容")
    done: bool | None = Field(default=None, description="新的完成状态")


class FieldErrorOut(BaseModel):
    """【字段级】校验明细，只在校验类错误（422 / 400）里出现。"""

    field: str = Field(description="哪个位置、哪个字段出的问题，如 query.limit、body.content")
    type: str = Field(description="机器可读的错误类型，如 missing、string_too_short")
    message: str = Field(description="人话说明")


class ErrorOut(BaseModel):
    """统一错误响应结构：所有非 2xx 的 JSON body 都长这个样。

    为什么要统一？前端只写一段处理逻辑就能应对全部错误：
      按 code 分支处理（比如 code == "todo_conflict" 时提示"已存在"），
      按 message 兜底展示，按 details 把错误标到对应输入框上。
    路由上写 responses={404: {"model": ErrorOut}} 就能在 Swagger 里看到它。
    """

    code: str = Field(description="稳定的错误码，给程序判断用，别拿它当文案")
    message: str = Field(description="给人看的说明，可能随时改，不要用它做逻辑判断")
    details: list[FieldErrorOut] = Field(default_factory=list, description="字段级明细；没有则为空列表")
