# 模块：持久化（storage）。
#
# 这里只负责"任务列表 <-> JSON 文件"的读写，不关心任务的业务规则（增删改查在 service 里）。
# 把 IO 单独抽成一个模块的意义：第三阶段换成数据库（SQLAlchemy）时，
# 只需要改这一个文件的实现，models 和 service 几乎不用动——这就是分层拆分的价值。

import json
import os

# 相对导入：从"同一个包内"的 models 模块拿 Task。
# 前面那个点(.) 就代表"当前包(todo_app)"，这是包内部模块互相引用的标准写法；
# 换成绝对导入也能写成 from todo_app.models import Task，但包内部一般用相对导入更稳。
from .models import Task


# 从 JSON 文件读取任务列表（文件不存在或损坏时返回空清单）
def load_tasks(data_file: str) -> list[Task]:
    if not os.path.exists(data_file):
        return []
    try:
        with open(data_file, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        print(f"读取任务文件失败（{error}），本次以空清单开始.")
        return []
    if not isinstance(data, list):
        print("任务文件格式不正确，本次以空清单开始.")
        return []
    tasks: list[Task] = []
    for item in data:
        task = Task.from_dict(item)
        if task is None:
            print(f"跳过无法识别的任务数据: {item!r}")
        else:
            tasks.append(task)
    return tasks


# 把任务列表写入 JSON 文件
def save_tasks(tasks: list[Task], data_file: str) -> None:
    try:
        with open(data_file, "w", encoding="utf-8") as file:
            json.dump([task.to_dict() for task in tasks], file, ensure_ascii=False, indent=2)
    except OSError as error:
        print(f"保存任务文件失败（{error}）.")
