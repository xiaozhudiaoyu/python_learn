# 【模板】容器专用数据库连接配置（todo_api 容器化用）。
#
# 与 db_config_local_example.py 的唯一区别：DB_HOST 的取值按 Docker 拓扑二选一（2026-09-28 实测）：
#   拓扑 A：Docker Desktop（Windows 侧）→ 写 "host.docker.internal"（compose 的
#           extra_hosts: host-gateway 在 Windows 引擎下指向 Windows 宿主）；
#   拓扑 B：Docker Engine 装在 WSL2 内（本项目当前实况）→ host-gateway 指向的是
#           **WSL 虚拟机自己**（其上无 3306，容器会报 Connection refused），
#           必须改写 Windows 虚拟网卡 IP（与 WSL 侧 db_config_local.py 的 DB_HOST 同值，
#           如 172.19.80.1；WSL 重启后该 IP 可能变化，以 ipconfig 实测为准）。
#
# 用法：复制本文件为同目录的 db_config_local_container.py，填入真实账号口令：
#
#     PowerShell（在项目根目录 e:/python_learn 下执行）：
#         Copy-Item day15_orm\db_config_local_container.example.py day15_orm\db_config_local_container.py
#
# db_config_local_container.py 已写进 .gitignore 且被 .dockerignore 排除，
# 运行时由 docker-compose.yml 以只读单文件挂载注入容器，口令不进镜像、不入库。
#
# 授权提醒：容器经 Docker NAT 访问宿主机 MySQL，MySQL 看到的来源 IP 不是 localhost。
# 若连接报 ERROR 1130 (Host ... is not allowed to connect)，需要为该账号补一条
# 放行 Docker 网段的授权（语句由人工审核后在 MySQL 客户端执行，勿交给工具静默执行）。

# 宿主机地址：拓扑 A 写 "host.docker.internal"；拓扑 B（Docker 引擎在 WSL2 内）写 Windows 虚拟网卡 IP
DB_HOST: str = "host.docker.internal"

# MySQL 端口，默认 3306
DB_PORT: int = 3306

# 库名。这个库必须【已经存在】且表结构已就绪（todo_api 启动不做 create_all，
# 建表/改表一律走 Alembic 迁移，见 day18_alembic）。
DB_NAME: str = "your_database_name"

# 连接账号，需要对上面这个库有 SELECT/INSERT/UPDATE/DELETE 权限
DB_USER: str = "your_mysql_user"

# 口令。只写在 db_config_local_container.py 里，不要提交、不要打印、不要贴进聊天记录
DB_PASSWORD: str = "your_mysql_password"

# 传给 PyMySQL 的连接参数，charset 必须 utf8mb4（与宿主机配置保持一致）
DB_QUERY: dict[str, str] = {"charset": "utf8mb4"}
