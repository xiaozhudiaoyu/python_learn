from logging.config import fileConfig

from sqlalchemy import create_engine
from sqlalchemy import pool

from alembic import context

# ── 接入本项目的模型与连接配置（Day 18）──────────────────────
# Alembic 的 autogenerate 靠“对比两份 schema”工作：
#   一份是 target_metadata（Python 模型里声明的目标结构），
#   一份是数据库里当前的真实结构（用连接反射出来），
#   两者的差异就是要生成的迁移。所以必须把 day15_orm 的 Base.metadata 交给它，
#   否则 target_metadata=None，autogenerate 什么都对比不出来。
#
# 连接串从 day15_orm.db_config.build_url() 拿 —— 它读的是被 .gitignore 排除的
# db_config_local.py。这样真实的账号口令只存在于本地私密文件，
# 【绝不】写进会被提交的 alembic.ini（那行只是占位符，下面会被覆盖）。
from day15_orm.db_config import build_url
from day15_orm.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 把项目所有 ORM 模型的“图纸”交给 Alembic 做 autogenerate 对比。
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


# ── 保护数据库里的"外来表"：include_object 过滤器（Day 18 重要安全点）──────────
# 这个库里除了本项目的 users/todos/tags/todo_tags，还残留着早期 sqlalchemy_learn/
# 实验建的两张表 user、account（注意 user 是单数，和本项目的 users 不是同一张表）。
# 它们不在 Base.metadata 里，而 autogenerate 的对比规则是：
#   "数据库里有、但模型里没有"的表 → 判定为多余 → 生成 op.drop_table() 把它删掉。
# 于是一次看似普通的迁移，会在 upgrade 时悄悄 DROP 掉这两张外来表连数据一起没了。
#
# include_object 返回 False，等于告诉 autogenerate"这个对象当作不存在"：
# 既不参与对比，也不会为它生成任何 create/drop 操作，外来表因此被保护起来。
# 这也是共享库 / 遗留库接入 Alembic 的通用手法——显式限定 autogenerate 的管辖范围，
# 只管自己模型里的表，别人的表一概不碰。
FOREIGN_TABLES = {"user", "account"}


def include_object(object, name, type_, reflected, compare_to) -> bool:
    """autogenerate 对比时的对象过滤器：把外来的 user/account 表排除在外。"""
    if type_ == "table" and name in FOREIGN_TABLES:
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = build_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = create_engine(build_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
