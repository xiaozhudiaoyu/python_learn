# Pydantic 数据模型层：定义接口"收什么、发什么"的结构与校验规则。
#
# 为什么单独一个文件、且叫 schemas 不叫 models？
#   · 与"路由文件"分开是 FastAPI 的常见分层：schemas 只管"数据长什么样"，routers 只管"收发请求"；
#   · 第三阶段 SQLAlchemy 的"数据库模型"通常占用 models.py 这个名字，这里用 schemas.py 避免混淆。
#
# 与你第一阶段写的 "todolist pydantic.py" 是同一套 BaseModel 语法，
# 区别只是：这次由 FastAPI 在【运行时】自动调用它来校验请求 / 序列化响应。

from pydantic import BaseModel, Field


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
