# 简单的任务清单程序（Task 改用第三方库 pydantic 实现的对照版本）
#
# 与 todolist.py / "todolist dataclass.py" 的区别：Task 继承 pydantic.BaseModel，
# 字段声明就是校验规则，而且在"创建对象"和"修改字段"两个时机都会真正校验
# （dataclass 只声明类型注解、不做运行时校验）。
#
# 因此本版本有两处行为差异：
#   1. 任务内容为空会被拦下，不会写入数据文件；
#   2. 旧数据里的非法字段（内容为空、状态不是布尔、时间格式错误）会跳过并提示原因。
#
# 数据文件独立为 tasks-pydantic.json。created_at 用真正的 datetime 类型，
# 写入 JSON 是 ISO 格式（如 2026-09-03T10:04:03）；读取时能兼容另两个版本写出的
# 字符串数组、空格分隔时间以及表示"未知"的空时间。反向也读得动（它们把时间当普通
# 字符串处理，会原样显示成带 T 的形式），不报错，只是显示格式不统一。
#
# 运行前需要安装依赖：pip install pydantic

import json
import os
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

# 任务数据保存的 JSON 文件（固定与脚本放在同一目录）
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks-pydantic.json")

# 创建时间的显示格式（写入文件时仍用 datetime 的 ISO 格式）
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


# 新建任务的创建时间，精确到秒，避免写入 JSON 时拖一长串微秒
def current_time():
    return datetime.now().replace(microsecond=0)

# pydantic 校验错误类型的中文说明，未收录的错误类型直接显示原始信息
ERROR_TEXTS = {
    "missing": "缺少必填字段",
    "string_type": "必须是文本",
    "string_too_short": "不能为空",
    "bool_parsing": "只能是 true 或 false",
    "datetime_parsing": "时间格式不正确",
    "datetime_from_date_parsing": "时间格式不正确",
    "model_type": "必须是任务对象或任务字符串",
    "model_attributes_type": "必须是任务对象或任务字符串",
}

# 把 pydantic 的校验错误转成一行可读提示
def error_text(error):
    messages = []
    for item in error.errors():
        field_name = item["loc"][0] if item["loc"] else "数据"
        reason = ERROR_TEXTS.get(item["type"], item["msg"])
        messages.append(f"{field_name} {reason}")
    return "、".join(messages)

# 定义任务类：字段声明即校验规则
class Task(BaseModel):
    # 默认只在创建对象时校验，打开这个开关后修改字段同样会校验
    model_config = ConfigDict(validate_assignment=True)

    content: str = Field(min_length=1)
    done: bool = False
    # 省略该字段时自动取当前时间；显式传 None 表示旧数据没有记录创建时间
    created_at: datetime | None = Field(default_factory=current_time)

    # 兼容旧版数据：整条记录就是一个任务字符串时，按"只有内容"处理
    @model_validator(mode="before")
    @classmethod
    def from_legacy_string(cls, data):
        if isinstance(data, str):
            return {"content": data, "created_at": None}
        return data

    # 完成状态的标记，用于清单显示
    def mark(self):
        return "√" if self.done else " "

    # 创建时间的显示文本，旧版数据显示为"未知"
    def created_text(self):
        return self.created_at.strftime(TIME_FORMAT) if self.created_at else "未知"

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
            record = item  # 保留文件里的原始数据，出错时按原样提示
            # 文件里的记录缺少 created_at，或者写的是空字符串（另两个版本表示"未知"的写法），
            # 都统一成 None；不这样处理会被当成时间格式错误，导致整条任务被丢弃
            if isinstance(item, dict) and not item.get("created_at"):
                item = {**item, "created_at": None}
            try:
                tasks.append(Task.model_validate(item))
            except ValidationError as error:
                print(f"跳过一条无法识别的任务数据（{error_text(error)}）: {record!r}")
        return tasks

    # 把任务列表写入 JSON 文件，model_dump(mode="json") 顶替手写的 to_dict()
    def save(self):
        try:
            with open(self.data_file, "w", encoding="utf-8") as file:
                json.dump([task.model_dump(mode="json") for task in self.tasks],
                          file, ensure_ascii=False, indent=2)
        except OSError as error:
            print(f"保存任务文件失败（{error}）.")

    # 判断输入的编号能否对应到一条任务
    def is_valid_number(self, number):
        return number.isdigit() and 1 <= int(number) <= len(self.tasks)

    # 添加任务，内容不合规会被校验拦下
    def add(self, content):
        try:
            task = Task(content=content)
        except ValidationError as error:
            print(f"添加失败（{error_text(error)}）.")
            return
        self.tasks.append(task)
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

    # 修改任务内容，校验失败时原内容保持不变
    def update(self, index, content):
        if index < 1 or index > len(self.tasks):
            print("无效的任务编号.")
            return
        task = self.tasks[index - 1]
        old_content = task.content
        try:
            task.content = content
        except ValidationError as error:
            print(f"修改失败（{error_text(error)}），原内容 '{old_content}' 保持不变.")
            return
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
