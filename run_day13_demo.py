# Day 13 · 综合练习 · 一键演示脚本（Day 20 重写为数据库版）
#
# 运行（项目根目录 e:/python_learn 下）：
#     .\.venv\Scripts\python.exe run_day13_demo.py
#
# 把 Day 8~12 五天的知识点串成一个完整的 CRUD 流程：
#   ① 准备演示数据（数据库版：demo 自建带前缀数据，不依赖固定种子）
#   ② 查询全部 + 按状态过滤（Day 8 查询参数 + done 过滤）
#   ③ 创建任务（Day 9 路由 + Day 10 Pydantic 校验 + 201 状态码）
#   ④ 按 id 查询单条（Day 9 路径参数）
#   ⑤ 部分更新 PATCH（Day 10 请求体 + exclude_unset）
#   ⑥ 错误处理全覆盖（Day 12：400/401/404/405/409/422/500）
#   ⑦ 删除 + 幂等性验证（204 No Content）
#   ⑧ 用户接口 CRUD（Day 20：users 从内存假数据升级为数据库版）
#   ⑨ 依赖注入串（Day 11：分页 / 登录态 / yield 资源）
#   ⑩ OpenAPI 文档验证（Day 12：/docs /redoc /openapi.json，含 users）
#   ⑪ 收尾清理（删除本次演示数据，验证无残留）
#
# ── Day 20 重写说明（与内存版的区别）──────────────────────────────────
# 1. 数据不再依赖"3 条固定种子"。Day 19 起 todos 接数据库、reset 语义从
#    "恢复种子"改成"清空全表"；Day 20 users 也接了数据库。库里还混着
#    Day16/17 的学习数据，所以本 demo 改为【自给自足】：所有演示数据都带
#    DEMO_PREFIX 前缀、自建自清理，断言只看"我的数据在不在结果里"，
#    不断言全表总数（总数会受其他学习数据影响，不稳定）。
# 2. 【不自动跑破坏性 reset】。POST /api/todos/reset 会清空整张 todos 表
#    （连带 Day16/17 数据），属不可逆操作（用户规则 2.7），demo 不自动执行；
#    reset 接口只在 ⑩ 文档段验证"它存在"，想体验清空请手工调用（见末尾清单）。
# 3. 新增 ⑧ users CRUD 段，验证 Day 20 的用户接口（含 username 唯一 409、
#    limit 下推 SQL、UserOut 只暴露 id/username/email）。
#
# 和 run_day12_demo.py 同一套路：uvicorn 后台线程 + urllib 客户端，不新增依赖。

import io
import json
import logging
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Any, NamedTuple

import uvicorn

from todo_api.main import app

BASE = "http://127.0.0.1:8014"
DEMO_PREFIX = "day13_demo"   # 所有演示数据的前缀，清理时靠它精准识别、不误伤别的数据
PASSED: list[bool] = []

if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(errors="replace", line_buffering=True)

logging.basicConfig(level=logging.CRITICAL)


class Result(NamedTuple):
    status: int
    headers: dict[str, str]
    body: Any
    raw: str


def start_server() -> uvicorn.Server:
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=8014, log_level="critical")
    )
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)
    return server


def call(
    method: str,
    path: str,
    *,
    json_body: Any = None,
    raw_body: str | None = None,
    headers: dict[str, str] | None = None,
) -> Result:
    data = None
    request_headers = dict(headers or {})
    if json_body is not None:
        data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    elif raw_body is not None:
        data = raw_body.encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")

    request = urllib.request.Request(BASE + path, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request) as response:
            raw = response.read().decode("utf-8", errors="replace")
            # 注意：uvicorn 的 h11 会把响应头统一转小写，取值要按小写 key
            # （如 headers.get("location")），按大写 "Location" 取会拿到 None。
            return Result(response.status, dict(response.headers), _parse(raw), raw)
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        return Result(error.code, dict(error.headers), _parse(raw), raw)


def _parse(raw: str) -> Any:
    if not raw.strip():
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def check(label: str, actual: Any, expected: Any) -> None:
    ok = actual == expected
    PASSED.append(ok)
    mark = "[OK]  " if ok else "[FAIL]"
    print(f"   {mark} {label}：期望 {expected!r}，实际 {actual!r}")


def show(res: Result) -> None:
    print(f"        {res.status} {json.dumps(res.body, ensure_ascii=False)}")


def cleanup_demo_data() -> None:
    """删除所有带 DEMO_PREFIX 的 todos 和 users。

    demo 开头跑一次（清掉上次可能的残留，保证重复运行幂等）、结尾再跑一次
    （清理本次演示数据）。只删前缀匹配的，绝不碰 Day16/17 的学习数据。
    users 列表默认 limit=10，清理时传大 limit 确保捞全（limit 无上限校验）。
    """
    res = call("GET", "/api/todos")
    for todo in res.body or []:
        if str(todo.get("content", "")).startswith(DEMO_PREFIX):
            call("DELETE", f"/api/todos/{todo['id']}")

    res = call("GET", "/api/users?limit=1000")
    for user in res.body or []:
        if str(user.get("username", "")).startswith(DEMO_PREFIX):
            call("DELETE", f"/api/users/{user['id']}")


def main() -> None:
    server = start_server()
    stamp = time.strftime("%H%M%S")
    unique = f"{DEMO_PREFIX} 综合任务 {stamp}"

    print("=" * 74)
    print(f"Day 13 · 综合练习（数据库版 · Day 20 重写）  服务已启动在 {BASE}")
    print("=" * 74)

    # 开头先清理残留，保证重复运行从干净状态开始（只清 day13_demo 前缀数据）
    cleanup_demo_data()

    # ── ① 准备演示数据 ─────────────────────────────────────────────────
    print("\n【1】准备演示数据（数据库版：自建带前缀数据，不依赖固定种子）")
    # 建 3 条：任务A/B 未完成，任务C 已完成 —— 供 ② 段验证 done 过滤。
    ta = call("POST", "/api/todos", json_body={"content": f"{DEMO_PREFIX} 任务A"})
    tb = call("POST", "/api/todos", json_body={"content": f"{DEMO_PREFIX} 任务B"})
    tc = call("POST", "/api/todos", json_body={"content": f"{DEMO_PREFIX} 任务C", "done": True})
    check("建任务A → 201", ta.status, 201)
    check("建任务B → 201", tb.status, 201)
    check("建任务C(done=true) → 201", tc.status, 201)
    id_a, id_b, id_c = ta.body["id"], tb.body["id"], tc.body["id"]
    print("        （数据库版 reset 是破坏性清空，demo 不自动跑，改为自建数据）")

    # ── ② 查询全部 + 按状态过滤 ───────────────────────────────────────
    print("\n【2】查询参数过滤（Day 8 查询参数 + done 过滤）")
    res = call("GET", "/api/todos")
    all_ids = [t["id"] for t in res.body]
    check("不传 done → 我建的 3 条都在结果里", all(i in all_ids for i in (id_a, id_b, id_c)), True)

    res = call("GET", "/api/todos?done=true")
    done_ids = [t["id"] for t in res.body]
    check("?done=true 包含任务C", id_c in done_ids, True)
    check("?done=true 不含任务A", id_a in done_ids, False)

    res = call("GET", "/api/todos?done=false")
    undone_ids = [t["id"] for t in res.body]
    check("?done=false 包含任务A", id_a in undone_ids, True)
    check("?done=false 包含任务B", id_b in undone_ids, True)
    check("?done=false 不含任务C", id_c in undone_ids, False)

    # FastAPI 的 bool 查询参数接受 yes/no/on/off/1/0 等多种写法，这是正常行为
    res = call("GET", "/api/todos?done=yes")
    check("?done=yes（FastAPI 的 bool 接受 yes/no/on/off）→ 200", res.status, 200)

    # ── ③ 创建任务（POST + Pydantic 校验 + 201）────────────────────────
    print("\n【3】创建任务（Day 9 路由 + Day 10 Pydantic + 状态码语义）")
    res = call("POST", "/api/todos", json_body={"content": unique})
    check("POST 创建 → 201", res.status, 201)
    check("响应体有 id", "id" in res.body, True)
    check("done 默认 false", res.body["done"], False)
    check("201 带 Location 头（小写 key）", res.headers.get("location"), f"/api/todos/{res.body['id']}")
    new_id = res.body["id"]
    show(res)

    # 重复内容 → 409
    res = call("POST", "/api/todos", json_body={"content": unique})
    check("内容重复 → 409", res.status, 409)
    check("错误码", res.body.get("code"), "todo_conflict")

    # 空内容 → 422
    res = call("POST", "/api/todos", json_body={"content": ""})
    check("空内容 → 422", res.status, 422)
    check("校验错误码", res.body.get("code"), "validation_error")

    # 非法 JSON → 422
    res = call("POST", "/api/todos", raw_body="{不是 JSON")
    check("请求体不是合法 JSON → 422", res.status, 422)

    # ── ④ 按 id 查询单条（路径参数）─────────────────────────────────────
    print("\n【4】按 id 查询（Day 9 路径参数：{todo_id} 自动转 int）")
    res = call("GET", f"/api/todos/{new_id}")
    check("查到刚创建的任务 → 200", res.status, 200)
    check("内容一致", res.body["content"], unique)
    show(res)

    res = call("GET", "/api/todos/99999")
    check("不存在的任务 → 404", res.status, 404)
    check("错误码", res.body.get("code"), "todo_not_found")
    check("统一错误结构（有 details 字段）", "details" in res.body, True)

    res = call("GET", "/api/todos/abc")
    check("路径参数类型不对 → 422", res.status, 422)

    # ── ⑤ PATCH 部分更新 ──────────────────────────────────────────────
    print("\n【5】部分更新 PATCH（Day 10 exclude_unset + Day 12 错误处理）")
    res = call("PATCH", f"/api/todos/{new_id}", json_body={"done": True})
    check("只改 done → 200", res.status, 200)
    check("done 变成 true", res.body["done"], True)
    check("content 没被改", res.body["content"], unique)
    show(res)

    renamed = f"{DEMO_PREFIX} 改个新名字"
    res = call("PATCH", f"/api/todos/{new_id}", json_body={"content": renamed})
    check("只改 content → 200", res.status, 200)
    check("content 已更新", res.body["content"], renamed)
    check("done 没被改", res.body["done"], True)

    res = call("PATCH", f"/api/todos/{new_id}", json_body={})
    check("空对象（什么都没要改）→ 400", res.status, 400)
    check("错误码", res.body.get("code"), "nothing_to_update")

    # 撞名 409：改成"任务A"的内容（自给自足，不依赖任何种子数据）
    res = call("PATCH", f"/api/todos/{new_id}", json_body={"content": f"{DEMO_PREFIX} 任务A"})
    check("改成已有任务的内容 → 409", res.status, 409)

    res = call("PATCH", f"/api/todos/{new_id}", json_body={"done": False, "contnet": "拼错"})
    check("TaskUpdate 有 extra=forbid，拼错字段 → 422", res.status, 422)

    # ── ⑥ 错误处理全覆盖 ──────────────────────────────────────────────
    print("\n【6】错误处理全景（Day 12：各类状态码 + 统一结构）")

    # 405：方法不对
    res = call("POST", "/api/errors/legacy")
    check("方法不对 → 405", res.status, 405)
    check("错误码", res.body.get("code"), "method_not_allowed")

    # 401：依赖里抛的错
    res = call("GET", "/api/errors/needs-token")
    check("缺 X-Token → 401", res.status, 401)
    check("错误码", res.body.get("code"), "unauthorized")
    check("WWW-Authenticate 头保留（小写 key）", res.headers.get("www-authenticate"), "Token")

    # 500：真 bug
    res = call("GET", "/api/errors/bug")
    check("服务端 bug → 500", res.status, 500)
    check("错误码", res.body.get("code"), "internal_error")
    leaked = any(word in res.raw for word in ("Traceback", ".py", "int("))
    check("响应体不泄露堆栈", leaked, False)

    # 不存在的路径
    res = call("GET", "/api/never-defined")
    check("路径不存在 → 框架抛的 404 也被统一 handler 接住", res.body.get("code"), "not_found")

    # ── ⑦ 删除 + 幂等性 ──────────────────────────────────────────────
    print("\n【7】删除（204 No Content + 幂等性验证）")
    res = call("DELETE", f"/api/todos/{new_id}")
    check("删除成功 → 204", res.status, 204)
    check("响应体为空（204 不带任何字节）", len(res.raw), 0)

    res = call("DELETE", f"/api/todos/{new_id}")
    check("再删一次 → 404（幂等：不是又删成功，而是资源已不存在）", res.status, 404)

    # 过滤验证删除生效
    res = call("GET", "/api/todos")
    remaining_ids = [t["id"] for t in res.body]
    check("列表里确实没有被删的 id", new_id in remaining_ids, False)

    # ── ⑧ 用户接口 CRUD（Day 20 新增）──────────────────────────────────
    print("\n【8】用户接口 CRUD（Day 20：users 从内存假数据升级为数据库版）")
    uname = f"{DEMO_PREFIX}_user_{stamp}"
    res = call("POST", "/api/users", json_body={"username": uname, "email": f"{uname}@d13.dev"})
    check("创建用户 → 201", res.status, 201)
    check("响应含 id", "id" in res.body, True)
    check("username 一致", res.body["username"], uname)
    check("UserOut 只暴露 id/username/email（ORM 的 created_at/todos 被挡住）",
          sorted(res.body.keys()), ["email", "id", "username"])
    check("201 带 Location 头（小写 key）", res.headers.get("location"), f"/api/users/{res.body['id']}")
    uid = res.body["id"]
    show(res)

    # 重名 → 409
    res = call("POST", "/api/users", json_body={"username": uname})
    check("用户名重复 → 409", res.status, 409)
    check("错误码", res.body.get("code"), "user_conflict")

    # 列表 + limit（limit 下推成 SQL LIMIT）
    res = call("GET", "/api/users?limit=1")
    check("limit=1 → 只返回 1 条", len(res.body), 1)
    res = call("GET", "/api/users?limit=1000")
    check("刚建的用户在列表里", uid in [u["id"] for u in res.body], True)

    # 单条 + 404
    res = call("GET", f"/api/users/{uid}")
    check("查单个用户 → 200", res.status, 200)
    check("username 一致", res.body["username"], uname)

    res = call("GET", "/api/users/99999")
    check("不存在的用户 → 404", res.status, 404)
    check("错误码", res.body.get("code"), "user_not_found")

    # PATCH 改 email
    res = call("PATCH", f"/api/users/{uid}", json_body={"email": "new@d13.dev"})
    check("改 email → 200", res.status, 200)
    check("email 已更新", res.body["email"], "new@d13.dev")
    check("username 没被改", res.body["username"], uname)

    # PATCH 空 body → 400
    res = call("PATCH", f"/api/users/{uid}", json_body={})
    check("空对象 → 400", res.status, 400)
    check("错误码", res.body.get("code"), "nothing_to_update")

    # PATCH 改名撞到别的用户 → 409（先建第二个用户当"别人"）
    uname2 = f"{DEMO_PREFIX}_user2_{stamp}"
    u2 = call("POST", "/api/users", json_body={"username": uname2})
    check("建第二个用户 → 201", u2.status, 201)
    uid2 = u2.body["id"]
    res = call("PATCH", f"/api/users/{uid}", json_body={"username": uname2})
    check("改名撞到别的用户 → 409", res.status, 409)

    # DELETE + 幂等
    res = call("DELETE", f"/api/users/{uid}")
    check("删除用户 → 204", res.status, 204)
    res = call("DELETE", f"/api/users/{uid}")
    check("再删一次 → 404", res.status, 404)
    call("DELETE", f"/api/users/{uid2}")   # 清掉第二个用户（⑪ 还会兜底再清一次）

    # ── ⑨ 依赖注入串 ─────────────────────────────────────────────────
    print("\n【9】依赖注入（Day 11：分页 / 登录态 / yield 资源）")

    # 分页
    res = call("GET", "/api/depends/page?limit=2&offset=0")
    check("分页 limit=2 → 200", res.status, 200)
    check("返回 2 条", len(res.body["items"]), 2)
    check("total 字段存在", "total" in res.body, True)

    res = call("GET", "/api/depends/page?limit=999")
    check("超出上限 → 422（依赖层就拦下）", res.status, 422)

    # 登录态
    res = call("GET", "/api/depends/me")
    check("无 X-Token → 401", res.status, 401)

    res = call("GET", "/api/depends/me", headers={"X-Token": "tok-001"})
    check("有效 token → 200", res.status, 200)
    check("返回用户信息", res.body["登录用户"]["name"], "张三")

    res = call("GET", "/api/depends/me", headers={"X-Token": "tok-bad"})
    check("无效 token → 401", res.status, 401)

    # yield 资源
    res = call("GET", "/api/depends/session")
    check("yield 依赖 → 200", res.status, 200)
    check("本次会话 closed=false（正在使用中）", res.body["本次会话"]["closed"], False)

    # ── ⑩ OpenAPI 文档验证 ────────────────────────────────────────────
    print("\n【10】OpenAPI 文档（Day 12：三种文档地址都免费生成）")
    for url, label in (("/docs", "Swagger UI"), ("/redoc", "ReDoc"), ("/openapi.json", "OpenAPI 原文")):
        check(f"{label} 可访问", call("GET", url).status, 200)

    spec = call("GET", "/openapi.json").body
    paths = spec["paths"]

    # todos：reset 接口存在（只验证文档，不实际调用破坏性清空）
    check("reset 接口出现在文档里", "post" in paths.get("/api/todos/reset", {}), True)

    # todos：GET 列表有 done 查询参数
    get_list = paths["/api/todos"]["get"]
    param_names = [p["name"] for p in get_list.get("parameters", [])]
    check("done 查询参数出现在文档里", "done" in param_names, True)

    # todos：错误响应声明
    get_todo = paths["/api/todos/{todo_id}"]["get"]
    check("文档里声明了 404 响应", "404" in get_todo["responses"], True)
    ref = get_todo["responses"]["404"]["content"]["application/json"]["schema"]["$ref"]
    check("404 响应模型是 ErrorOut", ref.endswith("/ErrorOut"), True)

    patch_todo = paths["/api/todos/{todo_id}"]["patch"]
    check("PATCH 文档有 200/400/404/409/422",
          sorted(patch_todo["responses"]),
          ["200", "400", "404", "409", "422"])

    # users（Day 20 新增）：四类操作都出现在文档里
    check("/api/users 的 GET/POST 在文档里",
          {"get", "post"} <= set(paths.get("/api/users", {})), True)
    check("/api/users/{user_id} 的 GET/PATCH/DELETE 在文档里",
          {"get", "patch", "delete"} <= set(paths.get("/api/users/{user_id}", {})), True)

    # users：UserOut schema 恰好 3 个属性（created_at/todos 没外泄）
    user_out = spec["components"]["schemas"]["UserOut"]
    check("UserOut 恰有 id/username/email 三属性",
          sorted(user_out["properties"]), ["email", "id", "username"])

    # users：GET 列表的 limit 查询参数在文档里
    users_get = paths["/api/users"]["get"]
    users_params = [p["name"] for p in users_get.get("parameters", [])]
    check("users 列表的 limit 查询参数在文档里", "limit" in users_params, True)

    tags = {tag["name"] for tag in spec.get("tags", [])}
    check("分组说明生效", "Day11 · Depends 依赖注入" in tags, True)
    check("Day12 分组也在", "Day12 · 异常与错误响应" in tags, True)

    # ── ⑪ 收尾清理 ───────────────────────────────────────────────────
    print("\n【11】收尾：清理本次演示数据（数据库版不自动跑破坏性 reset）")
    cleanup_demo_data()
    res = call("GET", "/api/todos")
    leftover_t = [t for t in res.body if str(t.get("content", "")).startswith(DEMO_PREFIX)]
    check("todos 表无演示残留", len(leftover_t), 0)
    res = call("GET", "/api/users?limit=1000")
    leftover_u = [u for u in res.body if str(u.get("username", "")).startswith(DEMO_PREFIX)]
    check("users 表无演示残留", len(leftover_u), 0)

    # ── 手跑清单 ─────────────────────────────────────────────────────
    print("\n" + "=" * 74)
    print("在 Swagger（/docs）里手跑的完整清单，和上面 11 段一一对应：")
    for line in (
        "  1. POST /api/todos 建几条任务（数据库版 demo 自建数据，不靠固定种子）",
        "  2. GET /api/todos?done=false → 只看未完成的（结果含其他学习数据属正常）",
        "  3. POST /api/todos 创建新任务 → 201，注意 Location 头",
        "  4. GET /api/todos/{id} 查刚创建的 → 200；GET /api/todos/99999 → 404",
        "  5. PATCH /api/todos/{id} 改 done=true → 200；传 {} → 400",
        "  6. GET /api/errors/needs-token 不填 X-Token → 401；GET /api/errors/bug → 500",
        "  7. DELETE /api/todos/{id} → 204；再删一次 → 404",
        "  8. users 分组：POST 建用户 → 201；重名 → 409；PATCH 改 email；DELETE → 204",
        "  9. Day11 分组：/api/depends/page、/api/depends/me、/api/depends/session",
        " 10. 左上角 Models 区展开 ErrorOut / TaskOut / UserOut 看字段说明",
        " 11. 【破坏性·手工】POST /api/todos/reset 会清空整张 todos 表（含 Day16/17",
        "     学习数据），demo 不自动跑；确需体验清空再手工调用，调用前自行备份。",
    ):
        print(line)

    server.should_exit = True

    # ── 汇总 ─────────────────────────────────────────────────────────
    total, passed = len(PASSED), sum(PASSED)
    print("\n" + "=" * 74)
    print(f"断言结果：{passed}/{total} 通过" + ("" if passed == total else "  ← 有未通过项，见上面 [FAIL]"))
    print("=" * 74)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
