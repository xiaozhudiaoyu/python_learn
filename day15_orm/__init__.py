# 包的入口文件（__init__.py）。
#
# 作用和 todo_app/__init__.py 完全一样：
#   1. 标识"day15_orm 是一个包"，能被 import；
#   2. 把子模块里最常用的名字"提上来"，外部就能写
#      `from day15_orm import User, Todo, get_engine`，
#      而不必知道内部分成了 db_config / models / database 三个文件。
#
# __all__ 是对外公开清单。db_config_local 属于本地私密配置、
# db_config 属于内部组装细节，都【故意不】放进 __all__ ——
# 外部只需要拿到 engine 和模型，不需要知道连接串是怎么拼出来的。

from .database import (
    existing_tables,
    get_engine,
    get_session_factory,
    init_models,
    masked_url,
    session_scope,
)
from .models import Base, Tag, Todo, User, todo_tags

__all__ = [
    "Base",
    "User",
    "Todo",
    "Tag",
    "todo_tags",
    "get_engine",
    "get_session_factory",
    "session_scope",
    "init_models",
    "existing_tables",
    "masked_url",
]
