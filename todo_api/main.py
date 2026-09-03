# FastAPI 应用入口：创建 app、挂载各业务路由，作为 uvicorn 的启动目标。
#
# 启动（在项目根目录 e:/python_learn 下运行；只监听本机 127.0.0.1）：
#     .\.venv\Scripts\python.exe -m uvicorn todo_api.main:app --reload
#
# 启动后浏览器打开下面地址，就是 FastAPI 自动生成的交互式接口文档（Swagger）：
#     http://127.0.0.1:8000/docs
# 在文档里点每个接口的 "Try it out" → "Execute"，就能直接在浏览器里发 HTTP 请求、看响应，
# 这正好对应 Day 8 要体会的"请求 / 响应 / 方法 / 状态码"。

from fastapi import FastAPI

from todo_api.routers import todos, users

# 创建应用实例。命令里的 "todo_api.main:app" 指的就是这个名为 app 的变量。
app = FastAPI(title="Todo API（第一阶段起步）", version="0.1.0")

# 把两个子路由"挂"到主应用上；它们各自带 /api/todos、/api/users 前缀。
app.include_router(todos.router)
app.include_router(users.router)


@app.get("/")
def root() -> dict[str, str]:
    """根路径健康检查，用来确认服务确实跑起来了。"""
    return {"message": "Todo API 已启动，访问 /docs 查看接口文档"}
