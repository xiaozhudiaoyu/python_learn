# 模块：数据库连接配置（Day 15 · SQLAlchemy 2 基础）。
#
# 这个文件只干一件事：把 db_config_local.py 里零散的字段，组装成 SQLAlchemy 的
# URL 对象，交给 database.py 去 create_engine。它自己不建连接、不碰数据库。
#
# 为什么不让各处代码自己拼连接串？
#   1. 口令只存在于 db_config_local.py 一个文件里，而那个文件已被 .gitignore 排除。
#      连接串一旦以完整字符串的形式散落各处，很容易被人顺手 print 出来或提交进仓库。
#   2. 将来换数据库（比如临时改用 SQLite 跑测试）只改这一处，
#      models.py 与 database.py 一行都不用动 —— 这正是 ORM 的核心价值：
#      模型定义与"数据到底存在哪种数据库里"解耦。

from sqlalchemy.engine import URL

try:
    from . import db_config_local
except ModuleNotFoundError as error:
    # 新克隆的仓库里只有 example 模板，没有真实配置文件，这里给出可直接照做的指引，
    # 而不是甩一个 "No module named 'day15_orm.db_config_local'" 让人猜。
    raise RuntimeError(
        "缺少本地数据库配置文件 day15_orm/db_config_local.py。\n"
        "请在项目根目录执行：\n"
        "    Copy-Item day15_orm\\db_config_local_example.py day15_orm\\db_config_local.py\n"
        "然后填入你自己的 MySQL 连接信息。该文件已在 .gitignore 中，不会被提交。"
    ) from error


def build_url() -> URL:
    """组装数据库连接 URL，返回 SQLAlchemy 的 URL 对象（不是字符串）。

    为什么用 URL.create() 而不是自己拼 "mysql+pymysql://user:pass@host:port/db"？
      口令里如果含有 ! : @ / ? 这些字符，在 URL 中必须做百分号转义，
      手工拼串一旦碰上就会报 "Could not parse SQLAlchemy URL"，
      而 URL.create() 接收的是拆开后的字段，转义由它自己负责。

    drivername 的 "mysql+pymysql" 读作"方言 + 驱动"：
      mysql    = SQLAlchemy 的 MySQL 方言，决定生成什么样的 SQL（如 AUTO_INCREMENT）
      pymysql  = 具体用哪个 DBAPI 驱动去连，也就是 .venv 里装的那个 PyMySQL 包
    """
    return URL.create(
        drivername="mysql+pymysql",
        username=db_config_local.DB_USER,
        password=db_config_local.DB_PASSWORD,
        host=db_config_local.DB_HOST,
        port=db_config_local.DB_PORT,
        database=db_config_local.DB_NAME,
        query=db_config_local.DB_QUERY,
    )


def masked_url() -> str:
    """返回可以放心打印到控制台的连接串：口令位置被替换成 ***。

    render_as_string(hide_password=True) 是 SQLAlchemy URL 自带的方法，
    比自己写字符串替换可靠 —— 它知道口令在 URL 里的确切位置。
    """
    return build_url().render_as_string(hide_password=True)
