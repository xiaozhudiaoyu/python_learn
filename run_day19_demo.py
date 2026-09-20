# Day 19 · 接口模型 vs ORM 模型分离 · 一键验证脚本
#
# 运行（项目根目录 e:/python_learn 下）：
#     .\.venv\Scripts\python.exe run_day19_demo.py
#
# 前置条件：
#   ① day15_orm/db_config_local.py 已配置好 MySQL 连接（Day 15 建过）；
#   ② 表结构已就位：.\.venv\Scripts\python.exe -m alembic upgrade head
#      （本脚本【不会】自动建表 —— Day 18 立的规矩：建表/改表一律走 Alembic）。
#
# 本脚本验证 Day 19 的三个目标：
#   ① Schema（Pydantic）和 Model（SQLAlchemy）的职责区分 —— 字段对照、互不替代；
#   ② 数据转换（ORM → Pydantic）—— from_attributes 开关的作用与必要性；
#   ③ 重构后的 TODO API 接入真实数据库 —— service 层进程内 CRUD + HTTP 端到端。
#
# 分段：
#   第 1 段  环境检查 + Schema vs Model 字段对照（"分离"的静态证据）
#   第 2 段  from_attributes 转换演示（含"没开关会报错"的对照实验）
#   第 3 段  ORM 对象脱离 Session 的危险 vs TaskOut 的安全（"分离"的运行时证据）
#   第 4 段  service 层进程内 CRUD + 三类业务异常（409/404/400）
#   第 5 段  HTTP 端到端：起 uvicorn，跑完整 CRUD，验证接口契约与内存版兼容
#
# 与 run_day15_demo.py 同一套路：check() 收集断言、末尾汇总、失败时退出码非 0。
#
# 【数据安全】本脚本创建的所有待办都带 "day19_demo" 前缀，结束时按前缀精确清理，
#            不碰表里的其他数据，不执行 TRUNCATE / DROP。

import io
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Any

import uvicorn
from sqlalchemy import select

from day15_orm import Todo, existing_tables
from todo_api import service
from todo_api.db import get_db_engine, get_db_session_factory
from todo_api.exceptions import NothingToUpdateError, TodoConflictError, TodoNotFoundError
from todo_api.main import app
from todo_api.schemas import TaskCreate, TaskOut, TaskUpdate

BASE = "http://127.0.0.1:8019"
DEMO_PREFIX = "day19_demo"

PASSED: list[bool] = []

# 中文 Windows 的终端默认 GBK 代码页，避开编不了的字符，再加一道兜底。
if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(errors="replace", line_buffering=True)


def check(label: str, actual: Any, expected: Any) -> None:
    ok = actual == expected
    PASSED.append(ok)
    mark = "[OK]  " if ok else "[FAIL]"
    print(f"   {mark} {label}：期望 {expected!r}，实际 {actual!r}")


def check_true(label: str, condition: bool) -> None:
    """布尔断言的简写：只关心真/假，不打印期望值。"""
    PASSED.append(condition)
    mark = "[OK]  " if condition else "[FAIL]"
    print(f"   {mark} {label}")


def section(title: str) -> None:
    print(f"\n{'─' * 72}\n{title}\n{'─' * 72}")


# ══════════════════════════════════════════════════════════════════════
# 第 1 段：环境检查 + Schema vs Model 字段对照
# ══════════════════════════════════════════════════════════════════════

def section_1_field_contrast() -> bool:
    """返回 False 表示环境不满足（表不存在），后续段落全部跳过。"""
    section("第 1 段 · 环境检查 + Schema vs Model 字段对照")

    engine = get_db_engine()
    tables = existing_tables(engine)
    print(f"   数据库现有表：{sorted(tables)}")
    if "todos" not in tables:
        print("   [FAIL] todos 表不存在！请先执行：")
        print("          .\\.venv\\Scripts\\python.exe -m alembic upgrade head")
        return False
    check_true("todos 表已就位（Alembic 迁移已执行）", True)

    # ── ORM 模型有哪些"列"────────────────────────────────────────────
    # 用 SQLAlchemy 的 inspect 拿列名，这是"数据库视角"的字段清单。
    from sqlalchemy import inspect as sa_inspect

    orm_columns = {c.key for c in sa_inspect(Todo).columns}
    print(f"   ORM  Model（todos 表列）  ：{sorted(orm_columns)}")

    # ── Pydantic Schema 有哪些"字段"──────────────────────────────────
    # model_fields 是 Pydantic v2 的类属性，key 就是字段名。
    # 注意这里对照的是 TaskOut（响应模型）—— 它代表"接口对外暴露什么"。
    out_fields = set(TaskOut.model_fields)
    create_fields = set(TaskCreate.model_fields)
    update_fields = set(TaskUpdate.model_fields)
    print(f"   Schema TaskOut（响应字段） ：{sorted(out_fields)}")
    print(f"   Schema TaskCreate（请求字段）：{sorted(create_fields)}")
    print(f"   Schema TaskUpdate（PATCH 字段）：{sorted(update_fields)}")

    # ── 断言 1：TaskOut 的字段是 ORM 列的【真子集】──────────────────
    # "真子集"是分离的直接证据：Schema 暴露的字段 ORM 全都有（否则转换会缺值），
    # 但 ORM 还有 Schema 不暴露的字段（priority/created_at/owner_id）——
    # 内部存储比对外契约"多"，多出来的部分被 Schema 挡在了接口边界之内。
    check_true("TaskOut 字段 ⊆ ORM 列（响应字段都有数据来源）", out_fields <= orm_columns)
    check_true("ORM 列 ⊋ TaskOut 字段（内部字段没有全部外泄）", out_fields < orm_columns)
    leaked = orm_columns - out_fields
    print(f"   被 Schema 挡住的 ORM 字段：{sorted(leaked)}")

    # ── 断言 2：三个 Schema 各司其职，字段集合互不相同 ────────────────
    # Create 没有 id（id 由数据库生成，客户端不该传）；
    # Update 全部可选（PATCH 语义）；Out 有 id（响应必须带）。
    # 如果三者是同一个模型，这些差异就表达不出来 —— 这就是"为什么要拆三个类"。
    check_true("TaskCreate 不含 id（id 由数据库生成）", "id" not in create_fields)
    check_true("TaskOut 含 id（响应必须带）", "id" in out_fields)
    check_true("TaskUpdate 字段全部可选（PATCH 语义）",
               all(f.default is None for f in TaskUpdate.model_fields.values()))

    # ── 断言 3：两套模型的"类型体系"互不依赖 ─────────────────────────
    # ORM 的 Todo 是 SQLAlchemy 声明式类，TaskOut 是 Pydantic BaseModel，
    # 没有继承关系、没有共享元类。字段名看起来像，纯属"刻意对齐"（models.py 注释里写了）。
    from pydantic import BaseModel as PydanticBaseModel

    check_true("Todo 不是 Pydantic 模型（ORM 不兼职做接口校验）",
               not issubclass(Todo, PydanticBaseModel))
    check_true("TaskOut 不是 SQLAlchemy 映射类（Schema 不兼职做表映射）",
               not hasattr(TaskOut, "__tablename__"))
    return True


# ══════════════════════════════════════════════════════════════════════
# 第 2 段：from_attributes 转换演示
# ══════════════════════════════════════════════════════════════════════

def section_2_from_attributes() -> None:
    section("第 2 段 · ORM → Pydantic 转换：from_attributes 的作用")

    factory = get_db_session_factory()
    session = factory()
    created_ids: list[int] = []
    try:
        # 建一条真实数据（带 demo 前缀，最后统一清理）。
        todo = service_dao_create(session, f"{DEMO_PREFIX}_转换演示")
        created_ids.append(todo.id)

        # ── 正常路径：TaskOut 开了 from_attributes，直接喂 ORM 对象 ──
        out = TaskOut.model_validate(todo)
        check("model_validate(ORM 对象) 成功转换 id", out.id, todo.id)
        check("转换后 content 一致", out.content, todo.content)
        check("转换后 done 一致", out.done, todo.done)
        check("转换结果类型是 TaskOut（不是 Todo）", type(out).__name__, "TaskOut")

        # ── 关键证据：TaskOut 上没有 ORM 多出来的字段 ────────────────
        # todo.priority / todo.created_at 在 ORM 对象上存在，
        # 但 TaskOut 没声明它们，转换后就被丢掉了 —— 这就是"过滤"。
        check_true("ORM 对象有 priority 属性", hasattr(todo, "priority"))
        check_true("TaskOut 实例没有 priority 字段", not hasattr(out, "priority"))
        check_true("TaskOut 实例没有 created_at 字段", not hasattr(out, "created_at"))

        # ── 对照实验：没开 from_attributes 的模型喂 ORM 对象会报错 ────
        # 临时定义一个"忘记配开关"的响应模型，复现 Pydantic 的报错，
        # 让"这个开关不是可有可无的装饰"变得可触摸。
        from pydantic import BaseModel as PydanticBaseModel

        class ForgottenConfig(PydanticBaseModel):
            id: int
            content: str
            done: bool

        try:
            ForgottenConfig.model_validate(todo)
            check_true("未开 from_attributes 时应当报错（实际没报错！）", False)
        except Exception as exc:  # Pydantic 抛 ValidationError
            # 报错信息里会提示 "Input should be a valid dictionary or instance of ..."，
            # 意思是：默认只认 dict，不认"任意对象的属性"。
            msg = str(exc)
            check_true("未开 from_attributes 时喂 ORM 对象确实报错", True)
            print(f"        报错摘要：{msg.splitlines()[0][:80]}...")

        # ── 顺带验证：dict 路径依然可用（向后兼容）──────────────────
        # from_attributes=True 是"额外支持读属性"，不是"只准读属性"。
        # 内存版时代 TaskOut.model_validate({"id":1,...}) 的写法照样能跑，
        # 所以 Day 13 的旧测试脚本不会因为这一个改动而挂掉。
        from_dict = TaskOut.model_validate({"id": 1, "content": "x", "done": False})
        check("dict 输入依然可用（向后兼容）", from_dict.id, 1)
    finally:
        cleanup_by_ids(session, created_ids)
        session.close()


def service_dao_create(session, content: str) -> Todo:
    """demo 内部用：绕过 service 的事务封装，直接走 dao 建数据（方便统一 rollback 控制）。

    为什么不直接调 service.create_todo？因为 service 内部会 commit，
    而 demo 某些段落想自己控制事务时序。这里复用 day16 dao，保持"不 commit"约定，
    由调用方决定何时 commit / rollback。
    """
    from day16_crud import dao

    todo = dao.create_todo(session, content=content, done=False)
    session.commit()
    return todo


def cleanup_by_ids(session, ids: list[int]) -> None:
    """按 id 精确清理 demo 数据。逐个删而不是批量 IN，是为了复用 dao、少写 SQL。"""
    from day16_crud import dao

    try:
        for todo_id in ids:
            dao.delete_todo(session, todo_id)
        session.commit()
    except Exception:
        session.rollback()


# ══════════════════════════════════════════════════════════════════════
# 第 3 段：ORM 对象脱离 Session 的危险 vs TaskOut 的安全
# ══════════════════════════════════════════════════════════════════════

def section_3_detached_orm() -> None:
    section("第 3 段 · 为什么 ORM 对象不能越过 service 层交给 router")

    factory = get_db_session_factory()
    session = factory()
    created_ids: list[int] = []
    try:
        todo = service_dao_create(session, f"{DEMO_PREFIX}_脱离演示")
        created_ids.append(todo.id)

        # 先在 session 存活期把"普通属性"读出来 —— 这些值已经加载进内存，
        # day15_orm 配的 expire_on_commit=False 保证 commit 后它们也不过期。
        check("session 存活时读 todo.content 正常", todo.content, f"{DEMO_PREFIX}_脱离演示")

        # 转换成 TaskOut：此刻 Schema 对象已经把值"抄"了一份，成为纯数据对象。
        out = TaskOut.model_validate(todo)

        # ── 关掉 session，模拟"请求结束、依赖把 session 收回"之后的世界 ──
        session.close()

        # TaskOut 是纯 Python 对象，不依赖任何 session，随时可读：
        check("session 关闭后 TaskOut.content 依然可读", out.content, f"{DEMO_PREFIX}_脱离演示")
        check("session 关闭后 TaskOut.id 依然可读", out.id, todo.id)

        # ORM 对象的普通属性因为 expire_on_commit=False 也还能读（这是配置换来的便利），
        # 但 relationship 是"懒加载"的 —— 访问它需要发新的 SQL，而 session 已经关了：
        try:
            _ = todo.owner  # 触发懒加载 → 需要 session → 报错
            # 走到这里说明 owner 恰好已被加载过（本例没有），不算失败，但要如实报告。
            print("   [WARN] todo.owner 未触发报错（可能已被预加载），换一个未加载的关系再试")
            detached_raised = False
        except Exception as exc:
            detached_raised = True
            print(f"   [OK]  session 关闭后访问 todo.owner 报错：{type(exc).__name__}")
        check_true("ORM 对象脱离 session 后 relationship 不可用（懒加载报错）", detached_raised)

        print("   结论：router 若直接返回 ORM 对象，FastAPI 序列化时一旦碰到")
        print("         relationship（或 expire_on_commit=True 下的普通属性），")
        print("         就会在'session 已关'的时机炸掉。TaskOut 没有这个问题 ——")
        print("         它在 service 层就已经把需要的值固化成了纯数据。")
    finally:
        # session 已 close，重新开一个做清理。
        cleanup_session = factory()
        cleanup_by_ids(cleanup_session, created_ids)
        cleanup_session.close()


# ══════════════════════════════════════════════════════════════════════
# 第 4 段：service 层进程内 CRUD + 业务异常
# ══════════════════════════════════════════════════════════════════════

def section_4_service_crud() -> None:
    section("第 4 段 · service 层 CRUD 与业务异常（进程内，不经过 HTTP）")

    factory = get_db_session_factory()
    session = factory()
    created_ids: list[int] = []
    try:
        # ── 4.1 create：返回的是 TaskOut 而不是 Todo ─────────────────
        payload = TaskCreate(content=f"{DEMO_PREFIX}_service新增", done=False)
        out = service.create_todo(session, payload)
        check("create_todo 返回类型是 TaskOut", type(out).__name__, "TaskOut")
        check("返回的 content 与请求一致", out.content, payload.content)
        check_true("返回的 id 是数据库生成的正整数", out.id > 0)
        created_ids.append(out.id)

        # ── 4.2 create 重名 → 409 TodoConflictError ──────────────────
        try:
            service.create_todo(session, TaskCreate(content=payload.content))
            check_true("重名应当抛 TodoConflictError（实际没抛！）", False)
        except TodoConflictError as exc:
            check("重名抛 TodoConflictError，status_code=409", exc.status_code, 409)
            check("错误码是 todo_conflict", exc.code, "todo_conflict")

        # ── 4.3 get：存在 → TaskOut；不存在 → 404 ────────────────────
        got = service.get_todo(session, out.id)
        check("get_todo 命中时返回同一条", got.id, out.id)
        try:
            service.get_todo(session, 999_999_999)
            check_true("不存在的 id 应当抛 TodoNotFoundError（实际没抛！）", False)
        except TodoNotFoundError as exc:
            check("不存在抛 TodoNotFoundError，status_code=404", exc.status_code, 404)

        # ── 4.4 list + done 过滤 ─────────────────────────────────────
        all_items = service.list_todos(session)
        check_true("list_todos 返回 list[TaskOut]",
                   isinstance(all_items, list)
                   and all(isinstance(i, TaskOut) for i in all_items))
        # 建一条 done=True 的，验证过滤真的在数据库层生效（where 子句）。
        done_item = service.create_todo(session, TaskCreate(content=f"{DEMO_PREFIX}_已完成", done=True))
        created_ids.append(done_item.id)
        only_done = service.list_todos(session, done=True)
        check_true("done=True 过滤结果非空", len(only_done) > 0)
        check_true("done=True 过滤结果里每条都是 done", all(i.done for i in only_done))
        check_true("过滤结果包含刚建的那条", any(i.id == done_item.id for i in only_done))

        # ── 4.5 update：正常改 / 空改 400 / 改名撞车 409 ─────────────
        updated = service.update_todo(session, out.id, TaskUpdate(done=True))
        check("PATCH done=True 生效", updated.done, True)
        check("PATCH 未传的字段保持不变", updated.content, payload.content)

        try:
            service.update_todo(session, out.id, TaskUpdate())
            check_true("空 PATCH 应当抛 NothingToUpdateError（实际没抛！）", False)
        except NothingToUpdateError as exc:
            check("空 PATCH 抛 NothingToUpdateError，status_code=400", exc.status_code, 400)

        try:
            # 把 out 的 content 改成 done_item 的 content → 与"别人"重名 → 409
            service.update_todo(session, out.id, TaskUpdate(content=done_item.content))
            check_true("改名撞车应当抛 TodoConflictError（实际没抛！）", False)
        except TodoConflictError as exc:
            check("改名撞车抛 TodoConflictError", exc.status_code, 409)

        # 改成自己的原名不算冲突（exclude_id 的作用）：
        same_name = service.update_todo(session, out.id, TaskUpdate(content=payload.content))
        check("改回自己的原名不报冲突", same_name.content, payload.content)

        # ── 4.6 delete：成功 → None；再删 → 404 ──────────────────────
        result = service.delete_todo(session, out.id)
        check("delete_todo 成功返回 None", result, None)
        created_ids.remove(out.id)  # 已删，从清理清单移除
        try:
            service.delete_todo(session, out.id)
            check_true("重复删除应当抛 TodoNotFoundError（实际没抛！）", False)
        except TodoNotFoundError as exc:
            check("重复删除抛 TodoNotFoundError", exc.status_code, 404)

        # ── 4.7 事务边界证据：service 内部已 commit，换个 session 也能看到 ──
        # 如果 service 没 commit，新 session（新连接）是看不到 done_item 的。
        verify_session = factory()
        try:
            rows = verify_session.scalars(
                select(Todo).where(Todo.content == f"{DEMO_PREFIX}_已完成")
            ).all()
            check_true("service commit 后，另一个 session 能查到数据（事务已落库）", len(rows) == 1)
        finally:
            verify_session.close()
    finally:
        cleanup_by_ids(session, created_ids)
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 第 5 段：HTTP 端到端（起 uvicorn，验证接口契约与内存版兼容）
# ══════════════════════════════════════════════════════════════════════

def start_server() -> uvicorn.Server:
    """在后台线程里把 app 跑起来（与 run_day11_demo.py 同一套路）。"""
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=8019, log_level="warning")
    )
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)
    return server


def http_call(
    method: str, path: str, body: dict[str, Any] | None = None
) -> tuple[int, Any, dict[str, str]]:
    """发一个 HTTP 请求，返回 (状态码, 解析后的 JSON 或 None, 响应头)。

    4xx/5xx 会被 urllib 当异常抛出，这里统一转成返回值，让断言写起来平铺直叙。
    """
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(request) as response:
            raw = response.read()
            parsed = json.loads(raw) if raw else None
            return response.status, parsed, dict(response.headers)
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            parsed = json.loads(raw) if raw else None
        except ValueError:
            parsed = {"raw": raw.decode("utf-8", errors="replace")}
        return error.code, parsed, dict(error.headers)


def section_5_http_end_to_end(server: uvicorn.Server) -> None:
    section("第 5 段 · HTTP 端到端（接口契约与内存版完全兼容）")
    created_ids: list[int] = []
    try:
        # ── 5.1 POST 创建 → 201 + Location 头 ────────────────────────
        code, body, headers = http_call(
            "POST", "/api/todos", {"content": f"{DEMO_PREFIX}_http新增", "done": False}
        )
        check("POST 创建返回 201", code, 201)
        check("响应体是 TaskOut 结构（恰好 3 个字段）", sorted(body), ["content", "done", "id"])
        check("响应 content 正确", body["content"], f"{DEMO_PREFIX}_http新增")
        created_ids.append(body["id"])
        # 头名称按小写取：uvicorn 的 h11 实现会把响应头统一转小写发送
        # （HTTP 头名本身大小写不敏感），run_day13_demo.py 也是按小写取的。
        check("Location 头指向新资源", headers.get("location"), f"/api/todos/{body['id']}")
        # 关键证据：响应体里【没有】priority/created_at/owner_id ——
        # ORM 有这些列，但 Schema 没声明，FastAPI 的 response_model 把它们过滤掉了。
        check_true("响应体不含 priority（ORM 字段被 Schema 挡住）", "priority" not in body)
        check_true("响应体不含 created_at", "created_at" not in body)
        check_true("响应体不含 owner_id", "owner_id" not in body)

        # ── 5.2 GET 列表 / 单条 ──────────────────────────────────────
        code, body, _ = http_call("GET", "/api/todos")
        check("GET 列表返回 200", code, 200)
        check_true("列表里能找到刚创建的那条", any(i["id"] == created_ids[0] for i in body))

        code, body, _ = http_call("GET", f"/api/todos/{created_ids[0]}")
        check("GET 单条返回 200", code, 200)
        check("GET 单条 id 正确", body["id"], created_ids[0])

        # ── 5.3 GET 不存在 → 404 + 统一错误结构 ──────────────────────
        code, body, _ = http_call("GET", "/api/todos/999999999")
        check("GET 不存在返回 404", code, 404)
        check("404 错误码是 todo_not_found", body["code"], "todo_not_found")
        check_true("404 带统一错误结构 {code,message,details}",
                   {"code", "message", "details"} <= set(body))

        # ── 5.4 POST 重名 → 409 ──────────────────────────────────────
        code, body, _ = http_call(
            "POST", "/api/todos", {"content": f"{DEMO_PREFIX}_http新增"}
        )
        check("重名创建返回 409", code, 409)
        check("409 错误码是 todo_conflict", body["code"], "todo_conflict")

        # ── 5.5 PATCH 部分更新 / 空更新 400 ──────────────────────────
        code, body, _ = http_call(
            "PATCH", f"/api/todos/{created_ids[0]}", {"done": True}
        )
        check("PATCH done=True 返回 200", code, 200)
        check("PATCH 后 done 变 True", body["done"], True)
        check("PATCH 未传字段 content 不变", body["content"], f"{DEMO_PREFIX}_http新增")

        code, body, _ = http_call("PATCH", f"/api/todos/{created_ids[0]}", {})
        check("空 PATCH 返回 400", code, 400)
        check("400 错误码是 nothing_to_update", body["code"], "nothing_to_update")

        # ── 5.6 校验失败 → 422（Schema 在接口边界拦住了非法输入）──────
        code, body, _ = http_call("POST", "/api/todos", {"content": ""})
        check("content 为空串返回 422", code, 422)
        check("422 错误码是 validation_error", body["code"], "validation_error")
        # 这条 422 证明：非法请求【根本没有】到达 service / dao / 数据库，
        # Pydantic Schema 在最外层就把它挡掉了 —— 这是 Schema 的本职。

        # ── 5.7 DELETE → 204；再删 → 404 ─────────────────────────────
        code, body, _ = http_call("DELETE", f"/api/todos/{created_ids[0]}")
        check("DELETE 返回 204", code, 204)
        check("204 无响应体", body, None)
        created_ids.remove(created_ids[0])

        code, body, _ = http_call("DELETE", f"/api/todos/{created_ids[0] if created_ids else 999999999}")
        check("重复 DELETE 返回 404", code, 404)

        # ── 5.8 done 过滤（查询参数透传到 SQL where）──────────────────
        code, body, _ = http_call("GET", "/api/todos?done=true")
        check("done=true 过滤返回 200", code, 200)
        check_true("过滤结果里每条都是 done", all(i["done"] for i in body))

        # ── 5.9 OpenAPI 文档里 response schema 只有 3 个字段 ──────────
        # 这是"分离"在文档层面的证据：/openapi.json 描述的 TaskOut
        # 不含 ORM 的多余字段，前端拿它生成 TS 类型时不会被污染。
        code, spec, _ = http_call("GET", "/openapi.json")
        check("openapi.json 返回 200", code, 200)
        task_out_props = spec["components"]["schemas"]["TaskOut"]["properties"]
        check("OpenAPI 里 TaskOut 恰好 3 个属性", sorted(task_out_props), ["content", "done", "id"])
    finally:
        # HTTP 建的数据也按 id 精确清理（复用进程内 session）。
        if created_ids:
            factory = get_db_session_factory()
            cleanup_session = factory()
            cleanup_by_ids(cleanup_session, created_ids)
            cleanup_session.close()
        server.should_exit = True


# ══════════════════════════════════════════════════════════════════════
# 入口
# ══════════════════════════════════════════════════════════════════════

def main() -> None:
    print("=" * 72)
    print("Day 19 · 接口模型 vs ORM 模型分离 · 验证脚本")
    print("=" * 72)

    env_ok = section_1_field_contrast()
    if not env_ok:
        print("\n环境不满足，后续段落跳过。")
        sys.exit(1)

    section_2_from_attributes()
    section_3_detached_orm()
    section_4_service_crud()

    server = start_server()
    print(f"\n   （uvicorn 已在 {BASE} 就绪）")
    section_5_http_end_to_end(server)

    # ── 汇总 ─────────────────────────────────────────────────────────
    total = len(PASSED)
    failed = total - sum(PASSED)
    print(f"\n{'═' * 72}")
    print(f"断言汇总：共 {total} 条，通过 {total - failed} 条，失败 {failed} 条")
    print(f"{'═' * 72}")

    # 收尾自检：demo 前缀的数据应当已全部清理干净，不在库里留垃圾。
    factory = get_db_session_factory()
    verify = factory()
    try:
        leftovers = verify.scalars(
            select(Todo.id).where(Todo.content.like(f"{DEMO_PREFIX}%"))
        ).all()
        if leftovers:
            print(f"[WARN] 库里还残留 {len(leftovers)} 条 demo 数据：{list(leftovers)}")
            print("       （脚本中断过？可手动执行 POST /api/todos/reset 或按 id 删除）")
        else:
            print("[OK]  demo 数据已全部清理，库里无残留")
    finally:
        verify.close()

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
