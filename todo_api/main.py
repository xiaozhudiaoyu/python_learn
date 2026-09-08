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
from todo_api.routers import depends_demo, todos, users

# 创建应用实例。命令里的 "todo_api.main:app" 指的就是这个名为 app 的变量。
# Day 11 新增 dependencies=[...]：【应用级依赖】，对全站所有接口统一生效；
# request_timer 返回 None，不会往任何接口注入参数，只负责在服务端记一行耗时日志。
app = FastAPI(
    title="Todo API（第一阶段起步）",
    version="0.1.0",
    dependencies=[Depends(request_timer)],
)
# app = FastAPI(title="...", version="0.1.0", docs_url="/api-docs")   # 文档地址变 http://127.0.0.1:8000/api-docs
# docs_url=None 可直接关掉文档

# 把子路由"挂"到主应用上；它们各自带 /api/todos、/api/users、/api/depends 前缀。
app.include_router(todos.router)
app.include_router(users.router)
app.include_router(depends_demo.router)   # Day 11：Depends 演示接口


@app.get("/")
def root() -> dict[str, str]:
    """根路径健康检查，用来确认服务确实跑起来了。"""
    return {"message": "Todo API 已启动，访问 /docs 查看接口文档"}
