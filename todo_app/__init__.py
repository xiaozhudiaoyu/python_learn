# 包的入口文件（__init__.py）。
#
# 有了这个文件，Python 才把 todo_app 这个目录当成一个"包"来导入（import todo_app）。
# 它的两个作用：
#   1. 标识"这是一个包"（能被 import）；
#   2. 把子模块里最常用的名字"提上来"，外部就能写简短的
#      `from todo_app import TodoList`，而不必知道内部其实分成了
#      models / storage / service 三个文件——把内部结构对外隐藏起来。
#
# __all__ 是一份"对外公开清单"：它决定 `from todo_app import *` 会导出哪些名字，
# 也明确告诉读者哪些才是这个包的公开 API。storage 属于内部实现细节，故意不放进 __all__。

from .models import Task
from .service import TodoList

__all__ = ["Task", "TodoList"]
