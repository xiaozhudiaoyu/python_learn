# syntax=docker/dockerfile:1
# ------------------------------------------------------------
# todo_api 服务镜像（2026-09-28 容器化方案产物）
#
# 构建上下文必须是仓库根目录：todo_api 跨包 import day15_orm，两个包都要 COPY 进来。
# 构建：docker build -t todo-api:0.1 .
# 运行：推荐走 docker-compose.yml（需要挂载 db_config_local_container.py，见 compose 文件）
#
# 三个关键设计点（对应 _docker_plan.md D1 考点）：
#   1. 先 COPY pyproject.toml + uv.lock 装依赖，再 COPY 代码 —— 层缓存，改代码不重装依赖；
#   2. uv 缓存走 BuildKit cache mount（--mount=type=cache）—— 加速重复构建，但缓存不落进镜像层，瘦身；
#   3. uvicorn 必须绑 0.0.0.0 —— 容器内绑 127.0.0.1 时宿主机/外部不可达。
#
# 口令安全（规则 1.4）：day15_orm/db_config_local.py 已被 .dockerignore 排除，
# 容器内的数据库配置由 compose 以只读单文件挂载注入，镜像里不含任何真实口令。
# ------------------------------------------------------------

FROM python:3.14-slim

# 从官方镜像取 uv 二进制（astral-sh 官方文档推荐的镜像内安装方式）
# COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
COPY --from=ghcr.m.daocloud.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ---- 第一层：依赖（只随 pyproject.toml / uv.lock 变化而失效）----
COPY pyproject.toml uv.lock ./
# --no-install-project：本项目是纯脚本仓库（package = false），只装第三方依赖；
# --no-dev：pyright 等开发工具不进运行镜像。
# 注：pyproject.toml 里配置的清华镜像源在容器内同样生效（国内网络友好）。
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-install-project

# ---- 第二层：代码（改代码只重建这一层）----
# 跨包依赖链（已用 grep 穷举 todo_api 的全部 day* 导入）：
#   todo_api → day15_orm（db.py / service.py）、day16_crud（service.py 的 dao）
#   day16_crud → day15_orm
# day18_alembic + alembic.ini：带进镜像是为了将来可在容器内手工执行 alembic upgrade head，本次不自动运行。
COPY day15_orm/ ./day15_orm/
COPY day16_crud/ ./day16_crud/
COPY todo_api/ ./todo_api/
COPY alembic.ini ./
COPY day18_alembic/ ./day18_alembic/

# uv sync 建出的虚拟环境在 /app/.venv，加进 PATH 让 uvicorn/python 直接可用
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# 应用启动不会 create_all（见 todo_api/main.py 文档注释），表结构以容器 MySQL 现状为准
# （2026-09-28 起数据库同在 docker-compose 编排内，数据来自宿主机 dump 导入），
# 建表/改表一律走 Alembic 迁移，镜像启动命令里不做任何 DDL。
CMD ["uvicorn", "todo_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
