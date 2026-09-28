# 【模板】容器专用数据库连接配置（todo_api 容器化用）。
#
# DB_HOST 的取值按 Docker 拓扑三选一（拓扑 A/B 为 2026-09-28 实测）：
#   拓扑 C（当前编排，数据库已容器化）：MySQL 与 todo-api 同在 docker-compose.yml
#           编排内 → DB_HOST 写服务名 "mysql"、DB_PORT 写 3306（容器内端口，
#           与宿主机映射的 3307 无关），走 compose 内部网络，不依赖任何宿主机 IP；
#   拓扑 A（历史：连宿主机 MySQL，Docker Desktop）→ 写 "host.docker.internal"；
#   拓扑 B（历史：连宿主机 MySQL，Docker Engine 在 WSL2 内）→ host-gateway 指向的是
#           **WSL 虚拟机自己**（其上无 3306，容器会报 Connection refused），
#           须改写 Windows 虚拟网卡 IP（如 172.19.80.1，WSL 重启后可能变化）。
#
# 用法：复制本文件为同目录的 db_config_local_container.py，填入真实账号口令：
#
#     PowerShell（在项目根目录 e:/python_learn 下执行）：
#         Copy-Item day15_orm\db_config_local_container.example.py day15_orm\db_config_local_container.py
#
# db_config_local_container.py 已写进 .gitignore 且被 .dockerignore 排除，
# 运行时由 docker-compose.yml 以只读单文件挂载注入容器，口令不进镜像、不入库。
#
# 授权提醒（仅拓扑 A/B 适用）：容器经 Docker NAT 访问宿主机 MySQL，MySQL 看到的来源 IP 不是 localhost。
# 若连接报 ERROR 1130 (Host ... is not allowed to connect)，需要为该账号补一条
# 放行 Docker 网段的授权（语句由人工审核后在 MySQL 客户端执行，勿交给工具静默执行）。
# 拓扑 C 不存在此问题：账号由 mysql 官方镜像在空卷首启时按 .env 的 MYSQL_USER/
# MYSQL_PASSWORD 自动创建并授予 MYSQL_DATABASE 库全部权限。

# 宿主机地址：拓扑 C 写 "mysql"（compose 服务名）；拓扑 A 写 "host.docker.internal"；
# 拓扑 B（Docker 引擎在 WSL2 内）写 Windows 虚拟网卡 IP
DB_HOST: str = "mysql"

# MySQL 端口：拓扑 C 写 3306（容器内端口，不是宿主机映射的 3307）；拓扑 A/B 写 3306
DB_PORT: int = 3306

# 库名。拓扑 C 下须与 .env 的 MYSQL_DATABASE 一致。这个库必须【已经存在】且表结构已就绪
# （todo_api 启动不做 create_all，建表/改表一律走 Alembic 迁移，见 day18_alembic；
# 拓扑 C 首次迁移时表结构随宿主机 dump 导入，含 alembic_version 表）。
DB_NAME: str = "your_database_name"

# 连接账号，需要对上面这个库有 SELECT/INSERT/UPDATE/DELETE 权限；
# 拓扑 C 下须与 .env 的 MYSQL_USER 一致
DB_USER: str = "your_mysql_user"

# 口令。只写在 db_config_local_container.py 里，不要提交、不要打印、不要贴进聊天记录；
# 拓扑 C 下须与 .env 的 MYSQL_PASSWORD 一致
DB_PASSWORD: str = "your_mysql_password"

# 传给 PyMySQL 的连接参数，charset 必须 utf8mb4（与 compose 里 mysql 服务的
# --character-set-server=utf8mb4 保持一致）
DB_QUERY: dict[str, str] = {"charset": "utf8mb4"}
