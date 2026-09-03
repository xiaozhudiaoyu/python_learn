# 路由模块：/api/todos —— 待办清单接口（起步版，数据先放内存 list）。
#
# 起步阶段不接数据库（那是第三阶段 SQLAlchemy 的事），先用一个模块级列表演示"接口层"。
# 第三阶段接入数据库后，这个文件仍然只管"接收请求、返回响应"，数据读写会交给独立的模型/仓储层。

from fastapi import APIRouter, HTTPException

# 定义本模块的路由：统一前缀 /api/todos；tags 会在 Swagger 文档里作为分组标题显示。
router = APIRouter(prefix="/api/todos", tags=["todos"])

# 起步用的内存数据（dict 列表即可，FastAPI 会自动序列化成 JSON）
_FAKE_TODOS: list[dict[str, object]] = [
    {"id": 1, "content": "学习 HTTP 基础", "done": True},
    {"id": 2, "content": "跑通 FastAPI 起步", "done": False},
    {"id": 3, "content": "预习 SQLAlchemy", "done": False},
]


@router.get("")
def list_todos() -> list[dict[str, object]]:
    """返回全部任务。HTTP 方法默认就是 GET，对应路径 /api/todos。"""
    return _FAKE_TODOS


@router.get("/{todo_id}")
def get_todo(todo_id: int) -> dict[str, object]:
    """按编号返回单个任务，演示【路径参数】：/api/todos/2。

    路径里的 {todo_id} 会自动绑定到同名函数参数；声明成 int，
    FastAPI 会帮忙做类型转换（/api/todos/abc 会被自动判为 422 校验错误）。
    """
    for todo in _FAKE_TODOS:
        if todo["id"] == todo_id:
            return todo
    # 抛 HTTPException 会得到一个带状态码的 JSON 错误响应；这里用 404 表示"资源不存在"。
    raise HTTPException(status_code=404, detail=f"没有找到编号为 {todo_id} 的任务")
