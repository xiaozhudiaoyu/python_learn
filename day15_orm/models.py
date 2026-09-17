# 模块：ORM 模型（Day 15 · SQLAlchemy 2 基础）。
#
# 这里回答两个问题："数据库里的表长什么样"，以及"Python 里的对象长什么样"。
# ORM 把这两者绑在一起：一个类 = 一张表，一个实例 = 一行记录，一个类属性 = 一个字段。
# 这套"用 Python 类声明表结构"的写法叫声明式映射（Declarative Mapping）。
#
# 与 todo_api/schemas.py 里的 Pydantic 模型有什么区别？（Day 19 会专门练这个分离）
#   Pydantic BaseModel —— 管"HTTP 接口收什么、发什么"，活在接口边界，做校验与序列化；
#   SQLAlchemy Base    —— 管"数据库里存什么"，活在持久层，做表映射与 SQL 生成。
#   两者字段名看起来很像，但职责完全不同，不能拿一个去顶另一个。
#
# Day 15 的范围：字段、主键、约束、建表。
# 外键与 relationship 是 Day 17 的内容，这里【故意不写】，免得一次塞太多概念。

from datetime import datetime

from sqlalchemy import Column, ForeignKey, String, Table, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """所有 ORM 模型的共同基类。

    SQLAlchemy 2.0 的写法是自己定义一个继承 DeclarativeBase 的类，
    而不是 1.x 时代的 `Base = declarative_base()` 函数调用。
    区别不只是好不好看：Base 变成一个真实的类之后，
    Pyright 才能推断出子类里 Mapped[int] 对应的实例属性就是 int。

    它身上还挂着 Base.metadata —— 所有表"图纸"的集合。
    Day 15 的建表动作 create_all()，干的就是把这份图纸翻译成 CREATE TABLE 语句。
    """


# 两张表共用的 MySQL 建表选项（SQLAlchemy 会把它拼进 CREATE TABLE 的尾部）：
#   mysql_engine  = InnoDB  支持事务与外键。MySQL 5.5 起它就是默认引擎，
#                           但显式写出来更保险：万一服务端默认被改成 MyISAM，
#                           表照样建成，只是悄悄丢掉事务能力，这种坑很难查。
#   mysql_charset = utf8mb4 完整的 UTF-8，能存中文与 emoji（老的 utf8 只有 3 字节）。
# 以 mysql_ 开头的键是"方言专属选项"，只对 MySQL 生效，换成别的数据库会被忽略。
MYSQL_TABLE_ARGS: dict[str, str] = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
}


# ── 多对多中间表（Day 17）────────────────────────────────────────────────────
# 多对多关系不能在任何一个"一"方放外键（那只能表达一对多），必须引入第三张表，
# 里面放两个外键分别指向两端的主键，组合起来做联合主键。
# 这张表叫 association table（关联表）或 junction table（连接表），
# SQLAlchemy 里用 Table 对象定义，不用继承 Base —— 因为它没有自己的业务字段，
# 纯粹是"谁和谁有关系"的记录，不需要映射成 Python 类来操作。
#
# 如果将来中间表要加额外字段（比如"何时打的标签"、"谁打的"），
# 就得把它升级成一个正式的 ORM 类（继承 Base），Day 17 先用最简形式。
todo_tags = Table(
    "todo_tags",
    Base.metadata,
    Column("todo_id", ForeignKey("todos.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    **MYSQL_TABLE_ARGS,
)
# ondelete="CASCADE" 写在 ForeignKey 里：当 Todo 或 Tag 被删除时，
# 数据库会自动清掉关联表里对应的行，不会留下"孤儿外键"导致 FK 约束报错。
# 这是数据库层面的行为（DDL 里会生成 ON DELETE CASCADE），不依赖 ORM。


class User(Base):
    """用户表。Day 17 会让 Todo 通过外键关联到这张表。"""

    # __tablename__ 决定数据库里真实的表名。
    # 用复数 users 而不是 User：表名习惯用小写复数，类名习惯用单数大驼峰，
    # 两边不一致是正常的，靠 __tablename__ 显式绑定，别让框架去猜。
    __tablename__ = "users"
    __table_args__ = MYSQL_TABLE_ARGS

    # ── 主键 ──────────────────────────────────────────────────────────
    # Mapped[int] 是给 Pyright 看的类型；mapped_column(...) 是给 SQLAlchemy 看的列定义。
    # 这一对组合就是 2.0 风格的核心：类型标注与列配置分开写，两边都能读懂。
    #
    # primary_key=True 主键；autoincrement=True 自增。
    # 在 MySQL 上，SQLAlchemy 会把这两条翻译成 `INTEGER NOT NULL AUTO_INCREMENT`。
    # 注意：自增值是【数据库】生成的，不是 Python 生成的，
    #       所以 insert 之后要 commit（或 flush）才能读到 id —— Day 16 会踩到这个点。
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        comment="用户主键，数据库自增",
    )

    # ── 唯一约束 + 非空 ────────────────────────────────────────────────
    # String(50) 在 MySQL 上生成 VARCHAR(50)。这个 50 必须写：
    # MySQL 的 VARCHAR 不给长度会直接报错，不像某些数据库可以偷懒。
    #
    # unique=True 会在数据库层建唯一索引；nullable=False 生成 NOT NULL。
    # 为什么"用户名不能重复"要放在数据库层，而不是像 todo_api 那样在 service 里写 if？
    #   因为应用层的检查挡不住并发：两个请求同时查到"没重复"，然后都插入。
    #   数据库的唯一索引是最后一道闸，谁都绕不过去。应用层的检查只是为了
    #   能返回友好的 409 而不是难看的 500 —— 两层都要有，职责不同。
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        comment="登录名，全表唯一",
    )

    # ── 可空字段 ──────────────────────────────────────────────────────
    # Mapped[str | None] 里的 `| None` 就是在告诉 SQLAlchemy："这列允许 NULL"。
    # 2.0 风格下 nullable 会从类型标注自动推断，所以这里不必再写 nullable=True
    # （写了也不冲突，但重复。上面 username 显式写出来是为了强调对比）。
    email: Mapped[str | None] = mapped_column(
        String(120),
        comment="邮箱，选填",
    )

    # ── 时间戳：server_default vs default 的区别 ───────────────────────
    # server_default=func.now() → 写进 DDL，生成 `DEFAULT now()`，
    #                             由【数据库】在 INSERT 时填值；
    # default=...               → 只存在于 Python 端，DDL 里看不到，
    #                             由【SQLAlchemy】在 INSERT 时填值。
    # 这里选 server_default：就算有人绕过 ORM 直接用 SQL 客户端插一行，
    # created_at 照样有值，不会出现 NULL。
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
        comment="入库时间，由数据库生成",
    )

    # ── relationship：一对多的"一"端（Day 17）────────────────────────────
    # relationship 不是数据库里的列，DDL 中看不到它；它是 ORM 层的"导航属性"，
    # 让你在 Python 里用 user.todos 直接拿到该用户名下所有 Todo 对象，
    # 底层 SQLAlchemy 替你生成 SELECT * FROM todos WHERE owner_id = ?。
    #
    # back_populates="owner" 表示"对面那个属性叫 owner，我和它互为镜像"：
    #   user.todos 里包含的每个 todo，它的 todo.owner 一定指回这个 user。
    #   改了一端，另一端自动同步（在同一 session 内）。
    #
    # Mapped[list["Todo"]] 是 2.0 风格的类型标注：
    #   · list 表示"一对多"的多端（如果写 Mapped["Todo"] 就是"一对一"）；
    #   · 引号 "Todo" 是前向引用，因为 Todo 类定义在 User 后面。
    #
    # cascade="all, delete-orphan" 的作用：
    #   删 User 时，它名下的所有 Todo 会被 ORM 自动一起删掉。
    #   "delete-orphan" 还额外处理"从 user.todos 列表里移除一个 todo"的情况 ——
    #   被移除的 todo 的 owner_id 变成 NULL 后，如果它是 delete-orphan 模式，
    #   SQLAlchemy 会直接删掉它（因为它成了"孤儿"）。
    #   这里先【不加】cascade，留给 demo 演示"没有 cascade 时删 user 会怎样"，
    #   让你亲眼看到 FK 约束的拦截效果，之后再解释 cascade 是干什么的。
    todos: Mapped[list["Todo"]] = relationship(
        back_populates="owner",
        # cascade="all, delete-orphan",  # demo 里会解释为什么需要它
    )

    def __repr__(self) -> str:
        # __repr__ 不是装饰：调试时 print(session.query(...) 的结果列表) 全靠它，
        # 否则看到的是一串 <day15_orm.models.User object at 0x000001A2B3C4D5E0>。
        return f"User(id={self.id!r}, username={self.username!r})"


class Todo(Base):
    """待办任务表。字段刻意与 todo_api/schemas.py 的 TaskCreate / TaskOut 对齐，

    这样 Day 19 做"接口模型 vs ORM 模型分离"时，能直观看到两套模型
    字段一样、职责不一样的对照关系。
    """

    __tablename__ = "todos"
    __table_args__ = MYSQL_TABLE_ARGS

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        comment="任务主键，数据库自增",
    )

    # 长度 200 与 todo_api 里 TaskCreate 的 max_length=200 保持一致。
    #
    # 注意这里【没有】加 unique=True —— todo_api 的"内容重复返回 409"是业务规则，
    # 由 service 层判断，不落数据库约束。区别在于：
    #   username 重复是数据完整性问题，任何情况下都不允许 → 数据库约束；
    #   content  重复是当前这个 API 的业务选择，将来可能放开     → 应用层逻辑。
    # 把业务规则写死进数据库约束，以后想改就得动表结构，代价大得多。
    content: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="任务内容，1~200 字",
    )

    # default=False 是【Python 端】默认值：不传 done 时 SQLAlchemy 填 False。
    # 这里故意用 default 而不用 server_default，和上面 created_at 形成对照 ——
    # 运行 run_day15_demo.py 打印 DDL 时会看到：
    #   created_at 那列有 DEFAULT 子句，done 那列没有。
    # 这就是两种默认值最直观的区别。
    done: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        comment="是否已完成，默认未完成",
    )

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
        comment="入库时间，由数据库生成",
    )

    # ── 外键（ForeignKey）：一对多的"多"端（Day 17）────────────────────────
    # ForeignKey("users.id") 告诉数据库："这列的值必须是 users 表 id 列里已有的值，
    # 或者是 NULL"。这就是参照完整性（referential integrity）—— 不允许 todo 指向
    # 一个不存在的 user。如果你尝试 INSERT 一条 owner_id=999 但 users 里没有 id=999，
    # MySQL 会直接拒绝并报 FK 约束违反错误。
    #
    # Mapped[int | None] → nullable=True：一条待办可以不归属于任何用户（"公共待办"），
    # 这是业务选择。如果写成 Mapped[int]（不带 None），则 owner_id 非空，
    # 每条 todo 必须有一个 owner —— 哪种更合理取决于你的业务规则。
    #
    # ondelete="SET NULL"：当关联的 User 被 DELETE 时，数据库自动把这列置 NULL，
    # 而不是拒绝删除（RESTRICT）或连带删除（CASCADE）。
    # 这意味着：删用户不会丢待办，待办变成"无主"状态。
    # 注意：ondelete 是【数据库层】的行为（写在 DDL 里），不依赖 ORM 是否加载。
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        comment="所属用户 ID，外键关联 users.id",
    )

    # ── relationship：一对多的"多"端导航 ─────────────────────────────────
    # todo.owner 让你从一个 Todo 对象直接跳到它所属的 User 对象，
    # 底层生成 SELECT * FROM users WHERE id = <todo.owner_id>。
    #
    # 和 User.todos 互为 back_populates 镜像。
    # Mapped["User" | None]：owner_id 可空 → owner 也可能是 None（无主待办）。
    # Python 3.14 前向引用坑："User" | None 运行时 TypeError，须整体加引号写成 "User | None" 延迟解析。
    owner: Mapped["User | None"] = relationship(
        back_populates="todos",
    )

    # ── relationship：多对多 ─────────────────────────────────────────────
    # secondary=todo_tags 指定中间表。SQLAlchemy 通过它自动维护关联：
    #   todo.tags.append(tag) → INSERT INTO todo_tags (todo_id, tag_id) VALUES (...)
    #   todo.tags.remove(tag) → DELETE FROM todo_tags WHERE todo_id=... AND tag_id=...
    # 你操作的是 Python 列表，SQLAlchemy 替你翻译成对中间表的增删。
    #
    # lazy="select"（默认值）：访问 todo.tags 时才发 SQL 去查 —— 即"懒加载"。
    # 好处是不浪费查询（如果不需要 tags 就不查），坏处是在循环里逐个访问
    # 会产生 N+1 查询问题。demo 里会演示用 selectinload 一次性预加载来解决。
    tags: Mapped[list["Tag"]] = relationship(
        secondary=todo_tags,
        back_populates="todos",
    )

    def __repr__(self) -> str:
        return f"Todo(id={self.id!r}, content={self.content!r}, done={self.done!r}, owner_id={self.owner_id!r})"


class Tag(Base):
    """标签表（Day 17 多对多演示）。

    一条 Todo 可以有多个标签，一个标签可以贴在多条 Todo 上 —— 典型的多对多。
    多对多不能在 Todo 里放一个 tag_id（那只能存一个标签），
    也不能在 Tag 里放一个 todo_id（那只能存一条待办），
    必须用中间表 todo_tags 来记录"谁和谁有关系"。

    Tag 本身是一个普通的 ORM 类，有自己的主键和业务字段（name）。
    """

    __tablename__ = "tags"
    __table_args__ = MYSQL_TABLE_ARGS

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        comment="标签主键，数据库自增",
    )

    # 标签名唯一：不允许两个标签叫同一个名字。
    name: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False,
        comment="标签名称，全表唯一",
    )

    # ── 多对多的另一端 ───────────────────────────────────────────────
    # secondary=todo_tags 和 Todo.tags 用的是同一张中间表，
    # back_populates="tags" 指向 Todo 类上的 tags 属性。
    # 这样 tag.todos 和 todo.tags 互为镜像，改了一端另一端自动同步。
    todos: Mapped[list["Todo"]] = relationship(
        secondary=todo_tags,
        back_populates="tags",
    )

    def __repr__(self) -> str:
        return f"Tag(id={self.id!r}, name={self.name!r})"
