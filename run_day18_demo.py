# Day 18 · Alembic 数据库迁移 · 一键验证脚本
#
# 运行（项目根目录 e:/python_learn 下）：
#     .\.venv\Scripts\python.exe run_day18_demo.py
#
# 前置条件：
#   · day15_orm/db_config_local.py 已配好 MySQL 连接（见 Day 15）；
#   · day18_alembic/ 迁移环境已就位，库里已 stamp 到基线（开发时已完成）：
#       versions/6ddbf4e09cce_baseline_initial_schema.py   基线：建 4 张表
#       versions/1145bfe61b0a_add_priority_to_todos.py     增量：todos 加 priority
#
# 本脚本验证 Day 18 的全部学习目标：
#   ① 迁移链路：alembic 把 schema 变更记录成有版本、可前进/回退的脚本
#   ② upgrade：把库推进到 head（priority 列存在）
#   ③ downgrade：回退一个版本（priority 列消失），且【只删列不删行】
#   ④ 再 upgrade：恢复到 head，老行被 server_default 回填为 2
#   ⑤ 全程外来表 user/account 不受影响（env.py 的 include_object 在保护）
#
# 为什么不像 Day 15~17 那样用 create_all()？
#   create_all() 只在“表不存在”时建表，表一旦建好就不再管——它无法表达
#   “给已有的表加一列”这种演进。真实项目的表结构是一点点改出来的，每次
#   改动都要能在别人机器上重放、也能回退，这正是 Alembic 的职责。
#   （本 demo 里的 1145bfe61b0a 就是开发时改了 models.py 后 autogenerate 出来的。）
#
# 与 Day 15/16/17 同一套路：check() 收集断言、末尾汇总、有失败则退出码非 0。
# 说明：输出里夹带的 INFO [alembic...] 日志是 Alembic 自己打的，正好证明迁移
#       是真的在数据库上跑，不是我们假装说说。

import io
import sys
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from day15_orm import get_engine, masked_url

PASSED: list[bool] = []

# 项目根目录（本脚本就放在根目录），用来给 alembic 定位 ini 与迁移目录，
# 这样即使从别的工作目录运行也不受影响。
PROJECT_ROOT = Path(__file__).resolve().parent

# 迁移过程中会被反复读行数的表。user / account 是早期 sqlalchemy_learn/ 实验
# 遗留的“外来表”，不在本项目模型里，专门留着验证 include_object 有没有护住它们。
COUNT_TABLES = ["users", "todos", "tags", "todo_tags", "user", "account"]

if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(errors="replace", line_buffering=True)


def check(label: str, actual: Any, expected: Any) -> None:
    ok = actual == expected
    PASSED.append(ok)
    mark = "[OK]  " if ok else "[FAIL]"
    print(f"   {mark} {label}：期望 {expected!r}，实际 {actual!r}")


# ─────────────────────────────────────────────────────────────────────────
# 数据库状态探针（全部实时查询、不复用连接与 Inspector 缓存，
# 确保每次读到的都是迁移之后的最新结构，而不是上一刻的旧快照）
# ─────────────────────────────────────────────────────────────────────────


def make_config() -> Config:
    """构造 Alembic 配置：用绝对路径锁定 ini 与迁移目录，免受 cwd 影响。"""
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "day18_alembic"))
    return cfg


def current_revision(engine: Any) -> str | None:
    """库里 alembic_version 记录的当前版本号（尚无版本表时为 None）。"""
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def todos_columns(engine: Any) -> list[str]:
    """todos 表当前的列名。每次新建 Inspector 实时反射，避免缓存到旧结构。"""
    return [c["name"] for c in inspect(engine).get_columns("todos")]


def db_table_names(engine: Any) -> set[str]:
    """库里当前所有表名（用来确认外来表还在不在）。"""
    return set(inspect(engine).get_table_names())


def row_counts(engine: Any) -> dict[str, int]:
    """一次性抓取所有关注表的行数，用于迁移前后对比。"""
    counts: dict[str, int] = {}
    with engine.connect() as conn:
        for t in COUNT_TABLES:
            counts[t] = int(conn.execute(text(f"SELECT COUNT(*) FROM `{t}`")).scalar() or 0)
    return counts


def priority_distribution(engine: Any) -> list[tuple[int, int]]:
    """todos.priority 的取值分布 [(优先级, 行数), ...]；列不存在时会抛异常。"""
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT priority, COUNT(*) FROM todos GROUP BY priority ORDER BY priority"
        )).fetchall()
        return [(r[0], r[1]) for r in rows]


# ─────────────────────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 74)
    print("Day 18 · Alembic 数据库迁移 —— upgrade / downgrade 全流程验证")
    print("=" * 74)
    print(f"        连接：{masked_url()}")

    cfg = make_config()
    engine = get_engine()

    # 从迁移脚本目录里读出“基线版本”和“最新版本”，不写死 revision id，
    # 这样即使以后重新生成迁移、id 变了，本脚本也不用改。
    script = ScriptDirectory.from_config(cfg)
    head_rev = script.get_current_head()
    base_rev = script.get_bases()[0]
    chain = [s.revision for s in script.walk_revisions()]  # 从新到旧

    # ── ① 迁移链路 ──────────────────────────────────────────────────────
    print("\n【1】迁移链路（alembic 把 schema 变更记录成可版本化的脚本）")
    print(f"        基线版本 base = {base_rev}")
    print(f"        最新版本 head = {head_rev}")
    print(f"        脚本链（新→旧）= {chain}")
    check("迁移脚本共 2 个版本（基线 + 加 priority）", len(chain), 2)
    check("基线与最新不是同一个版本", base_rev != head_rev, True)

    # 动手之前先记录所有表的行数，作为“基准快照”，后面每步都拿它对比。
    baseline_counts = row_counts(engine)
    todos_count = baseline_counts["todos"]
    print(f"        迁移前各表行数：{baseline_counts}")

    try:
        # ── ② upgrade 到 head：priority 列应在 ──────────────────────────
        print("\n【2】upgrade head —— 把库推进到最新版本（priority 列应存在）")
        command.upgrade(cfg, "head")
        check("当前版本 == head", current_revision(engine), head_rev)
        check("todos 有 priority 列", "priority" in todos_columns(engine), True)
        check("upgrade 未改动任何表的行数", row_counts(engine), baseline_counts)

        # ── ③ downgrade 回基线：priority 列消失 ─────────────────────────
        print("\n【3】downgrade -1 —— 回退一个版本（drop 掉 priority 列）")
        print("        注意：drop_column 会丢掉该列数据；本 demo 里 priority 只是默认值 2，无实质损失。")
        command.downgrade(cfg, "-1")
        check("当前版本 == 基线", current_revision(engine), base_rev)
        check("priority 列已消失", "priority" in todos_columns(engine), False)
        counts_after_down = row_counts(engine)
        check("downgrade 只删列不删行（todos 行数不变）", counts_after_down["todos"], todos_count)
        check("downgrade 未改动任何表的行数", counts_after_down, baseline_counts)
        names_after_down = db_table_names(engine)
        check("外来表 user 未被误删", "user" in names_after_down, True)
        check("外来表 account 未被误删", "account" in names_after_down, True)

        # ── ④ 再 upgrade 到 head：priority 回来 + 老行回填 ──────────────
        print("\n【4】再 upgrade head —— 恢复 priority 列，老行被 server_default 回填")
        command.upgrade(cfg, "head")
        check("当前版本 == head", current_revision(engine), head_rev)
        check("priority 列已恢复", "priority" in todos_columns(engine), True)
        check("老行全部被回填为优先级 2", priority_distribution(engine), [(2, todos_count)])
        counts_after_up = row_counts(engine)
        check("恢复后各表行数仍与基准一致", counts_after_up, baseline_counts)
        names_after_up = db_table_names(engine)
        check("全程外来表 user 仍在", "user" in names_after_up, True)
        check("全程外来表 account 仍在", "account" in names_after_up, True)
    finally:
        # 安全网：无论断言结果如何，都确保结束时停在 head（priority 列在）。
        # 否则 ORM 模型（已声明 priority）会与库结构不一致，连累 Day16/17 的插入。
        # happy path 下此刻已在 head，条件为假，不会多跑一次、也不会多打日志。
        if current_revision(engine) != head_rev:
            command.upgrade(cfg, "head")

    # ── ⑤ 汇总 ──────────────────────────────────────────────────────────
    print("\n【5】汇总 —— 迁移走完一圈后的库结构")
    print(f"        最终版本：{current_revision(engine)} (head)")
    print(f"        todos 列：{todos_columns(engine)}")
    print(f"        各表行数：{row_counts(engine)}")
    print("        一句话：改模型 → autogenerate 出迁移 → upgrade 落库 → 需要时 downgrade 回退，")
    print("               每一步都有版本、可重放、可撤销，这就是它比 create_all 强的地方。")

    engine.dispose()

    total_assertions, passed = len(PASSED), sum(PASSED)
    print("\n" + "=" * 74)
    print(f"断言结果：{passed}/{total_assertions} 通过"
          + ("" if passed == total_assertions else "  ← 有未通过项，见上面 [FAIL]"))
    print("=" * 74)
    print("Day 19 预告：Pydantic 模型 vs ORM 模型的分离 —— 接口边界与持久层各司其职。")
    sys.exit(0 if passed == total_assertions else 1)


if __name__ == "__main__":
    main()
