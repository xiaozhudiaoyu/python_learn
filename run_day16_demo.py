# Day 16 · CRUD + Session 生命周期 · 一键验证脚本
#
# 运行（项目根目录 e:/python_learn 下）：
#     .\.venv\Scripts\python.exe run_day16_demo.py
#
# 前置条件：day15_orm/db_config_local.py 已配好 MySQL 连接（见 Day 15）；
#           users / todos 两张表已存在（Day 15 建的；本脚本开头也会幂等兜底建一次）。
#
# 本脚本验证 Day 16 的目标：用一组 DAO 函数覆盖全部 CRUD，并把 Session 的
# 创建 / 提交 / 回滚 / 关闭 与"事务边界"讲清楚：
#   ① 连接与基线 + 幂等预清理（只清带 day16- / day16: 标记的行）
#   ② Create + commit → flush 拿自增 id、再开新 session 验证真的落了库
#   ③ Read：单条(by id / by username)、列表、条件过滤(done)
#   ④ Update：改邮箱、把待办标记完成
#   ⑤ Delete：删存在的、删不存在的(幂等返回 False)
#   ⑥ Rollback：插入后回滚不留痕、唯一约束经 session_scope 自动回滚、自增号不复用
#   ⑦ 事务隔离：未提交时"自己可见 / 别的 session 不可见"，提交后才全局可见
#   ⑧ 汇总 + 打印本次留在库里的数据
#
# 与 run_day15_demo.py 同一套路：check() 收集断言、末尾汇总、有失败则退出码非 0。
#
# 【重要】与 Day 15「零残留」不同：本次按需求【保留】CRUD 结果数据供你在 SQL 客户端查看。
#         留下的行都带标记（username 以 day16- 开头、content 以 day16: 开头）；
#         重跑本脚本会先幂等清掉这些标记行再重建，绝不触碰你库里的其它数据。

import io
import sys
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from day15_orm import (
    Todo,
    User,
    get_engine,
    get_session_factory,
    init_models,
    masked_url,
    session_scope,
)
from day16_crud import (
    create_todo,
    create_user,
    delete_todo,
    delete_user,
    get_todo,
    get_user,
    get_user_by_username,
    list_todos,
    list_users,
    set_todo_done,
    update_user_email,
)

PASSED: list[bool] = []

# 本次 demo 所有数据都带这两个前缀，作为"这是我造的、可以安全清理"的标记。
# 用连字符 day16- 和冒号 day16: 而不是下划线：LIKE 里下划线 _ 是"任意单字符"通配符，
# 用 day16_ 做前缀去 LIKE 匹配会误伤 day16X... 之类；连字符和冒号不是通配符，匹配才精确。
USER_PREFIX = "day16-"
TODO_PREFIX = "day16:"

if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(errors="replace", line_buffering=True)


def check(label: str, actual: Any, expected: Any) -> None:
    ok = actual == expected
    PASSED.append(ok)
    mark = "[OK]  " if ok else "[FAIL]"
    print(f"   {mark} {label}：期望 {expected!r}，实际 {actual!r}")


# ── 下面几个 committed_* 辅助函数都【另开一个全新 session】去读 ──────────────
# 为什么？因为验证"数据真的提交进库了"必须换一个事务去查：
# 如果在刚写完的那个 session 里查，就算没 commit 也能查到（自己事务内可见），
# 那样根本证明不了"已落库"。换个新 session（= 新事务、新连接）还查得到，才算数。
def committed_user_count(engine: Any) -> int:
    with session_scope(engine) as session:
        return int(session.scalar(select(func.count()).select_from(User)) or 0)


def committed_todo_count(engine: Any, done: bool | None = None) -> int:
    with session_scope(engine) as session:
        return len(list_todos(session, done))


def committed_get_user_by_username(engine: Any, username: str) -> User | None:
    with session_scope(engine) as session:
        return get_user_by_username(session, username)


def committed_get_todo(engine: Any, todo_id: int) -> Todo | None:
    with session_scope(engine) as session:
        return get_todo(session, todo_id)


def purge_demo_rows(engine: Any) -> tuple[int, int]:
    """幂等预清理：只删本 demo 自己打标记的行，返回删掉的 (用户数, 待办数)。

    放在最前面，是为了让脚本可以反复运行：上一次留下的 day16- 用户先清掉，
    这一次再重建，就不会撞上 users.username 的唯一约束。
    删除范围严格限定在标记前缀内（like 'day16-%' / 'day16:%'），别的数据一概不碰。
    """
    with session_scope(engine) as session:
        stale_users = list(session.scalars(select(User).where(User.username.like(f"{USER_PREFIX}%"))).all())
        stale_todos = list(session.scalars(select(Todo).where(Todo.content.like(f"{TODO_PREFIX}%"))).all())
        for user in stale_users:
            session.delete(user)
        for todo in stale_todos:
            session.delete(todo)
        return len(stale_users), len(stale_todos)


def main() -> None:
    print("=" * 74)
    print("Day 16 · CRUD + Session 生命周期（DAO / 提交 / 回滚 / 事务边界）")
    print("=" * 74)

    # ── ① 连接与基线 + 幂等预清理 ────────────────────────────────────────
    print("\n【1】连接配置与基线")
    masked = masked_url()
    print(f"        {masked}")
    check("连接串里口令位置已打码成 ***", "***" in masked, True)

    engine = get_engine()
    # 兜底：Day 15 已建过表，这里幂等再确保一次（checkfirst=True，已存在就跳过），
    # 这样即便在没跑过 Day 15 的新库上直接跑 Day 16 也不会因为缺表而失败。
    init_models(engine)

    purged_users, purged_todos = purge_demo_rows(engine)
    print(f"        幂等预清理：删掉上次遗留的 day16- 用户 {purged_users} 个、day16: 待办 {purged_todos} 条")
    base_users = committed_user_count(engine)
    base_todos = committed_todo_count(engine)
    print(f"        清理后基线行数：users={base_users}  todos={base_todos}")

    # session_factory 用来手动开 session（第 6、7 段要亲手控制 commit / rollback，
    # 不能用会自动提交的 session_scope）。
    session_factory = get_session_factory(engine)

    # ── ② Create + commit ────────────────────────────────────────────────
    print("\n【2】新增（Create）—— flush 拿 id，commit 后才对别人可见")
    # 一个 with session_scope 就是一个事务：里面连着调多个 DAO 函数，
    # 全部成功才在退出时统一 commit。这正是"DAO 不 commit、调用方定边界"的用法。
    with session_scope(engine) as session:
        alice = create_user(session, f"{USER_PREFIX}alice", email="alice@example.com")
        bob = create_user(session, f"{USER_PREFIX}bob")
        t1 = create_todo(session, f"{TODO_PREFIX} 学 CRUD 增删改查")
        t2 = create_todo(session, f"{TODO_PREFIX} 学事务边界")
        t3 = create_todo(session, f"{TODO_PREFIX} 一条已完成的任务", done=True)
        # create_user 内部 flush 过，此刻 id 已由数据库回填 —— 兑现 models.py:62 的伏笔。
        check("create_user 后立刻拿到自增 id（>0）", alice.id > 0, True)
        check("create_todo 后立刻拿到自增 id（>0）", t1.id > 0, True)
        alice_id, bob_id = alice.id, bob.id
        t1_id, t3_id = t1.id, t3.id
    # 出了 with 块，session_scope 已 commit。换新 session 验证"真的落库了"。
    check("提交后：新 session 查得到 alice", committed_get_user_by_username(engine, f"{USER_PREFIX}alice") is not None, True)
    check("提交后：新 session 查得到 bob", committed_get_user_by_username(engine, f"{USER_PREFIX}bob") is not None, True)
    check("提交后：用户数比基线多 2", committed_user_count(engine), base_users + 2)
    check("提交后：待办数比基线多 3", committed_todo_count(engine), base_todos + 3)

    # ── ③ Read ───────────────────────────────────────────────────────────
    print("\n【3】查询（Read）—— 单条 / 列表 / 条件过滤")
    with session_scope(engine) as session:
        by_id = get_user(session, alice_id)
        check("get_user(by id) 命中 alice", by_id is not None and by_id.username, f"{USER_PREFIX}alice")
        by_name = get_user_by_username(session, f"{USER_PREFIX}alice")
        check("get_user_by_username 命中且 id 与 alice 一致", by_name is not None and by_name.id, alice_id)
        check("get_user 查不存在的 id 返回 None", get_user(session, 99999999), None)

        users = list_users(session)
        names = {u.username for u in users}
        check("list_users 至少含 alice、bob", names >= {f"{USER_PREFIX}alice", f"{USER_PREFIX}bob"}, True)

        all_todos = list_todos(session)                 # 不过滤
        pending = list_todos(session, done=False)       # 只未完成
        done = list_todos(session, done=True)           # 只已完成
        check("list_todos(done=True) 全是已完成", all(t.done for t in done) and len(done) >= 1, True)
        check("list_todos(done=False) 全是未完成", all(not t.done for t in pending), True)
        check("全部 = 已完成 + 未完成（无遗漏无重复）", len(all_todos), len(pending) + len(done))

    # ── ④ Update ─────────────────────────────────────────────────────────
    print("\n【4】修改（Update）—— 改跟踪对象的属性，commit 时自动生成 UPDATE")
    with session_scope(engine) as session:
        updated = update_user_email(session, alice_id, "alice_new@example.com")
        check("update_user_email 返回改后对象、邮箱已变", updated is not None and updated.email, "alice_new@example.com")
        marked = set_todo_done(session, t1_id, True)
        check("set_todo_done 把 t1 标记为完成", marked is not None and marked.done, True)
        check("update 不存在的 id 返回 None", update_user_email(session, 99999999, "x@y.z"), None)
    alice_after = committed_get_user_by_username(engine, f"{USER_PREFIX}alice")
    check("提交后：新 session 里 alice 邮箱真的变了", alice_after is not None and alice_after.email, "alice_new@example.com")
    t1_after = committed_get_todo(engine, t1_id)
    check("提交后：新 session 里 t1.done 真的变 True", t1_after is not None and t1_after.done, True)

    # ── ⑤ Delete ─────────────────────────────────────────────────────────
    print("\n【5】删除（Delete）—— 删存在的返回 True，删不存在的返回 False")
    with session_scope(engine) as session:
        check("delete_user 删掉 bob 返回 True", delete_user(session, bob_id), True)
        check("delete_todo 删掉 t3 返回 True", delete_todo(session, t3_id), True)
        check("delete_user 删不存在的 id 返回 False（幂等）", delete_user(session, 99999999), False)
    check("提交后：bob 真的没了", committed_get_user_by_username(engine, f"{USER_PREFIX}bob"), None)
    check("提交后：t3 真的没了", committed_get_todo(engine, t3_id), None)

    # ── ⑥ Rollback ───────────────────────────────────────────────────────
    print("\n【6】回滚（Rollback）—— 事务边界的另一半：不提交就等于没发生")
    # 6a 手动开 session，插入后 flush（拿到 id）再 rollback
    print("   6a 插入 → flush → rollback，行不应留下")
    session = session_factory()
    try:
        temp = create_user(session, f"{USER_PREFIX}temp")   # 内部 flush，temp.id 已分配
        temp_id = temp.id
        check("rollback 前 temp 已拿到自增 id", temp_id > 0, True)
        session.rollback()                                   # 亲手回滚
    finally:
        session.close()
    check("rollback 后：新 session 查不到 temp", committed_get_user_by_username(engine, f"{USER_PREFIX}temp"), None)

    # 6b 唯一约束触发的"中途出错"，交给 session_scope 的 except 分支自动 rollback
    print("   6b 插入重复 username，session_scope 应自动回滚并把异常抛出来")
    raised = False
    detail = ""
    try:
        with session_scope(engine) as s:
            create_user(s, f"{USER_PREFIX}alice")   # 与 §2 已提交的 alice 重名，flush 即违反唯一索引
    except IntegrityError as error:
        raised = True
        detail = str(error.orig)   # orig 是 PyMySQL 的原始报错，带 MySQL 错误信息
    print(f"        数据库原始报错：{detail}")
    check("重复 username 触发 IntegrityError", raised, True)
    check("报错指向唯一约束（Duplicate entry）", "Duplicate entry" in detail, True)

    # 6c 回滚"烧掉"的自增号不会被复用 —— 这就是基线里 counter 跳号的原因
    print("   6c 回滚不复位自增计数器：回滚后再提交的行，id 比被回滚的更大")
    with session_scope(engine) as session2:
        carol = create_user(session2, f"{USER_PREFIX}carol")
        carol_id = carol.id
    check("carol（回滚之后才提交）的 id 大于被回滚的 temp.id", carol_id > temp_id, True)

    # ── ⑦ 事务隔离：commit 才是"对别人可见"的分界线 ───────────────────────
    print("\n【7】事务边界 / 隔离 —— 未提交的改动只有自己看得见")
    session_a = session_factory()   # A：制造一个"改了但还没提交"的事务
    session_b = session_factory()   # B：另一个连接、另一个事务，用来观察 A 的可见性
    try:
        create_user(session_a, f"{USER_PREFIX}iso")   # A 里 flush，但先不 commit
        check("A 事务内能查到自己刚插入(未提交)的 iso",
              get_user_by_username(session_a, f"{USER_PREFIX}iso") is not None, True)
        check("A 未提交时，另一个 session B 查不到 iso",
              get_user_by_username(session_b, f"{USER_PREFIX}iso"), None)
        session_a.commit()   # A 提交，越过"事务边界"
        # 用全新 session 查（不复用 B：MySQL 默认 REPEATABLE READ，
        # B 的快照停在它第一次查询的时刻，即使 A 提交了 B 也可能仍看不到）。
        check("A 提交后，全新 session 就能查到 iso 了",
              committed_get_user_by_username(engine, f"{USER_PREFIX}iso") is not None, True)
    finally:
        session_a.close()
        session_b.close()
    # iso 只是隔离演示的临时行，清掉，不留在最终数据里
    with session_scope(engine) as session:
        iso_user = get_user_by_username(session, f"{USER_PREFIX}iso")
        if iso_user is not None:
            delete_user(session, iso_user.id)
    check("清理后 iso 已不在库里", committed_get_user_by_username(engine, f"{USER_PREFIX}iso"), None)

    # ── ⑧ 汇总 + 留在库里的数据 ──────────────────────────────────────────
    print("\n【8】本次 demo 留在库里的数据（按需求保留，供你在 SQL 客户端查看）")
    with session_scope(engine) as session:
        left_users = [u for u in list_users(session) if u.username.startswith(USER_PREFIX)]
        left_todos = [t for t in list_todos(session) if t.content.startswith(TODO_PREFIX)]
    print("        users：")
    for user in left_users:
        print(f"            {user!r}  email={user.email!r}")
    print("        todos：")
    for todo in left_todos:
        print(f"            {todo!r}")
    print("        想清掉它们：删 username 以 'day16-' 开头、content 以 'day16:' 开头的行；")
    print("                    或直接重跑本脚本——开头的幂等预清理会先删标记行再重建。")

    engine.dispose()   # 关掉连接池，避免脚本退出后留一堆 CLOSE_WAIT

    total, passed = len(PASSED), sum(PASSED)
    print("\n" + "=" * 74)
    print(f"断言结果：{passed}/{total} 通过" + ("" if passed == total else "  ← 有未通过项，见上面 [FAIL]"))
    print("=" * 74)
    print("Day 17 预告：给 Todo 加 users 外键与 relationship（一对多），并实现 limit/offset 分页。")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
