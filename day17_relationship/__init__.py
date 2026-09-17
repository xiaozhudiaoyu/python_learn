# 包的入口文件（__init__.py）。
#
# day17_relationship 在 Day 16 的 CRUD 基础上，增加：
#   · 一对多关联操作（Todo ↔ User）
#   · 多对多关联操作（Todo ↔ Tag）
#   · 分页查询（limit/offset + total count）
#
# 和 day16_crud 一样：只对外提供 DAO 函数，模型与连接从 day15_orm 拿。

from .dao import (
    add_tags_to_todo,
    count_todos,
    create_tag,
    create_todo_with_owner,
    get_or_create_tag,
    get_todo_with_owner,
    get_todo_with_tags,
    get_user_with_todos,
    list_todos_by_owner,
    list_todos_by_tag,
    list_todos_paginated,
    remove_tag_from_todo,
)

__all__ = [
    "create_todo_with_owner",
    "list_todos_by_owner",
    "get_user_with_todos",
    "get_todo_with_owner",
    "create_tag",
    "get_or_create_tag",
    "add_tags_to_todo",
    "remove_tag_from_todo",
    "list_todos_by_tag",
    "get_todo_with_tags",
    "count_todos",
    "list_todos_paginated",
]
