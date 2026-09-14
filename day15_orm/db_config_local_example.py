# 【模板】本地数据库连接配置。
#
# 用法：复制本文件为同目录的 db_config_local.py，再把下面 5 个占位值换成你自己的。
#
#     PowerShell（在项目根目录 e:/python_learn 下执行）：
#         Copy-Item day15_orm\db_config_local_example.py day15_orm\db_config_local.py
#
# db_config_local.py 已写进 .gitignore，不会被提交；本模板里只有占位值，可以提交。
# 约定：仓库里只留"结构与说明"，真实账号口令永远只存在于本地未跟踪的文件中 ——
#       .gitignore 不等于工具的读取排除规则，所以连示例都不要填真口令。

# MySQL 服务地址。本机装的 MySQL 就写 127.0.0.1 或 localhost
DB_HOST: str = "127.0.0.1"

# MySQL 端口，默认 3306
DB_PORT: int = 3306

# 库名（MySQL 里叫 database 或 schema，是一回事）。
# 这个库必须【已经存在】：Day 15 只做建表（create_all），不做建库（CREATE DATABASE）。
# 建库语句留给 Day 18 的 Alembic 阶段一并讨论，或在 MySQL 客户端里手工执行一次。
DB_NAME: str = "your_database_name"

# 连接账号，需要对上面这个库有 SELECT/INSERT/UPDATE/DELETE/CREATE/INDEX 权限
# （CREATE 与 INDEX 是 create_all 建表和唯一约束所必需的）
DB_USER: str = "your_mysql_user"

# 口令。只写在 db_config_local.py 里，不要提交、不要打印、不要贴进聊天记录
DB_PASSWORD: str = "your_mysql_password"

# 传给 PyMySQL 的连接参数，最终成为 URL 的 query 部分。
# charset 必须是 utf8mb4（MySQL 老的 utf8 只有 3 字节，存不了 emoji 和部分生僻字）
DB_QUERY: dict[str, str] = {"charset": "utf8mb4"}
