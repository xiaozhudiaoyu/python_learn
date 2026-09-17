# Day 17 · 关联关系 + 分页 · 一键验证脚本
#
# 运行（项目根目录 e:/python_learn 下）：
#     .\.venv\Scripts\python.exe run_day17_demo.py
#
# 前置条件：day15_orm/db_config_local.py 已配好 MySQL 连接（见 Day 15）；
#           users / todos 两张表已存在（Day 15 建的）。
#
# 本脚本验证 Day 17 的全部学习目标：
#   ① Schema 迁移：给 todos 加 owner_id 列 + FK 约束；建 tags / todo_tags 新表
#   ② 幂等预清理 + 基线
#   ③ 一对多：创建 User 与 Todo 的 FK 关联
#   ④ relationship 双向导航 + back_populates 同步
#   ⑤ 懒加载 vs 急加载（N+1 问题与 selectinload 解法）
#   ⑥ 多对多：Todo ↔ Tag 经由中间表
#   ⑦ 分页查询：limit/offset + total count
#   ⑧ FK 行为验证：删 User 后 Todo.owner_id 自动变 NULL（SET NULL）
#   ⑨ 汇总
#
# 与 Day 15/16 同一套路：check() 收集断言、末尾汇总、有失败则退出码非 0。

import io
import sys
from typing import Any

from sqlalchemy import inspect, select, text

from day15_orm import (
    Tag,
    Todo,
    User,
    get_engine,
    get_session_factory,
    init_models,
    masked_url,
    session_scope,
)
from day16_crud import create_todo, create_user
from day17_relationship import (
    add_tags_to_todo,
    count_todos,
    create_todo_with_owner,
    get_todo_with_owner,
    get_todo_with_tags,
    get_user_with_todos,
    list_todos_by_owner,
    list_todos_by_tag,
    list_todos_paginated,
    remove_tag_from_todo,
)

PASSED: list[bool] = []

# 本次 demo 数据的标记前缀（幂等清理用）
USER_PREFIX = "day17-"
TODO_PREFIX = "day17:"
TAG_PREFIX = "day17-"

if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(errors="replace", line_buffering=True)


def check(label: str, actual: Any, expected: Any) -> None:
    ok = actual == expected
    PASSED.append(ok)
    mark = "[OK]  " if ok else "[FAIL]"
    print(f"   {mark} {label}：期望 {expected!r}，实际 {actual!r}")


# ─────────────────────────────────────────────────────────────────────────
# Schema 迁移辅助
# ─────────────────────────────────────────────────────────────────────────


def column_exists(engine: Any, table: str, column: str) -> bool:
    """检查数据库里某张表是否已有某列（用 inspect 反射）。"""
    insp = inspect(engine)
    columns = [c["name"] for c in insp.get_columns(table)]
    return column in columns


def table_exists(engine: Any, table: str) -> bool:
    """检查数据库里某张表是否存在。"""
    return table in inspect(engine).get_table_names()


def migrate_schema(engine: Any) -> list[str]:
    """执行 Day 17 所需的 schema 变更，返回执行过的操作列表。

    这里是手动 ALTER TABLE —— 正是这种"手工管迁移"的麻烦，
    催生了 Day 18 的 Alembic：它能自动对比模型与数据库的差异、生成迁移脚本。
    """
    actions: list[str] = []

    with engine.begin() as conn:
        # 1) todos 表加 owner_id 列 + FK 约束
        if not column_exists(engine, "todos", "owner_id"):
            conn.execute(text(
                "ALTER TABLE todos "
                "ADD COLUMN owner_id INTEGER NULL COMMENT '所属用户 ID，外键关联 users.id'"
            ))
            conn.execute(text(
                "ALTER TABLE todos "
                "ADD CONSTRAINT fk_todos_owner_id "
                "FOREIGN KEY (owner_id) REFERENCES users(id) "
                "ON DELETE SET NULL"
            ))
            actions.append("ALTER TABLE todos ADD COLUMN owner_id + FK")
        else:
            actions.append("todos.owner_id 已存在，跳过")

    # 2) tags / todo_tags 是新表，create_all(checkfirst=True) 幂等建表
    before = set(inspect(engine).get_table_names())
    init_models(engine)
    after = set(inspect(engine).get_table_names())
    new_tables = after - before
    if new_tables:
        actions.append(f"CREATE TABLE: {', '.join(sorted(new_tables))}")
    else:
        actions.append("tags / todo_tags 已存在，跳过")

    return actions


# ─────────────────────────────────────────────────────────────────────────
# 幂等预清理
# ─────────────────────────────────────────────────────────────────────────


def purge_demo_rows(engine: Any) -> tuple[int, int, int]:
    """清理本 demo 上次留下的数据，返回 (用户数, 待办数, 标签数)。"""
    with session_scope(engine) as session:
        # 先处理标签（多对多关联需要先断开）
        stale_tags: list[Tag] = []
        if table_exists(engine, "tags"):
            stale_tags = list(session.scalars(
                select(Tag).where(Tag.name.like(f"{TAG_PREFIX}%"))
            ).all())
            # 断开所有多对多关联（清中间表），避免删 Todo/Tag 时 FK 报错
            for tag in stale_tags:
                tag.todos.clear()
            session.flush()

        # 删待办
        stale_todos = list(session.scalars(
            select(Todo).where(Todo.content.like(f"{TODO_PREFIX}%"))
        ).all())
        for todo in stale_todos:
            session.delete(todo)
        session.flush()

        # 删标签
        for tag in stale_tags:
            session.delete(tag)
        session.flush()

        # 删用户
        stale_users = list(session.scalars(
            select(User).where(User.username.like(f"{USER_PREFIX}%"))
        ).all())
        for user in stale_users:
            session.delete(user)
        session.flush()

        return len(stale_users), len(stale_todos), len(stale_tags)


# ─────────────────────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 74)
    print("Day 17 · 关联关系（一对多 / 多对多）+ 分页查询")
    print("=" * 74)

    # ── ① Schema 迁移 ──────────────────────────────────────────────────
    print("\n【1】Schema 迁移（手动 ALTER TABLE —— Day 18 会用 Alembic 自动化这一步）")
    print(f"        连接：{masked_url()}")
    engine = get_engine()
    actions = migrate_schema(engine)
    for action in actions:
        print(f"        → {action}")
    check("todos 表有 owner_id 列", column_exists(engine, "todos", "owner_id"), True)
    check("tags 表已存在", table_exists(engine, "tags"), True)
    check("todo_tags 中间表已存在", table_exists(engine, "todo_tags"), True)

    # ── ② 幂等预清理 + 基线 ────────────────────────────────────────────
    print("\n【2】幂等预清理")
    purged_users, purged_todos, purged_tags = purge_demo_rows(engine)
    print(f"        清理：用户 {purged_users} 个、待办 {purged_todos} 条、标签 {purged_tags} 个")

    session_factory = get_session_factory(engine)

    # ── ③ 一对多：创建关联 ──────────────────────────────────────────────
    print("\n【3】一对多 —— ForeignKey 关联创建")
    with session_scope(engine) as session:
        alice = create_user(session, f"{USER_PREFIX}alice", email="alice@d17.dev")
        bob = create_user(session, f"{USER_PREFIX}bob")
        alice_id, bob_id = alice.id, bob.id

        # 给 alice 创建 3 条待办
        t1 = create_todo_with_owner(session, f"{TODO_PREFIX} 学 ForeignKey", alice_id)
        t2 = create_todo_with_owner(session, f"{TODO_PREFIX} 学 relationship", alice_id)
        t3 = create_todo_with_owner(session, f"{TODO_PREFIX} 学分页查询", alice_id)
        # 给 bob 创建 2 条待办
        t4 = create_todo_with_owner(session, f"{TODO_PREFIX} bob 的任务A", bob_id)
        t5 = create_todo_with_owner(session, f"{TODO_PREFIX} bob 的任务B", bob_id)
        # 一条"无主"待办（owner_id=NULL）
        t6 = create_todo(session, f"{TODO_PREFIX} 公共待办（无主）")

        t1_id, t2_id, t3_id = t1.id, t2.id, t3.id
        t4_id, t5_id, t6_id = t4.id, t5.id, t6.id

        check("create_todo_with_owner 后 owner_id 已设置", t1.owner_id, alice_id)
        check("无主待办 owner_id 为 None", t6.owner_id, None)

    # 用新 session 验证落库
    with session_scope(engine) as session:
        alice_todos = list_todos_by_owner(session, alice_id)
        bob_todos = list_todos_by_owner(session, bob_id)
        check("alice 名下有 3 条待办", len(alice_todos), 3)
        check("bob 名下有 2 条待办", len(bob_todos), 2)

    # ── ④ relationship 双向导航 ─────────────────────────────────────────
    print("\n【4】relationship 双向导航 + back_populates 同步")
    with session_scope(engine) as session:
        # 从 User 端导航到 Todos
        alice = session.get(User, alice_id)
        assert alice is not None
        alice_todo_ids = {t.id for t in alice.todos}
        check("user.todos 包含 alice 的 3 条待办", alice_todo_ids, {t1_id, t2_id, t3_id})

        # 从 Todo 端导航到 User
        todo1 = session.get(Todo, t1_id)
        assert todo1 is not None
        check("todo.owner 指向 alice", todo1.owner is not None and todo1.owner.username, f"{USER_PREFIX}alice")

        # back_populates 同步验证：在 Python 端改一侧，另一侧自动更新
        # 把 t6（无主待办）分配给 bob
        t6 = session.get(Todo, t6_id)
        bob = session.get(User, bob_id)
        assert t6 is not None and bob is not None
        t6.owner = bob  # 从"多"端设置
        session.flush()
        check("设置 todo.owner 后，user.todos 自动包含它（back_populates 同步）",
              t6_id in {t.id for t in bob.todos}, True)

        # 反向：从"一"端 append
        t7 = Todo(content=f"{TODO_PREFIX} 通过 user.todos.append 创建", owner_id=None)
        session.add(t7)
        session.flush()
        t7_id = t7.id
        alice.todos.append(t7)  # 从"一"端 append
        session.flush()
        check("user.todos.append 后，todo.owner_id 自动填充（back_populates 同步）",
              t7.owner_id, alice_id)

    # ── ⑤ 懒加载 vs 急加载 ──────────────────────────────────────────────
    print("\n【5】懒加载 vs 急加载（N+1 问题与 selectinload 解法）")
    # 5a 懒加载：访问 user.todos 时才触发 SQL
    print("   5a 懒加载演示（默认行为）")
    session = session_factory()
    try:
        alice = session.get(User, alice_id)
        # 此刻 alice.todos 还没加载 —— 只有访问时才发 SQL
        # 用 inspect 查看对象的加载状态
        state = inspect(alice)
        # 'todos' 在 unloaded 属性里（还没被访问过）
        unloaded = state.unloaded
        check("刚 get 出来的 User，todos 属性处于未加载状态", "todos" in unloaded, True)
        # 访问后触发懒加载
        _ = alice.todos
        # 重新获取 unloaded 状态（它每次访问都是实时计算，不是缓存）
        check("访问 user.todos 后属性已加载", "todos" in inspect(alice).unloaded, False)
    finally:
        session.close()

    # 5b 急加载：selectinload 一次性预加载
    print("   5b 急加载演示（selectinload）")
    with session_scope(engine) as session:
        alice_eager = get_user_with_todos(session, alice_id)
        assert alice_eager is not None
        state = inspect(alice_eager)
        check("selectinload 后，todos 属性已预加载（不在 unloaded 里）",
              "todos" in state.unloaded, False)
        check("预加载的数据正确：alice 有 4 条待办（3 + t7）",
              len(alice_eager.todos), 4)

    # 5c 多对一的急加载
    with session_scope(engine) as session:
        todo_loaded = get_todo_with_owner(session, t1_id)
        assert todo_loaded is not None
        check("get_todo_with_owner 预加载了 owner",
              todo_loaded.owner is not None and todo_loaded.owner.id, alice_id)

    # ── ⑥ 多对多：Todo ↔ Tag ────────────────────────────────────────────
    print("\n【6】多对多 —— Todo ↔ Tag（经由中间表 todo_tags）")
    with session_scope(engine) as session:
        # 给 t1 打标签
        tagged_t1 = add_tags_to_todo(session, t1_id, [f"{TAG_PREFIX}ORM", f"{TAG_PREFIX}基础"])
        assert tagged_t1 is not None
        check("t1 打上 2 个标签", len(tagged_t1.tags), 2)
        tag_names = {t.name for t in tagged_t1.tags}
        check("标签名正确", tag_names, {f"{TAG_PREFIX}ORM", f"{TAG_PREFIX}基础"})

        # 给 t2 和 t4 也打上同一个标签（验证"多对多"：一个标签属于多个 Todo）
        add_tags_to_todo(session, t2_id, [f"{TAG_PREFIX}ORM"])
        add_tags_to_todo(session, t4_id, [f"{TAG_PREFIX}ORM", f"{TAG_PREFIX}bob"])

        # 给 t3 打一个独有标签
        add_tags_to_todo(session, t3_id, [f"{TAG_PREFIX}分页"])

    # 用新 session 验证
    with session_scope(engine) as session:
        # 从 Tag 端导航：查所有带 "day17-ORM" 标签的 Todo
        orm_todos = list_todos_by_tag(session, f"{TAG_PREFIX}ORM")
        check("标签 'day17-ORM' 关联了 3 条待办（t1, t2, t4）", len(orm_todos), 3)
        orm_todo_ids = {t.id for t in orm_todos}
        check("关联的 id 正确", orm_todo_ids, {t1_id, t2_id, t4_id})

        # 从 Todo 端导航：查 t1 的标签
        t1_loaded = get_todo_with_tags(session, t1_id)
        assert t1_loaded is not None
        check("t1 有 2 个标签", len(t1_loaded.tags), 2)

        # 解除关联：从 t1 移除 "day17-基础" 标签
        removed = remove_tag_from_todo(session, t1_id, f"{TAG_PREFIX}基础")
        check("解除关联返回 True", removed, True)
    with session_scope(engine) as session:
        t1_after = get_todo_with_tags(session, t1_id)
        assert t1_after is not None
        check("解除后 t1 只剩 1 个标签", len(t1_after.tags), 1)
        check("剩下的是 'day17-ORM'", t1_after.tags[0].name, f"{TAG_PREFIX}ORM")

        # 验证 Tag 本身还在（只是断开了和 t1 的关联，没删 Tag）
        tag_still_exists = session.scalars(
            select(Tag).where(Tag.name == f"{TAG_PREFIX}基础")
        ).first()
        check("Tag '基础' 本身未被删除（只解除关联）", tag_still_exists is not None, True)

    # ── ⑦ 分页查询 ──────────────────────────────────────────────────────
    print("\n【7】分页查询 —— limit/offset + total count")
    with session_scope(engine) as session:
        # 先确认总数（本 demo 创建了 t1~t7 共 7 条带 day17: 前缀的待办）
        total_all = count_todos(session)
        total_alice = count_todos(session, owner_id=alice_id)
        total_bob = count_todos(session, owner_id=bob_id)
        print(f"        全部待办：{total_all}，alice 名下：{total_alice}，bob 名下：{total_bob}")
        check("alice 有 4 条待办", total_alice, 4)
        check("bob 有 3 条待办（t4 + t5 + t6）", total_bob, 3)

        # 分页：每页 2 条，取 alice 的第 1 页
        page1, total = list_todos_paginated(session, page=1, page_size=2, owner_id=alice_id)
        check("第 1 页返回 2 条", len(page1), 2)
        check("total 为 4", total, 4)

        # 第 2 页
        page2, total2 = list_todos_paginated(session, page=2, page_size=2, owner_id=alice_id)
        check("第 2 页返回 2 条", len(page2), 2)
        check("两页不重复", {t.id for t in page1} & {t.id for t in page2}, set())
        check("total 一致", total2, 4)

        # 第 3 页（超出范围，应返回空）
        page3, total3 = list_todos_paginated(session, page=3, page_size=2, owner_id=alice_id)
        check("第 3 页为空（超出范围）", len(page3), 0)
        check("total 仍然是 4", total3, 4)

        # 带 owner 预加载的分页
        page1_with_owner, _ = list_todos_paginated(
            session, page=1, page_size=3, owner_id=alice_id, with_owner=True
        )
        check("with_owner=True 后每条 todo 的 owner 已预加载",
              all(t.owner is not None for t in page1_with_owner), True)

        # 全局分页（不过滤 owner）
        all_page1, all_total = list_todos_paginated(session, page=1, page_size=3)
        check("全局分页 total >= 7（至少有本 demo 的 7 条）", all_total >= 7, True)
        check("全局分页第 1 页返回 3 条", len(all_page1), 3)

    # ── ⑧ FK 行为验证：ON DELETE SET NULL ────────────────────────────────
    print("\n【8】FK 行为 —— 删 User 后 Todo.owner_id 自动变 NULL（SET NULL）")
    # bob 有 3 条待办（t4, t5, t6），删 bob 后这 3 条的 owner_id 应变成 NULL
    with session_scope(engine) as session:
        bob_todos_before = list_todos_by_owner(session, bob_id)
        check("删 bob 前：bob 名下有 3 条待办", len(bob_todos_before), 3)

    with session_scope(engine) as session:
        # 用原生 SQL 删 bob —— 绕过 ORM，纯验证数据库层的 ON DELETE SET NULL
        session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": bob_id})

    with session_scope(engine) as session:
        # bob 的待办应该还在，但 owner_id 变成 NULL
        t4_after = session.get(Todo, t4_id)
        t5_after = session.get(Todo, t5_id)
        t6_after = session.get(Todo, t6_id)
        check("删 bob 后 t4 仍存在", t4_after is not None, True)
        check("t4.owner_id 变成 NULL（SET NULL 生效）", t4_after.owner_id if t4_after else "N/A", None)
        check("t5.owner_id 变成 NULL", t5_after.owner_id if t5_after else "N/A", None)
        check("t6.owner_id 变成 NULL", t6_after.owner_id if t6_after else "N/A", None)
        check("bob 用户已不存在", session.get(User, bob_id), None)

        # alice 的待办不受影响
        alice_todos_after = list_todos_by_owner(session, alice_id)
        check("alice 名下待办不受 bob 删除影响（仍为 4 条）", len(alice_todos_after), 4)

    # ── ⑨ 汇总 ──────────────────────────────────────────────────────────
    print("\n【9】汇总 —— 本次 demo 留在库里的数据")
    with session_scope(engine) as session:
        left_users = list(session.scalars(
            select(User).where(User.username.like(f"{USER_PREFIX}%")).order_by(User.id)
        ).all())
        left_todos = list(session.scalars(
            select(Todo).where(Todo.content.like(f"{TODO_PREFIX}%")).order_by(Todo.id)
        ).all())
        left_tags = list(session.scalars(
            select(Tag).where(Tag.name.like(f"{TAG_PREFIX}%")).order_by(Tag.id)
        ).all())

    print(f"        users（{len(left_users)}）：")
    for u in left_users:
        print(f"            {u!r}  email={u.email!r}")
    print(f"        todos（{len(left_todos)}）：")
    for t in left_todos:
        print(f"            {t!r}")
    print(f"        tags（{len(left_tags)}）：")
    for tg in left_tags:
        print(f"            {tg!r}")
    print("        想清掉它们：重跑本脚本（开头幂等预清理），或手动删标记前缀行。")

    engine.dispose()

    total_assertions, passed = len(PASSED), sum(PASSED)
    print("\n" + "=" * 74)
    print(f"断言结果：{passed}/{total_assertions} 通过"
          + ("" if passed == total_assertions else "  ← 有未通过项，见上面 [FAIL]"))
    print("=" * 74)
    print("Day 18 预告：用 Alembic 管理数据库结构迁移 —— 再也不用手写 ALTER TABLE。")
    sys.exit(0 if passed == total_assertions else 1)


if __name__ == "__main__":
    main()
