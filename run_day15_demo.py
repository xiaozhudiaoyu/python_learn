# Day 15 · SQLAlchemy 2 基础 · 一键验证脚本
#
# 运行（项目根目录 e:/python_learn 下）：
#     .\.venv\Scripts\python.exe run_day15_demo.py
#
# 前置条件：先按 day15_orm/db_config_local_example.py 建好本地配置文件
#           day15_orm/db_config_local.py 并填入 MySQL 连接信息（该文件不会被提交）。
#
# 本脚本验证 Day 15 的三个目标：engine/session、ORM 模型定义、建表。
#   ① 环境与连接串（口令打码）
#   ② 实测连通：SELECT VERSION() / DATABASE() / @@sql_mode
#   ③ create_all() 建表 → 反射断言 users / todos 真的出现了
#   ④ 逐列断言：类型、NOT NULL、主键、唯一索引、两种默认值的差别
#   ⑤ 打印 MySQL 方言下真实的 CREATE TABLE 语句，看清 ORM 生成了什么
#   ⑥ 幂等性：create_all() 再跑一次不报错、不重复建
#   ⑦ 事务冒烟：插入 → 验证 → rollback，并断言约束真的拦得住、库里零残留
#
# 与 run_day13_demo.py 同一套路：check() 收集断言、末尾汇总、失败时退出码非 0。
# 区别是本脚本不需要起 HTTP 服务，直连数据库。
#
# 【重要】本脚本对你的数据库只做两件事：建 users / todos 两张表、
#         以及在事务里插入几条数据后【立即 rollback】。
#         不删表、不改表、不留任何数据。

import io
import sys
import time
from datetime import datetime
from typing import Any

from sqlalchemy import Table, func, inspect, select, text
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateTable

from day15_orm import (
    Base,
    Todo,
    User,
    existing_tables,
    get_engine,
    get_session_factory,
    init_models,
    masked_url,
    session_scope,
)

PASSED: list[bool] = []

if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(errors="replace", line_buffering=True)


def check(label: str, actual: Any, expected: Any) -> None:
    ok = actual == expected
    PASSED.append(ok)
    mark = "[OK]  " if ok else "[FAIL]"
    print(f"   {mark} {label}：期望 {expected!r}，实际 {actual!r}")


def compile_ddl(table: Table) -> str:
    """把表对象编译成 MySQL 方言下的 CREATE TABLE 文本，【只翻译不执行】。

    compile(dialect=mysql.dialect()) 不会连数据库、不会发任何语句，
    纯粹在本地把表结构渲染成 SQL 字符串，所以可以随便调用、随便打印。
    """
    return str(CreateTable(table).compile(dialect=mysql.dialect())).strip()


def main() -> None:
    stamp = time.strftime("%H%M%S")

    print("=" * 74)
    print("Day 15 · SQLAlchemy 2 基础（engine / session / ORM 模型 / 建表）")
    print("=" * 74)

    # ── ① 环境与连接串 ────────────────────────────────────────────────
    print("\n【1】连接配置（口令已打码，可以安全截图）")
    masked = masked_url()
    print(f"        {masked}")
    check("连接串里口令位置已替换成 ***", "***" in masked, True)

    # engine 是整个进程共用一个：它内部是连接池，不是"一次连接"
    engine = get_engine()
    print("        engine =", engine)

    # ── ② 实测连通 ────────────────────────────────────────────────────
    print("\n【2】连通性实测（真的连上去问数据库，不是只看配置像不像）")
    # text() 把一段裸 SQL 包成 SQLAlchemy 能执行的对象。
    # 这三句用裸 SQL 而不是 ORM，是因为"服务端版本 / 当前库 / sql_mode"
    # 本来就不属于任何一张表，ORM 管不着。
    with engine.connect() as conn:
        version = conn.execute(text("SELECT VERSION()")).scalar()
        current_db = conn.execute(text("SELECT DATABASE()")).scalar()
        sql_mode = conn.execute(text("SELECT @@sql_mode")).scalar()
    print(f"        服务端版本 = {version}")
    print(f"        当前库     = {current_db}")
    print(f"        sql_mode   = {sql_mode}")
    check("拿到了服务端版本号", isinstance(version, str) and version != "", True)
    check("连接落在配置指定的库上", isinstance(current_db, str) and current_db != "", True)
    # sql_mode 里有没有 STRICT_TRANS_TABLES，决定了第 7 段的 NOT NULL 违反
    # 是被数据库【拒绝】还是被【悄悄改成空串并给个 warning】
    check("sql_mode 含 STRICT_TRANS_TABLES（严格模式，非法值会被拒绝而不是被改写）",
          "STRICT_TRANS_TABLES" in str(sql_mode), True)

    # ── ③ 建表 ────────────────────────────────────────────────────────
    print("\n【3】create_all() 建表")
    before = existing_tables(engine)
    print(f"        建表前库里已有 {len(before)} 张表：{before}")

    init_models(engine)

    after = existing_tables(engine)
    added = sorted(set(after) - set(before))
    print(f"        建表后共 {len(after)} 张表，本次新增：{added or '（无，说明表早已存在）'}")
    check("users 表存在", "users" in after, True)
    check("todos 表存在", "todos" in after, True)
    check("原有表一张都没被动到", set(before).issubset(set(after)), True)

    # ── ④ 逐列断言 ────────────────────────────────────────────────────
    # 注意：inspect() 是【反射】—— 它去问数据库"你这张表实际长什么样"，
    # 而不是读 Python 里的模型定义。所以这一段验证的是"模型真的落到了库里"，
    # 拿模型自己跟模型自己比是没有意义的。
    print("\n【4】表结构逐列核对（数据来自数据库反射，不是来自模型定义）")
    inspector = inspect(engine)

    users_cols: dict[str, Any] = {c["name"]: c for c in inspector.get_columns("users")}
    todos_cols: dict[str, Any] = {c["name"]: c for c in inspector.get_columns("todos")}

    check("users 的列集合", sorted(users_cols), ["created_at", "email", "id", "username"])
    check("todos 的列集合", sorted(todos_cols), ["content", "created_at", "done", "id"])

    # 主键
    check("users 主键是 id", inspector.get_pk_constraint("users")["constrained_columns"], ["id"])
    check("todos 主键是 id", inspector.get_pk_constraint("todos")["constrained_columns"], ["id"])

    # 类型与长度：String(50) 在 MySQL 上落成 VARCHAR(50)
    check("username 类型 = VARCHAR(50)", str(users_cols["username"]["type"]), "VARCHAR(50)")
    check("email 类型 = VARCHAR(120)", str(users_cols["email"]["type"]), "VARCHAR(120)")
    check("content 类型 = VARCHAR(200)", str(todos_cols["content"]["type"]), "VARCHAR(200)")

    # NOT NULL：nullable=False 的列，与 Mapped[str | None] 推断出的可空列
    check("username NOT NULL", users_cols["username"]["nullable"], False)
    check("content NOT NULL", todos_cols["content"]["nullable"], False)
    check("done NOT NULL", todos_cols["done"]["nullable"], False)
    check("email 允许 NULL（因为标注是 Mapped[str | None]）", users_cols["email"]["nullable"], True)

    # 唯一约束：unique=True 在 MySQL 上落成一个唯一索引
    users_indexes = inspector.get_indexes("users")
    print(f"        users 的索引：{users_indexes}")
    username_unique = any(
        ix.get("unique") and ix.get("column_names") == ["username"] for ix in users_indexes
    )
    check("username 上有唯一索引", username_unique, True)

    # ── default vs server_default：这一段是本脚本最值得看的地方 ────────
    # models.py 里 done 用的是 default=False（Python 端），
    # created_at 用的是 server_default=func.now()（数据库端）。
    # 反射回来就能看到差别：数据库层只有 created_at 带 DEFAULT 子句。
    print("\n【4b】default（Python 端）vs server_default（数据库端）的实证对比")
    print(f"        todos.done       在库里的 DEFAULT = {todos_cols['done']['default']!r}")
    print(f"        todos.created_at 在库里的 DEFAULT = {todos_cols['created_at']['default']!r}")
    check("done 在数据库层【没有】DEFAULT（它只是 Python 端默认值）",
          todos_cols["done"]["default"], None)
    check("created_at 在数据库层【有】DEFAULT（server_default 落进了 DDL）",
          todos_cols["created_at"]["default"] is not None, True)

    # ── ⑤ 打印真实 DDL ────────────────────────────────────────────────
    # CreateTable(...).compile(dialect=mysql.dialect()) 只"翻译不执行"：
    # 把表对象编译成 MySQL 方言下的 CREATE TABLE 文本，一个字都不发给数据库。
    # 学习期强烈建议多看这个输出 —— 它能治"ORM 到底替我做了什么"的糊涂账。
    print("\n【5】ORM 生成的真实建表语句（MySQL 方言，仅编译未执行）")
    # 为什么写 Base.metadata.tables["users"] 而不是 User.__table__？
    #   SQLAlchemy 的类型声明里（orm/decl_api.py）__table__ 是 ClassVar[FromClause]，
    #   而 CreateTable 要的是更具体的 Table；拿 __table__ 去传会被类型检查器拦下。
    #   MetaData.tables 的声明是 FacadeDict[str, Table]（sql/schema.py），取出来就是 Table。
    # 顺手也印证了 models.py 里那句话：Base.metadata 就是所有表"图纸"的集合。
    users_ddl = compile_ddl(Base.metadata.tables["users"])
    todos_ddl = compile_ddl(Base.metadata.tables["todos"])
    for table_name, ddl in (("users", users_ddl), ("todos", todos_ddl)):
        print(f"\n-------- {table_name} --------")
        for line in ddl.splitlines():
            print(f"        {line.rstrip()}")

    check("users DDL 里有 AUTO_INCREMENT", "AUTO_INCREMENT" in users_ddl, True)
    check("users DDL 里有 UNIQUE", "UNIQUE" in users_ddl, True)
    check("users DDL 里有 NOT NULL", "NOT NULL" in users_ddl, True)
    check("todos DDL 指定了 InnoDB 引擎", "InnoDB" in todos_ddl, True)
    check("todos DDL 指定了 utf8mb4 字符集", "utf8mb4" in todos_ddl, True)

    # ── ⑥ 幂等性 ──────────────────────────────────────────────────────
    print("\n【6】create_all() 的幂等性（checkfirst=True）")
    try:
        init_models(engine)
        raised = False
    except Exception as error:
        # 这里就是要看它会不会抛任何异常，所以宽泛地接住；接到就算失败
        raised = True
        print(f"        意外异常：{error!r}")
    check("重复建表不报错", raised, False)
    check("重复建表后表数量不变", len(existing_tables(engine)), len(after))
    print("        提醒：create_all 只管\"从无到有\"，改了模型字段它【不会】ALTER 旧表；")
    print("              结构变更要靠 Day 18 的 Alembic。")

    # ── ⑦ 事务冒烟：插入 → 验证 → rollback ─────────────────────────────
    # 为什么插入完要 rollback？
    #   Day 15 的验收目标是"表结构建对了"，不是"往里塞数据"。
    #   但只有真的写一次，才能证明自增主键、server_default、约束都在工作。
    #   所以做法是：在事务里写 → 验证 → 回滚。库里干干净净，证据一样拿到。
    print("\n【7】事务冒烟（全程 rollback，库里不留任何数据）")
    with session_scope(engine) as session:
        users_before: int = int(session.scalar(select(func.count()).select_from(User)) or 0)
        todos_before: int = int(session.scalar(select(func.count()).select_from(Todo)) or 0)
    print(f"        冒烟前行数：users={users_before}  todos={todos_before}")

    session_factory = get_session_factory(engine)

    # 7a 正常插入：验证自增主键、Python 端默认值、数据库端默认值
    print("\n   7a 正常插入一条 User + 一条 Todo（flush 后读取，然后回滚）")
    session = session_factory()
    try:
        probe_name = f"day15_probe_{stamp}"
        user = User(username=probe_name)          # email 不传 → NULL
        todo = Todo(content="Day 15 建表冒烟任务")  # done 不传 → Python 端默认值 False
        session.add_all([user, todo])

        # flush：把 INSERT 发给数据库，但【不提交】。
        # 发完就能拿到数据库生成的自增 id —— 这正是"自增值由数据库生成"的证据。
        session.flush()
        print(f"        flush 后：{user!r}")
        print(f"                 {todo!r}")
        check("flush 后拿到数据库生成的自增 id（> 0）", user.id > 0, True)
        check("Todo 也拿到了自增 id", todo.id > 0, True)
        check("done 不传时用了 Python 端默认值 False", todo.done, False)
        # created_at 是 server_default，SQLAlchemy 在 flush 后回查数据库取值
        check("created_at 由数据库填成了 datetime", isinstance(user.created_at, datetime), True)
        check("email 不传就是 None", user.email, None)
    finally:
        session.rollback()
        session.close()

    # 7b 唯一约束：同一个事务里插两个同名 username
    print("\n   7b 唯一约束：连续插两条相同 username，第二条应被数据库拒绝")
    session = session_factory()
    raised = False
    detail = ""
    try:
        dup_name = f"day15_dup_{stamp}"
        session.add(User(username=dup_name))
        session.flush()
        session.add(User(username=dup_name))
        try:
            session.flush()
        except IntegrityError as error:
            raised = True
            # orig 是 PyMySQL 抛出的原始错误，里面带 MySQL 的错误码与错误号
            detail = str(error.orig)
    finally:
        session.rollback()
        session.close()
    print(f"        数据库原始报错：{detail}")
    check("重复 username 触发 IntegrityError", raised, True)
    check("报错信息指向唯一约束（Duplicate entry）", "Duplicate entry" in detail, True)

    # 7c NOT NULL 约束：给 content 塞 None
    print("\n   7c NOT NULL 约束：content 传 None，应被数据库拒绝")
    session = session_factory()
    raised = False
    detail = ""
    try:
        # 用字典解包传参，是为了绕过类型检查器 —— 这里【故意】要传一个
        # 类型不对的值，去验证数据库层的 NOT NULL 真的拦得住。
        # 正常业务代码不要这么写；Mapped[str] 的字段本来就不该收到 None。
        broken = Todo(**{"content": None})
        session.add(broken)
        try:
            session.flush()
        except IntegrityError as error:
            raised = True
            detail = str(error.orig)
    finally:
        session.rollback()
        session.close()
    print(f"        数据库原始报错：{detail}")
    check("content 为 NULL 触发 IntegrityError", raised, True)
    check("报错信息指向 content 列不能为 null", "content" in detail.lower(), True)

    # 7d 零残留验证：三次 rollback 之后，行数应该和冒烟前一模一样
    print("\n   7d 零残留验证")
    with session_scope(engine) as session:
        users_after: int = int(session.scalar(select(func.count()).select_from(User)) or 0)
        todos_after: int = int(session.scalar(select(func.count()).select_from(Todo)) or 0)
    print(f"        冒烟后行数：users={users_after}  todos={todos_after}")
    check("users 行数没变（rollback 生效）", users_after, users_before)
    check("todos 行数没变（rollback 生效）", todos_after, todos_before)

    # 连接池收工：把池里的连接真正关掉，否则脚本退出时会留一堆 CLOSE_WAIT
    engine.dispose()

    # ── 汇总 ──────────────────────────────────────────────────────────
    total, passed = len(PASSED), sum(PASSED)
    print("\n" + "=" * 74)
    print(f"断言结果：{passed}/{total} 通过" + ("" if passed == total else "  ← 有未通过项，见上面 [FAIL]"))
    print("=" * 74)
    print("Day 16 预告：在这个包上写一组 DAO 函数，覆盖增删改查与分页，")
    print("            并正式处理 Session 的创建 / 提交 / 回滚 / 关闭与事务边界。")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
