# Day 11 · Depends 依赖注入 · 一键演示脚本
#
# 运行（项目根目录 e:/python_learn 下）：
#     .\.venv\Scripts\python.exe run_day11_demo.py
#
# 不额外装任何依赖：服务端用已装好的 uvicorn 起在后台线程，
# 客户端用标准库 urllib.request 发请求，把"状态码 + 响应体"原样打出来，
# 这样依赖注入的每条规则都能一次跑完、亲眼看到，比手动点 /docs 快。
#
# 想看接口文档，另外开一个终端跑：
#     .\.venv\Scripts\python.exe -m uvicorn todo_api.main:app --reload
#     浏览器打开 http://127.0.0.1:8000/docs ，找 "Day11 · Depends 依赖注入" 分组。

import io
import json
import logging
import sys
import threading
import time
import urllib.error
import urllib.request

import uvicorn

from todo_api.deps import CurrentUser, get_current_user
from todo_api.main import app

BASE = "http://127.0.0.1:8011"

# 中文 Windows 的终端默认 GBK 代码页，打印到控制台的字串得避开编不了的字符；
# 再加一道兜底：真碰到无法编码的字符就用 "?" 代替，不让整个演示脚本崩掉。
# reconfigure 只有 TextIOWrapper 有，管道重定向时未必，所以先判类型。
if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(errors="replace", line_buffering=True)

# 打开 INFO 级日志，才能看到 app 级依赖 request_timer 打出的"耗时"那一行
logging.basicConfig(level=logging.INFO, format="    [log] %(name)s | %(message)s")


def start_server() -> uvicorn.Server:
    """在后台线程里把 app 跑起来，等服务就绪后返回 server 对象。"""
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=8011, log_level="warning")
    )
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)  # 等服务端真正监听端口，否则第一个请求会连不上
    return server


def call(path: str, headers: dict[str, str] | None = None) -> tuple[int, dict[str, object]]:
    """发一个 GET 请求。4xx/5xx 会被 urllib 当成异常抛出，这里统一转成 (状态码, 响应体)。"""
    request = urllib.request.Request(BASE + path, headers=headers or {})
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        try:
            return error.code, json.loads(raw)
        except ValueError:
            return error.code, {"detail": raw}


def show(title: str, path: str, headers: dict[str, str] | None = None) -> None:
    """打印一次调用的完整信息，方便和 todo_api/deps.py 里的注释逐条对照。"""
    code, body = call(path, headers)
    print(f"\n→ {title}")
    print(f"   GET {path}   请求头 {headers or '（无）'}")
    print(f"   → {code}  {_brief(body)}")


def _brief(body: dict[str, object]) -> str:
    """422 的响应体是一长串校验明细，只留最关键的第一条，免得刷屏。"""
    detail = body.get("detail")
    if isinstance(detail, list) and detail and isinstance(detail[0], dict):
        first: dict[str, object] = detail[0]
        loc_raw = first.get("loc") or []
        parts = loc_raw if isinstance(loc_raw, list) else [loc_raw]
        return f"校验失败 → 字段[{'.'.join(str(p) for p in parts)}] {first.get('msg')}"
    return json.dumps(body, ensure_ascii=False)


def main() -> None:
    server = start_server()
    print("=" * 72)
    print("Day 11 · Depends 依赖注入 演示（服务已启动在", BASE, "）")
    print("=" * 72)

    # ── 1. 依赖收敛查询参数 + 框架自动校验 ─────────────────────────
    print("\n【1】普通依赖：limit/offset 两个查询参数 → 一个 Pagination 对象")
    show("默认值（接口里没写任何 if 取默认）", "/api/depends/page")
    show("传参生效", "/api/depends/page?limit=2&offset=3")
    show("超上限 → 依赖层直接 422，没进接口函数", "/api/depends/page?limit=999")

    # ── 2. 依赖嵌套：order 与 page 来自不同层 ───────────────────────
    print("\n【2】依赖嵌套：page_query 依赖 pagination_params，再加一个 order")
    show("order=desc", "/api/depends/page?limit=3&order=desc")
    show("非法枚举值 → 422", "/api/depends/page?order=down")

    # ── 3. yield 依赖：资源创建 / 使用 / 释放 ────────────────────────
    print("\n【3】yield 依赖：连调两次，看上一个会话是否已被 finally 关掉")
    show("第一次", "/api/depends/session?note=first")
    show("第二次（上一条 closed 变 true 即为收尾生效）", "/api/depends/session?note=second")

    # ── 4. 登录态：401 / 403 / 200 三种结果 ──────────────────────────
    print("\n【4】登录态依赖链：api_token → get_current_user → require_admin")
    show("缺 X-Token → 401（第一层拦）", "/api/depends/me")
    show("token 无效 → 401（第二层拦）", "/api/depends/me", {"X-Token": "tok-bad"})
    show("有效 token → 200", "/api/depends/me", {"X-Token": "tok-001"})
    show("李四不是管理员 → 403（第三层拦）", "/api/depends/admin", {"X-Token": "tok-002"})
    show(
        "张三通过；same_instance=true 且次数=1 → 同一请求内依赖只解析一次",
        "/api/depends/admin",
        {"X-Token": "tok-001"},
    )

    # ── 5. 可选登录 + 只拦不注入 ─────────────────────────────────────
    print("\n【5】可选登录（不抛错的依赖） / 守卫型依赖（dependencies=[...]）")
    show("游客也能访问", "/api/depends/feed")
    show("带 token 则个性化", "/api/depends/feed", {"X-Token": "tok-002"})
    show("缺 X-Client → 400", "/api/depends/guarded")
    show("带 X-Client → 200（但接口拿不到它的值）", "/api/depends/guarded", {"X-Client": "script"})

    # ── 6. dependency_overrides：测试时整条链换掉 ────────────────────
    print("\n【6】依赖覆盖：不写 if 开关，就能把「当前用户」换成假的（单元测试常用）")

    def fake_current_user() -> CurrentUser:
        """假的依赖实现：签名返回类型一致即可，不需要读任何请求头。"""
        return CurrentUser(id=99, name="测试用户（假）", is_admin=True)

    app.dependency_overrides[get_current_user] = fake_current_user
    show("覆盖后 /me 不带 token 也 200（api_token 整条子链被绕过）", "/api/depends/me")
    show(
        "覆盖后 /admin 也直接放行；注意执行次数=0 —— 真的那个 get_current_user 一行都没跑",
        "/api/depends/admin",
    )

    app.dependency_overrides.clear()  # 演示完毕清掉，恢复真实校验
    show("clear() 之后 → 又回到 401，说明覆盖只作用于当前进程内的这个 app", "/api/depends/me")

    # ── 收尾 ──────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("演示结束，回看上面 6 段：Depends 的日常用法就这几招。")
    print("中间那些 [log] 行就是 app 级依赖 request_timer 打的（包括被 401/422 拦掉的请求也会记）")
    print("=" * 72)

    server.should_exit = True   # 通知 uvicorn 优雅关闭
    time.sleep(0.5)             # 留点时间收尾；服务线程是 daemon，主线程一退它就结束


if __name__ == "__main__":
    main()
