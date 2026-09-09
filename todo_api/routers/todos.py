# 路由模块：/api/todos —— 待办清单接口（起步版，数据先放内存 list）。
#
# 起步阶段不接数据库（那是第三阶段 SQLAlchemy 的事），先用一个模块级列表演示"接口层"。
# 第三阶段接入数据库后，这个文件仍然只管"接收请求、返回响应"，数据读写会交给独立的模型/仓储层。

from fastapi import APIRouter, Response, status

from todo_api.exceptions import NothingToUpdateError, TodoConflictError, TodoNotFoundError
from todo_api.schemas import ErrorOut, TaskCreate, TaskOut, TaskUpdate

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


def _find_todo(todo_id: int) -> dict[str, object]:
    """Day 12 抽出来的小助手：找不到就抛领域异常，调用处一行都不写错误处理。

    这就是"用异常代替返回错误值"的直接好处：三个接口都要按 id 找任务，
    找不到的处理只写在这一个 raise 上，状态码 404 由异常类自己带、响应结构由 handler 统一决定。
    （对比原来：每个接口都得自己 for 循环 + raise HTTPException(404, ...)。）
    """
    for todo in _FAKE_TODOS:
        if todo["id"] == todo_id:
            return todo
    raise TodoNotFoundError(todo_id)


@router.get(
    "/{todo_id}",                          # ① 路径里的 {todo_id} 声明了"这是个路径参数"
    responses={404: {"model": ErrorOut, "description": "任务不存在（统一错误结构，见 /docs）"}},
)
def get_todo(todo_id: int) -> TaskOut:     # ② 参数名对上路径占位符，自动取值
    """按编号返回单个任务，演示【路径参数】：/api/todos/2。

    类型注解 todo_id: int 是 FastAPI 的精髓，一份注解同时干三件事：
      1) 取值来源——名字在路径 {todo_id} 里，故按"路径参数"取值；
      2) 运行时转换 + 校验——URL 里的 "2" 自动转成整数 2；转不了(如 /api/todos/abc)直接返回 422；
      3) 自动生成文档——/docs 里会标注该参数的类型。
    更强校验可写：todo_id: int = Path(..., ge=1)（需 from fastapi import Path）。

    Day 12 变化：函数体里不再自己拼 404，只需 _find_todo()；
    能走到 return 这一行，说明任务一定存在。错误响应长什么样，去 /docs 看 404 那一档。
    """
    return TaskOut.model_validate(_find_todo(todo_id))


@router.post(
    "",
    response_model=TaskOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"model": ErrorOut, "description": "内容已存在（与服务器当前状态冲突）"},
        422: {"model": ErrorOut, "description": "请求体没通过校验（统一后的自定义结构）"},
    },
)
def create_todo(payload: TaskCreate, response: Response) -> TaskOut:
    """演示【请求体】：客户端 POST 一段 JSON，FastAPI 用 TaskCreate 校验后交给 payload。

    语法要点（对照 main.py 里那张“参数取值来源”规则表）：
      · payload: TaskCreate —— 参数类型是 Pydantic 模型 → 从“请求体 body”取值，不是路径/查询；
      · 校验由 TaskCreate 里的 Field 规则完成：content 为空串/超长、缺字段等，直接返回 422，不会进函数体；
      · response_model=TaskOut —— 返回值按 TaskOut 结构序列化，顺带过滤掉多余字段；
      · status_code=201 —— “创建成功”的标准状态码（默认是 200）。

    Day 12 新增两处：
      · response: Response —— 框架注入的“响应对象”，用它回写 Location 头。
        201 的规范动作是同时告诉客户端新资源在哪，前端可以直接拿这个 URL 再 GET 一次；
        它不是接口参数，Swagger 里不会多出一个叫 response 的表单字段。
      · 重名 → raise TodoConflictError → 409：格式完全合法、只是和现有数据冲突，
        这种错误不能归给 422（见 exceptions.py 里对 409/422 区别的解释）。
      · responses={...} —— 只影响文档，不影响运行时行为：写上去，/docs 里每个接口
        就会多出一档可展开的错误响应示例。
        注意 422 这一档：接口一带请求体，FastAPI 就自动在文档里补一个 422（默认指向
        HTTPValidationError）；这里显式写 422 是为了把它覆盖成我们自己的 ErrorOut。
    """
    if any(todo["content"] == payload.content for todo in _FAKE_TODOS):
        raise TodoConflictError(payload.content)

    # 取最大 id + 1（Day 12 加了 DELETE 后，不能再靠 len()+1 了：
    # 一旦删掉最后一条，len()+1 就会和现有 id 撞上，产生两条同号的任务）
    new_id = max((int(str(todo["id"])) for todo in _FAKE_TODOS), default=0) + 1
    created = {"id": new_id, "content": payload.content, "done": payload.done}
    _FAKE_TODOS.append(created)

    response.headers["Location"] = f"/api/todos/{new_id}"
    return TaskOut.model_validate(created)


@router.patch(
    "/{todo_id}",
    response_model=TaskOut,
    responses={
        400: {"model": ErrorOut, "description": "请求体里没有任何要改的字段"},
        404: {"model": ErrorOut, "description": "任务不存在"},
        409: {"model": ErrorOut, "description": "新内容和别的任务重名"},
    },
)
def update_todo(todo_id: int, payload: TaskUpdate) -> TaskOut:
    """演示【部分更新 PATCH】与 400。

    语法要点：
      · payload: TaskUpdate —— 依然是"类型是 Pydantic 模型 → 从 body 取值"，两个字段都可省；
      · model_dump(exclude_unset=True) —— 只拿客户端真正传了的字段，这是 PATCH 语义的关键；
      · HTTP 方法不自动推断：@router.patch 就是 PATCH，路径可以和 GET /{todo_id} 一样，
        因为 FastAPI 是按"方法 + 路径"组合匹配路由的。

    错误全部靠 raise：400（空改）/ 404（不存在）/ 409（重名），
    函数体里没有一处 "return 错误体" —— 这正是 Day 12 要体会的清爽感。
    """
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        raise NothingToUpdateError(sorted(TaskUpdate.model_fields))

    todo = _find_todo(todo_id)
    new_content = fields.get("content")
    if (
        new_content is not None
        and new_content != todo["content"]
        and any(other["content"] == new_content for other in _FAKE_TODOS)
    ):
        raise TodoConflictError(str(new_content))

    todo.update(fields)
    return TaskOut.model_validate(todo)


@router.delete(
    "/{todo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorOut, "description": "任务不存在"}},
)
def delete_todo(todo_id: int) -> None:
    """演示【204 No Content】：删成功但没什么可返回的。

    三条要一起记住的细节（少一条就不规范）：
      · 不写 response_model，函数也不 return 任何东西（-> None），只发一个空 body；
      · 204 语义上不允许带响应体，所以状态码得靠状态行看，不能靠解析 JSON 判断成功；
      · 前端拿到 204 应该直接去刷新列表，而不是尝试 JSON.parse("")。
    幂等性小常识：同一个 id 再 DELETE 一次就变成 404（已不存在），而 PUT 重复调仍是那个结果。
    """
    _FAKE_TODOS.remove(_find_todo(todo_id))
