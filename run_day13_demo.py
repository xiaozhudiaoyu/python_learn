# Day 13 · 综合练习 · 一键演示脚本
#
# 运行（项目根目录 e:/python_learn 下）：
#     .\.venv\Scripts\python.exe run_day13_demo.py
#
# 把 Day 8~12 五天的知识点串成一个完整的 CRUD 流程：
#   ① 数据重置（Day 13 新接口）→ 干净起点
#   ② 查询全部 + 按状态过滤（Day 8 查询参数 + Day 13 新增）
#   ③ 创建任务（Day 9 路由 + Day 10 Pydantic 校验 + 201 状态码）
#   ④ 按 id 查询单条（Day 9 路径参数）
#   ⑤ 部分更新 PATCH（Day 10 请求体 + exclude_unset）
#   ⑥ 错误处理全覆盖（Day 12：400/401/404/405/409/422/500）
#   ⑦ 删除 + 幂等性验证（204 No Content）
#   ⑧ 依赖注入串（Day 11：分页 / 登录态 / yield 资源）
#   ⑨ OpenAPI 文档验证（Day 12：/docs /redoc /openapi.json）
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


def main() -> None:
    server = start_server()
    stamp = time.strftime("%H%M%S")
    unique = f"Day 13 综合任务 {stamp}"

    print("=" * 74)
    print(f"Day 13 · 综合练习（Day 8~12 知识串联）  服务已启动在 {BASE}")
    print("=" * 74)

    # ── ① 数据重置：POST /api/todos/reset ─────────────────────────────
    print("\n【1】数据重置（Day 13 新接口）→ 回到干净的初始状态")
    res = call("POST", "/api/todos/reset")
    check("重置 → 200", res.status, 200)
    check("返回 3 条初始数据", len(res.body), 3)
    check("第一条内容", res.body[0]["content"], "学习 HTTP 基础")
    show(res)

    # ── ② 查询全部 + 按状态过滤 ───────────────────────────────────────
    print("\n【2】查询参数过滤（Day 8 查询参数 + Day 13 新增 done 过滤）")
    res = call("GET", "/api/todos")
    check("不传 done → 返回全部 3 条", len(res.body), 3)

    res = call("GET", "/api/todos?done=true")
    check("?done=true → 只返回已完成的", len(res.body), 1)
    check("已完成的那条 id=1", res.body[0]["id"], 1)

    res = call("GET", "/api/todos?done=false")
    check("?done=false → 只返回未完成的", len(res.body), 2)

    # FastAPI 的 bool 查询参数接受 yes/no/on/off/1/0 等多种写法，这是正常行为
    res = call("GET", "/api/todos?done=yes")
    check("?done=yes（FastAPI 的 bool 接受 yes/no/on/off）→ 200", res.status, 200)

    # ── ③ 创建任务（POST + Pydantic 校验 + 201）────────────────────────
    print("\n【3】创建任务（Day 9 路由 + Day 10 Pydantic + 状态码语义）")
    res = call("POST", "/api/todos", json_body={"content": unique})
    check("POST 创建 → 201", res.status, 201)
    check("响应体有 id", "id" in res.body, True)
    check("done 默认 false", res.body["done"], False)
    check("201 带 Location 头", res.headers.get("location"), f"/api/todos/{res.body['id']}")
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

    res = call("PATCH", f"/api/todos/{new_id}", json_body={"content": "改个新名字"})
    check("只改 content → 200", res.status, 200)
    check("content 已更新", res.body["content"], "改个新名字")
    check("done 没被改", res.body["done"], True)

    res = call("PATCH", f"/api/todos/{new_id}", json_body={})
    check("空对象（什么都没要改）→ 400", res.status, 400)
    check("错误码", res.body.get("code"), "nothing_to_update")

    res = call("PATCH", f"/api/todos/{new_id}", json_body={"content": "学习 HTTP 基础"})
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
    check("WWW-Authenticate 头保留", res.headers.get("www-authenticate"), "Token")

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

    # ── ⑧ 依赖注入串 ─────────────────────────────────────────────────
    print("\n【8】依赖注入（Day 11：分页 / 登录态 / yield 资源）")

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

    # ── ⑨ OpenAPI 文档验证 ────────────────────────────────────────────
    print("\n【9】OpenAPI 文档（Day 12：三种文档地址都免费生成）")
    for url, label in (("/docs", "Swagger UI"), ("/redoc", "ReDoc"), ("/openapi.json", "OpenAPI 原文")):
        check(f"{label} 可访问", call("GET", url).status, 200)

    spec = call("GET", "/openapi.json").body

    # 验证 Day 13 新增接口出现在文档里
    reset_path = spec["paths"].get("/api/todos/reset", {})
    check("reset 接口出现在文档里", "post" in reset_path, True)

    # 验证 GET /api/todos 有 done 查询参数
    get_list = spec["paths"]["/api/todos"]["get"]
    param_names = [p["name"] for p in get_list.get("parameters", [])]
    check("done 查询参数出现在文档里", "done" in param_names, True)

    # 验证错误响应声明
    get_todo = spec["paths"]["/api/todos/{todo_id}"]["get"]
    check("文档里声明了 404 响应", "404" in get_todo["responses"], True)
    ref = get_todo["responses"]["404"]["content"]["application/json"]["schema"]["$ref"]
    check("404 响应模型是 ErrorOut", ref.endswith("/ErrorOut"), True)

    patch_todo = spec["paths"]["/api/todos/{todo_id}"]["patch"]
    check("PATCH 文档有 200/400/404/409/422",
          sorted(patch_todo["responses"]),
          ["200", "400", "404", "409", "422"])

    tags = {tag["name"] for tag in spec.get("tags", [])}
    check("分组说明生效", "Day11 · Depends 依赖注入" in tags, True)
    check("Day12 分组也在", "Day12 · 异常与错误响应" in tags, True)

    # ── ⑩ 最终重置验证：确认 reset 后数据恢复 ─────────────────────────
    print("\n【10】收尾：再跑一次 reset，确认数据恢复")
    res = call("POST", "/api/todos/reset")
    check("重置 → 200", res.status, 200)
    check("恢复到 3 条", len(res.body), 3)
    ids = [t["id"] for t in res.body]
    check("id 恢复为 1, 2, 3", ids, [1, 2, 3])

    # ── 手跑清单 ─────────────────────────────────────────────────────
    print("\n" + "=" * 74)
    print("在 Swagger（/docs）里手跑的完整清单，和上面 10 段一一对应：")
    for line in (
        "  1. POST /api/todos/reset → 200，看返回的 3 条初始数据",
        "  2. GET /api/todos?done=false → 只有 2 条未完成",
        "  3. POST /api/todos 创建新任务 → 201，注意 Location 头",
        "  4. GET /api/todos/{id} 查刚创建的 → 200；GET /api/todos/99999 → 404",
        "  5. PATCH /api/todos/{id} 改 done=true → 200；传 {} → 400",
        "  6. GET /api/errors/needs-token 不填 X-Token → 401；GET /api/errors/bug → 500",
        "  7. DELETE /api/todos/{id} → 204；再删一次 → 404",
        "  8. Day11 分组：/api/depends/page、/api/depends/me、/api/depends/session",
        "  9. 左上角 Models 区展开 ErrorOut / TaskCreate / TaskUpdate 看字段说明",
        " 10. 再跑一次 POST /api/todos/reset，确认数据恢复如初",
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
