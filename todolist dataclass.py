# 简单的任务清单程序（Task 改用标准库 @dataclass 实现的对照版本）
#
# 与 todolist.py 的唯一区别是 Task 类的写法：__init__、__repr__、to_dict 都交给
# dataclass 生成，不再手写；业务行为和菜单交互与 todolist.py 完全一致。
# 数据文件独立为 tasks-dataclass.json，避免和 todolist.py 抢同一个 tasks.json，
# 但写入的 JSON 结构两边通用，可以互相读取。

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime

# 任务数据保存的 JSON 文件（固定与脚本放在同一目录）
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks-dataclass.json")

# 创建时间的保存格式
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# 定义任务类：字段用类型注解声明，__init__ 和 __repr__ 由装饰器自动生成
@dataclass
class Task:
    content: str
    done: bool = False
    # None 表示新建任务，自动记录当前时间；空字符串表示旧版数据没有创建时间，保持"未知"
    created_at: str | None = None

    # 生成的 __init__ 里插不进代码，需要加工字段时用这个钩子
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().strftime(TIME_FORMAT)

    # 完成状态的标记，用于清单显示
    def mark(self):
        return "√" if self.done else " "

    # 创建时间的显示文本，旧版数据显示为"未知"
    def created_text(self):
        return self.created_at or "未知"

    # 从 JSON 数据还原任务，兼容旧版的纯字符串格式；数据无法识别时返回 None
    @classmethod
    def from_dict(cls, data):
        if isinstance(data, str):
            return cls(content=data, created_at="")
        if isinstance(data, dict):
            return cls(content=str(data.get("content", "")),
                       done=bool(data.get("done", False)),
                       # 字段缺失或为 null 都按"未知"处理，避免被误记成当前时间
                       created_at=data.get("created_at") or "")
        return None

# 定义任务清单类，负责任务的增删改查和 JSON 文件读写
class TodoList:
    def __init__(self, data_file=DATA_FILE):
        self.data_file = data_file
        self.tasks = self.load()

    # 从 JSON 文件读取任务列表（文件不存在时为空清单）
    def load(self):
        if not os.path.exists(self.data_file):
            return []
        try:
            with open(self.data_file, "r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            print(f"读取任务文件失败（{error}），本次以空清单开始.")
            return []
        if not isinstance(data, list):
            print("任务文件格式不正确，本次以空清单开始.")
            return []
        tasks = []
        for item in data:
            task = Task.from_dict(item)
            if task is None:
                print(f"跳过无法识别的任务数据: {item!r}")
            else:
                tasks.append(task)
        return tasks

    # 把任务列表写入 JSON 文件，asdict() 顶替了手写的 to_dict()
    def save(self):
        try:
            with open(self.data_file, "w", encoding="utf-8") as file:
                json.dump([asdict(task) for task in self.tasks], file, ensure_ascii=False, indent=2)
        except OSError as error:
            print(f"保存任务文件失败（{error}）.")

    # 判断输入的编号能否对应到一条任务
    def is_valid_number(self, number):
        return number.isdigit() and 1 <= int(number) <= len(self.tasks)

    # 添加任务
    def add(self, content):
        self.tasks.append(Task(content))
        self.save()
        print(f"任务 '{content}' 已添加.")

    # 显示任务清单
    def show(self):
        if not self.tasks:
            print("任务清单是空的.")
        else:
            print("任务清单:")
            for index, task in enumerate(self.tasks, start=1):
                print(f"{index}. [{task.mark()}] {task.content}  (创建时间: {task.created_text()})")

    # 删除任务
    def remove(self, index):
        if index < 1 or index > len(self.tasks):
            print("无效的任务编号.")
        else:
            removed = self.tasks.pop(index - 1)
            self.save()
            print(f"任务 '{removed.content}' 已删除.")

    # 修改任务内容
    def update(self, index, content):
        if index < 1 or index > len(self.tasks):
            print("无效的任务编号.")
        else:
            task = self.tasks[index - 1]
            old_content = task.content
            task.content = content
            self.save()
            print(f"任务 '{old_content}' 已修改为 '{content}'.")

    # 按关键词查询任务
    def find(self, keyword):
        result = [task for task in self.tasks if keyword in task.content]
        if not result:
            print(f"没有找到包含 '{keyword}' 的任务.")
        else:
            print(f"查询结果 (共 {len(result)} 条):")
            for task in result:
                print(f"- [{task.mark()}] {task.content}")

# 主程序：负责菜单交互
def main():
    todo = TodoList()
    print(f"已加载 {len(todo.tasks)} 条任务，数据保存在 {todo.data_file}")

    while True:
        print("\n选择一个选项:")
        print("1. 添加任务")
        print("2. 显示任务清单")
        print("3. 删除任务")
        print("4. 查询任务")
        print("5. 修改任务")
        print("6. 退出")

        choice = input("输入选项编号: ")

        if choice == "1":
            new_task = input("输入新任务: ")
            todo.add(new_task)
        elif choice == "2":
            todo.show()
        elif choice == "3":
            todo.show()
            number = input("输入要删除的任务编号: ")
            if number.isdigit():
                todo.remove(int(number))
            else:
                print("请输入数字编号.")
        elif choice == "4":
            keyword = input("输入要查询的关键词: ")
            todo.find(keyword)
        elif choice == "5":
            todo.show()
            number = input("输入要修改的任务编号: ")
            # 先校验编号，避免编号无效时还多问一次新内容
            if not number.isdigit():
                print("请输入数字编号.")
            elif not todo.is_valid_number(number):
                print("无效的任务编号.")
            else:
                new_content = input("输入新的任务内容: ")
                todo.update(int(number), new_content)
        elif choice == "6":
            print("退出程序.")
            break
        else:
            print("无效的选项，请重新输入.")

if __name__ == "__main__":
    main()
