# 路由模块：/api/todos —— 待办清单接口（起步版，数据先放内存 list）。
#
# 起步阶段不接数据库（那是第三阶段 SQLAlchemy 的事），先用一个模块级列表演示"接口层"。
# 第三阶段接入数据库后，这个文件仍然只管"接收请求、返回响应"，数据读写会交给独立的模型/仓储层。

from fastapi import APIRouter, HTTPException, status

from todo_api.schemas import TaskCreate, TaskOut

# 定义本模块的路由：统一前缀 /api/todos；tags 会在 Swagger 文档里作为分组标题显示。
router = APIRouter(prefix="/api/todos", tags=["todos"])

# 起步用的内存数据（dict 列表即可，FastAPI 会自动序列化成 JSON）
_FAKE_TODOS: list[dict[str, object]] = [
    {"id": 1, "content": "学习 HTTP 基础", "done": True},
    {"id": 2, "content": "跑通 FastAPI 起步", "done": False},
    {"id": 3, "content": "预习 SQLAlchemy", "done": False},
]


@router.get("")                          # ① 装饰器：GET 方法 + 路径（prefix + "" = /api/todos）
def list_todos() -> list[dict[str, object]]:
    """返回全部任务。HTTP 方法默认就是 GET，对应路径 /api/todos。"""
    # ③ 返回值即响应体：直接 return 列表，FastAPI 自动序列化成 JSON 数组，不用手动 json.dumps
    return _FAKE_TODOS


@router.get("/{todo_id}")                 # ① 路径里的 {todo_id} 声明了"这是个路径参数"
def get_todo(todo_id: int) -> dict[str, object]:   # ② 参数名对上路径占位符，自动取值
    """按编号返回单个任务，演示【路径参数】：/api/todos/2。

    类型注解 todo_id: int 是 FastAPI 的精髓，一份注解同时干三件事：
      1) 取值来源——名字在路径 {todo_id} 里，故按"路径参数"取值；
      2) 运行时转换 + 校验——URL 里的 "2" 自动转成整数 2；转不了(如 /api/todos/abc)直接返回 422；
      3) 自动生成文档——/docs 里会标注该参数的类型。
    更强校验可写：todo_id: int = Path(..., ge=1)（需 from fastapi import Path）。
    """
    for todo in _FAKE_TODOS:
        if todo["id"] == todo_id:
            return todo
    # 抛 HTTPException 会得到一个带状态码的 JSON 错误响应（如 {"detail": ...}）；404 = 资源不存在。
    raise HTTPException(status_code=404, detail=f"没有找到编号为 {todo_id} 的任务")


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_todo(payload: TaskCreate) -> TaskOut:
    """演示【请求体】：客户端 POST 一段 JSON，FastAPI 用 TaskCreate 校验后交给 payload。

    语法要点（对照 main.py 里那张“参数取值来源”规则表）：
      · payload: TaskCreate —— 参数类型是 Pydantic 模型 → 从“请求体 body”取值，不是路径/查询；
      · 校验由 TaskCreate 里的 Field 规则完成：content 为空串/超长、缺字段等，直接返回 422，不会进函数体；
      · response_model=TaskOut —— 返回值按 TaskOut 结构序列化，顺带过滤掉多余字段；
      · status_code=201 —— “创建成功”的标准状态码（默认是 200）。
    """
    # 起步用“当前条数 + 1”生成 id（本项目只有新增、没删除，能保证唯一；
    # 第三阶段接入数据库后，主键由数据库自增，就不用手动编号了）
    new_id = len(_FAKE_TODOS) + 1
    _FAKE_TODOS.append({"id": new_id, "content": payload.content, "done": payload.done})
    return TaskOut(id=new_id, content=payload.content, done=payload.done)
