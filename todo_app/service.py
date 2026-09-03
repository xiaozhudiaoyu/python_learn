# 模块：业务逻辑（service）。
#
# TodoList 负责增删改查，它把"数据模型(models.Task)"和"持久化(storage)"组合起来：
# 自己既不定义任务字段、也不直接 open/json 读写文件，而是通过 import 复用另外两个模块。
# 这正是模块化拆分后的职责划分——每个文件只做一件事，改一处不影响其他处。

import os

# 两种包内导入方式都在这里演示：
from .models import Task        # 方式一：从子模块拿具体的名字（这里是 Task 类）
from . import storage           # 方式二：整体导入子模块，调用时写 storage.load_tasks(...)

# 默认数据文件：包版本独立使用 tasks-app.json，不与其他 todolist 版本抢同一个 tasks.json。
# __file__ 是 todo_app/service.py，两次 dirname 退到项目根目录，再拼上数据文件名。
DATA_FILE: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tasks-app.json",
)


# 定义任务清单类，负责任务的增删改查；文件读写全部委托给 storage 模块
class TodoList:
    # 实例属性的类型声明
    data_file: str
    tasks: list[Task]

    def __init__(self, data_file: str = DATA_FILE) -> None:
        self.data_file = data_file
        # 通过 storage 模块加载数据，而不是自己写 open/json
        self.tasks = storage.load_tasks(self.data_file)

    # 把任务列表写入文件：同样委托给 storage 模块
    def save(self) -> None:
        storage.save_tasks(self.tasks, self.data_file)

    # 判断输入的编号能否对应到一条任务
    def is_valid_number(self, number: str) -> bool:
        return number.isdigit() and 1 <= int(number) <= len(self.tasks)

    # 添加任务
    def add(self, content: str) -> None:
        self.tasks.append(Task(content))
        self.save()
        print(f"任务 '{content}' 已添加.")

    # 显示任务清单
    def show(self) -> None:
        if not self.tasks:
            print("任务清单是空的.")
        else:
            print("任务清单:")
            for index, task in enumerate(self.tasks, start=1):
                print(f"{index}. [{task.mark()}] {task.content}  (创建时间: {task.created_text()})")

    # 删除任务
    def remove(self, index: int) -> None:
        if index < 1 or index > len(self.tasks):
            print("无效的任务编号.")
        else:
            removed = self.tasks.pop(index - 1)
            self.save()
            print(f"任务 '{removed.content}' 已删除.")

    # 修改任务内容
    def update(self, index: int, content: str) -> None:
        if index < 1 or index > len(self.tasks):
            print("无效的任务编号.")
        else:
            task = self.tasks[index - 1]
            old_content = task.content
            task.content = content
            self.save()
            print(f"任务 '{old_content}' 已修改为 '{content}'.")

    # 按关键词查询任务
    def find(self, keyword: str) -> None:
        result: list[Task] = [task for task in self.tasks if keyword in task.content]
        if not result:
            print(f"没有找到包含 '{keyword}' 的任务.")
        else:
            print(f"查询结果 (共 {len(result)} 条):")
            for task in result:
                print(f"- [{task.mark()}] {task.content}")
