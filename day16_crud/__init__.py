# 包的入口文件（__init__.py）。
#
# 作用和 day15_orm/__init__.py 一样：
#   1. 标识"day16_crud 是一个包"，能被 import；
#   2. 把 dao.py 里的 CRUD 函数"提上来"，外部就能写
#      `from day16_crud import create_user, list_todos`，
#      不必知道它们其实都在 dao.py 这一个文件里。
#
# 注意：本包【不】重新导出 User / Todo / session_scope —— 那些是 Day 15 的东西，
# 用的人直接从 day15_orm 拿。day16_crud 只对外提供"数据访问函数"这一层，
# 职责边界清楚：day15_orm 管模型与连接，day16_crud 管增删改查。

from .dao import (
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

__all__ = [
    "create_user",
    "get_user",
    "get_user_by_username",
    "list_users",
    "update_user_email",
    "delete_user",
    "create_todo",
    "get_todo",
    "list_todos",
    "set_todo_done",
    "delete_todo",
]
