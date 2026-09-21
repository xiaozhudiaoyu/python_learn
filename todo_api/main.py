# FastAPI 应用入口：创建 app、挂载各业务路由，作为 uvicorn 的启动目标。
#
# 启动（在项目根目录 e:/python_learn 下运行；只监听本机 127.0.0.1）：
#     .\.venv\Scripts\python.exe -m uvicorn todo_api.main:app --reload
#
# 启动后浏览器打开下面地址，就是 FastAPI 自动生成的交互式接口文档（Swagger）：
#     http://127.0.0.1:8000/docs
# 在文档里点每个接口的 "Try it out" → "Execute"，就能直接在浏览器里发 HTTP 请求、看响应，
# 这正好对应 Day 8 要体会的"请求 / 响应 / 方法 / 状态码"。
#
# ── FastAPI 语法心智模型（速查，配合各 router 文件一起看）─────────────
# 一句话：写"普通 Python 函数 + 类型注解"，框架靠【装饰器】把函数变成 HTTP 接口，
#   再靠【类型注解】在运行时自动完成 取参数 → 校验 → 序列化 → 生成文档，几乎不写胶水代码。
#   （同一份类型注解：第一阶段是给 Pyright 静态检查看，这里是 FastAPI 在运行时消费它。）
#
# 看懂任意接口的三步：
#   @app.get("/path")        # ① 装饰器 = HTTP 方法 + 路径
#   def handler(x: int):     # ② 函数体 = 处理逻辑；参数 = 从请求取值的来源
#       return {...}         # ③ 返回值 = 响应体，自动转 JSON
#
# 【核心】函数参数"从请求哪里取值"，只由"它在不在路径里 + 它的类型"决定，无需额外配置：
#   · 名字出现在路径 {x} 里            → 路径参数    （见 routers/todos.py 的 todo_id）
#   · 标量(int/str/bool)且不在路径里   → 查询参数    （见 routers/users.py 的 limit）
#   · 参数类型是 Pydantic BaseModel    → 请求体 body （见 routers/todos.py 的 payload，Day 10）
#   · 注解是 Request/Response/Depends  → 框架注入    （Depends 见 deps.py，Day 11）
#
# async def 还是 def？—— 调异步库(要 await)用 async def；调同步阻塞库(requests、多数 DB 驱动)
#   用普通 def，FastAPI 会自动丢进线程池跑、不卡事件循环。起步用 def 足够，切忌在 async def 里写阻塞调用。
#
# 最小可运行模板：
#   from fastapi import FastAPI
#   app = FastAPI()
#   @app.get("/items/{item_id}")
#   def read_item(item_id: int, q: str | None = None):   # 路径参数 + 可选查询参数
#       return {"item_id": item_id, "q": q}
# ──────────────────────────────────────────────────────────────

from fastapi import Depends, FastAPI

from todo_api.deps import request_timer
from todo_api.exceptions import register_exception_handlers
from todo_api.routers import depends_demo, errors, todos, users

# OpenAPI 文档元信息（Day 12）：给文档里的每个分组配一句"人话简介"。
# 注意 name 必须和各 router 里写的 tags 一字不差（含中间点 ·），对不上就不会显示说明。
_TAGS_METADATA = [
    {"name": "todos", "description": "待办清单主业务接口（Day 9~13 起步、Day 19 接入数据库），增删改查 + 查询过滤 + 清空重置，完整错误响应。"},
    {"name": "users", "description": "用户接口（Day 9 查询参数示例、Day 20 接入数据库），增删改查 + limit 过滤，username 唯一冲突返回 409。"},
    {"name": "Day11 · Depends 依赖注入", "description": "依赖树 / yield 收尾 / 登录态链 / 依赖覆盖的演示集合。"},
    {"name": "Day12 · 异常与错误响应", "description": "故意出错的教学样本：400/401/404/405/409/422/500 一次看全。"},
]

# 创建应用实例。命令里的 "todo_api.main:app" 指的就是这个名为 app 的变量。
# Day 11 新增 dependencies=[...]：【应用级依赖】，对全站所有接口统一生效；
# request_timer 返回 None，不会往任何接口注入参数，只负责在服务端记一行耗时日志。
app = FastAPI(
    title="Todo API（Day 19 · 数据库版）",
    version="0.2.0",
    dependencies=[Depends(request_timer)],
    description=(
        "学习用项目。Day 19 起 /api/todos 接入 MySQL（SQLAlchemy 2.0 + PyMySQL），"
        "Day 20 起 /api/users 也接入数据库并补全增删改查；"
        "接口模型（Pydantic Schema）与 ORM 模型（SQLAlchemy Model）严格分离。"
        "错误响应统一为 {code, message, details} 结构，见各接口的 Responses 区。\n\n"
        "启动前请确认：① MySQL 服务已运行；② 已执行 `alembic upgrade head` 建好表结构"
        "（本应用启动时【不会】自动 create_all，建表/改表一律走 Alembic 迁移，见 Day 18）。"
    ),
    openapi_tags=_TAGS_METADATA,
)

# Day 12：注册全站错误处理（必须在 app 创建之后、路由生效之前调用）。
# 四类异常（校验错 / HTTPException / 领域异常 / 其他 bug）全部在 exceptions.py 里集中定义。
register_exception_handlers(app)

# 三个文档地址都是免费生成的（Day 12 "用 OpenAPI 文档验证接口"就用它们）：
#   /docs         Swagger UI：能直接发请求，本项目主要用它
#   /redoc        ReDoc：只读版，左侧目录右侧说明，通读长文档更舒服
#   /openapi.json 机器可读的接口描述原文（第四阶段前端可用它自动生成 TS 类型）
# app = FastAPI(title="...", version="0.1.0", docs_url="/api-docs")   # 文档地址变 http://127.0.0.1:8000/api-docs
# docs_url=None 可直接关掉文档

# 把子路由"挂"到主应用上；它们各自带 /api/todos、/api/users、/api/depends、/api/errors 前缀。
app.include_router(todos.router)
app.include_router(users.router)
app.include_router(depends_demo.router)   # Day 11：Depends 演示接口
app.include_router(errors.router)         # Day 12：错误场景集锦


@app.get("/")
def root() -> dict[str, str]:
    """根路径健康检查，用来确认服务确实跑起来了。"""
    return {"message": "Todo API 已启动，访问 /docs 查看接口文档"}
