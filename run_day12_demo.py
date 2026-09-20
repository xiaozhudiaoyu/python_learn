# Day 12 · 异常处理 + 状态码 + OpenAPI 文档 · 一键演示脚本
#
# 运行（项目根目录 e:/python_learn 下）：
#     .\.venv\Scripts\python.exe run_day12_demo.py
#
# 和 Day 11 的脚本同一套路：uvicorn 起在后台线程，标准库 urllib 当客户端，
# 不新增任何依赖。和 Day 11 不同的是：这次每条演示都带一个 [OK]/[FAIL] 断言，
# 结尾汇总，有失败就以退出码 1 结束 —— "改完说好了"不算好，跑一遍才知道。
#
# 想在 Swagger 里手跑一遍？照本脚本最后打印的"手跑清单"来，步骤完全对应。

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

BASE = "http://127.0.0.1:8013"
PASSED: list[bool] = []

if isinstance(sys.stdout, io.TextIOWrapper):  # 中文终端默认 GBK，遇到编不了的字符用 "?" 代替，不让脚本崩掉
    sys.stdout.reconfigure(errors="replace", line_buffering=True)

# 关掉 uvicorn 自身的日志噪音（只保留我们自己 logger 的输出），原因见第 7 段的说明
logging.basicConfig(level=logging.CRITICAL)


class Result(NamedTuple):
    status: int
    headers: dict[str, str]
    body: Any
    raw: str


def start_server() -> uvicorn.Server:
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=8013, log_level="critical")
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
    """发一个请求；4xx/5xx 也照样拿回 Result（urllib 会抛 HTTPError，这里统一接住）。

    raw_body 用来故意发一段非法 JSON，验证最外层的解析错误怎么处理。
    """
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
    """尽量按 JSON 解析；204 的空 body、/docs 的 HTML 都返回 None，不值得为它们报错。"""
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
    """把响应体原样打出来，方便和 /docs 里看到的结构对照。"""
    print(f"        {res.status} {json.dumps(res.body, ensure_ascii=False)}")


def main() -> None:
    server = start_server()
    stamp = time.strftime("%H%M%S")  # 每次跑都用新内容，避免重名导致重复运行时全是 409
    unique = f"Day 12 演示任务 {stamp}"

    print("=" * 74)
    print(f"Day 12 · 异常处理 + 状态码 + OpenAPI 文档   （服务已启动在 {BASE}）")
    print("=" * 74)

    # ── 1. 成功路径上的状态码语义：200 / 201+Location ────────────────
    print("\n【1】状态码语义化：读 200、创建 201（并回一个 Location 头）")
    res = call("GET", "/api/todos")
    check("GET 列表", res.status, 200)

    res = call("POST", "/api/todos", json_body={"content": unique})
    check("POST 创建 → 201", res.status, 201)
    print(f"        Location 头 = {res.headers.get('location')!r}（201 的规范动作：告诉你新资源在哪）")
    new_id = res.body["id"]

    # ── 2. 409 vs 422：同为"没成功"，语义完全不同 ─────────────────────
    print("\n【2】409（与现有数据冲突）vs 422（格式本身不合法）")
    res = call("POST", "/api/todos", json_body={"content": unique})
    check("内容重复 → 409", res.status, 409)
    check("错误码", res.body.get("code"), "todo_conflict")
    show(res)

    res = call("POST", "/api/todos", json_body={"content": ""})
    check("空内容 → 422", res.status, 422)
    check("错误码", res.body.get("code"), "validation_error")
    print(f"        定制后的明细：{json.dumps(res.body.get('details'), ensure_ascii=False)}")

    # 下面这个 contnet 是【故意拼错的】（正确拼写是 content），用来演示拼错字段名会被 422 拦下；
    # 改成 content 请求就合法了，服务端会正常返回 201，这一条断言就失效了。
    res = call("POST", "/api/todos", json_body={"contnet": "拼错字段名"})
    check("缺 content（TaskCreate 未禁多余字段，所以是 missing 而非 extra）→ 422", res.status, 422)

    res = call("POST", "/api/todos", raw_body="{不是合法 JSON")
    check("请求体压根就不是合法 JSON → 422", res.status, 422)
    print(f"        明细：{json.dumps(res.body.get('details'), ensure_ascii=False)}")

    # ── 3. 404 / 405：自己抛的 与 框架自己抛的，出口同一个 ────────────
    print("\n【3】404 / 405：业务里 raise 的，和框架自己抛的，结构一致")
    res = call("GET", "/api/todos/99999")
    check("不存在的任务 → 404", res.status, 404)
    check("错误码", res.body.get("code"), "todo_not_found")
    show(res)

    res = call("GET", "/api/never-defined")
    check("路径压根不存在 → 框架抛的 404 也被同一个 handler 接住", res.body.get("code"), "not_found")

    res = call("POST", "/api/errors/legacy")
    check("方法不对 → 405", res.status, 405)
    check("错误码", res.body.get("code"), "method_not_allowed")

    # ── 4. PATCH：部分更新的三种错误 ─────────────────────────────────
    print("\n【4】PATCH 部分更新（exclude_unset 才是 PATCH 语义的关键）")
    res = call("PATCH", f"/api/todos/{new_id}", json_body={"done": True})
    check("只改 done → 200", res.status, 200)
    check("content 未被改动", res.body.get("content"), unique)
    show(res)

    res = call("PATCH", f"/api/todos/{new_id}", json_body={})
    check("空对象（什么都没要改）→ 400", res.status, 400)
    check("错误码", res.body.get("code"), "nothing_to_update")

    # 同上，contnet 是故意拼错的字段名；TaskUpdate 开了 extra="forbid"，所以这里报的是 extra_forbidden。
    res = call("PATCH", f"/api/todos/{new_id}", json_body={"done": False, "contnet": "拼错"})
    check("TaskUpdate 有 extra=forbid，拼错字段 → 422", res.status, 422)
    print(f"        明细：{json.dumps(res.body.get('details'), ensure_ascii=False)}")

    # Day 19 起 todos 接入数据库，内存版的种子数据（"学习 HTTP 基础"）不再保证存在，
    # 撞名断言改为自给自足：先建一个"参照任务"，再把 new_id 改成它的 content → 409。
    ref_content = f"Day 12 参照任务 {stamp}"
    ref = call("POST", "/api/todos", json_body={"content": ref_content})
    check("创建撞名参照任务 → 201", ref.status, 201)
    res = call("PATCH", f"/api/todos/{new_id}", json_body={"content": ref_content})
    check("改成已有任务的内容 → 409", res.status, 409)
    call("DELETE", f"/api/todos/{ref.body['id']}")  # 清理参照任务，不在库里留垃圾

    # ── 5. 204：成功但没有响应体 ─────────────────────────────────────
    print("\n【5】DELETE → 204 No Content（注意 raw body 必须是空的）")
    res = call("DELETE", f"/api/todos/{new_id}")
    check("删除成功 → 204", res.status, 204)
    check("响应体长度（204 不该带任何字节）", len(res.raw), 0)

    res = call("DELETE", f"/api/todos/{new_id}")
    check("再删一次 → 404（DELETE 的第二次不是「又删成功」，而是资源已不存在）", res.status, 404)

    # ── 6. 依赖里抛的错，也走同一套 handler ──────────────────────────
    print("\n【6】Day 11 的登录态依赖 + Day 12 的统一错误：跨天协作验证")
    res = call("GET", "/api/errors/needs-token")
    check("缺 X-Token → 401", res.status, 401)
    check(
        "错误码（以前是裸的 detail 字段，现在被 HTTPException handler 归一了）",
        res.body.get("code"),
        "unauthorized",
    )
    check("WWW-Authenticate 头被保留（handler 里回传 exc.headers 才有）",
          res.headers.get("www-authenticate"), "Token")
    show(res)

    res = call("GET", "/api/errors/conflict")
    check("领域异常 → 409，结构和其它错误完全一样", res.body.get("code"), "todo_conflict")
    res = call("GET", "/api/errors/legacy")
    check("旧写法 HTTPException → 418，同结构，code 退化成 http_418", res.body.get("code"), "http_418")

    # ── 7. 兜底 500：对外不含堆栈，对内日志一条不少 ───────────────────
    print("\n【7】故意制造一个真 bug → 500")
    res = call("GET", "/api/errors/bug")
    check("状态码", res.status, 500)
    check("错误码", res.body.get("code"), "internal_error")
    leaked = any(word in res.raw for word in ("Traceback", ".py", "int(", "ZeroDivision"))
    check("响应体里有没有泄露堆栈/文件名（False 才合格）", leaked, False)
    print("        本段用的是 log_level=「critical」，所以看不到服务端 traceback；")
    print("        把 start_server() 里改成 log_level=「info」 再跑，你会看到 uvicorn 打了一整段堆栈")
    print("        —— 客户端拿不到、开发看得到，这就是 500 该有的样子。")

    # ── 8. OpenAPI 文档：不靠眼睛看，用程序断言文档确实生成了 ─────────
    print("\n【8】OpenAPI 文档验证（/docs 里看到的东西，这里逐项断言）")
    for url, label in (("/docs", "Swagger UI"), ("/redoc", "ReDoc"), ("/openapi.json", "OpenAPI 原文")):
        check(f"{label} 可访问", call("GET", url).status, 200)

    spec = call("GET", "/openapi.json").body
    get_todo = spec["paths"]["/api/todos/{todo_id}"]["get"]
    check("文档里声明了 404 响应", "404" in get_todo["responses"], True)
    ref = get_todo["responses"]["404"]["content"]["application/json"]["schema"]["$ref"]
    check("404 响应的模型就是 ErrorOut", ref.endswith("/ErrorOut"), True)
    check("PATCH 文档里有 400/404/409，外加 FastAPI 自动补上的 422",
          sorted(spec["paths"]["/api/todos/{todo_id}"]["patch"]["responses"]),
          ["200", "400", "404", "409", "422"])
    print("        422 这一档没写也会存在：接口一带请求体，FastAPI 就自动补；显式写它是为了把模型换成 ErrorOut")
    check("DELETE 的成功状态码写进文档为 204",
          "204" in spec["paths"]["/api/todos/{todo_id}"]["delete"]["responses"], True)
    tags = {tag["name"] for tag in spec.get("tags", [])}
    check("分组说明已生效（openapi_tags）", "Day12 · 异常与错误响应" in tags, True)

    # ── 手跑清单 ─────────────────────────────────────────────────────
    print("\n" + "=" * 74)
    print("在 Swagger（/docs）里完整跑一遍的清单，和上面 8 段一一对应：")
    for line in (
        "  a. todos → POST /api/todos 试合法内容 → 看 201 响应头的 Location",
        "  b. 同一条内容再 Execute 一次 → 409，Responses 区展开能看到 ErrorOut 结构",
        "  c. 把 content 改成 \"\" → 422，details 里是我们定制过的 field/type/message",
        "  d. GET /api/todos/99999 → 404；PATCH 传 {} → 400；DELETE 两次 → 204 然后 404",
        "  e. Day11 分组里 /api/depends/me 不填 X-Token → 401（现在也是统一结构了）",
        "  f. Day12 分组里 GET /api/errors/bug → 500；再对 /api/errors/legacy 发 POST → 405",
        "  g. 每个接口右侧的 Models 区展开，能看到 ErrorOut / TaskUpdate 的字段说明",
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
