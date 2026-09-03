# 顶层入口脚本：演示"从包的外部如何使用这个包"。
#
# 运行（在项目根目录 e:/python_learn 下）：
#     .\.venv\Scripts\python.exe run_todo_app.py
#
# 为什么在这里就能 import todo_app？因为运行一个脚本时，Python 会把"脚本所在目录"
# （也就是项目根目录）自动放进模块搜索路径 sys.path，于是同目录下的 todo_app 包就能被找到。
# 这也是为什么"入口脚本"通常放在项目根目录、和包目录平级。

# 绝对导入：从 todo_app 包直接拿 TodoList 和 Task。
# 能写得这么简短，全靠 todo_app/__init__.py 把这两个名字"提了上来"，
# 否则就得写成 from todo_app.service import TodoList、from todo_app.models import Task。
from todo_app import TodoList, Task

# 需要时也能直接导入包内部的某个子模块（storage 没有在 __all__ 里，但仍可显式导入）：
from todo_app import storage


def main() -> None:
    # 演示 1：看看这些名字分别来自哪个模块，体会"一个包把代码分散在不同文件里"
    print("=== 这些对象各自来自哪个模块 ===")
    print(f"TodoList 来自模块：{TodoList.__module__}")   # todo_app.service
    print(f"Task     来自模块：{Task.__module__}")        # todo_app.models
    print(f"storage  是模块  ：{storage.__name__}")        # todo_app.storage

    # 演示 2：正常使用业务逻辑。增删改查由 service.TodoList 完成，
    # 而它内部又调用 models.Task（数据）和 storage（读写文件）——三个模块协同工作。
    print("\n=== 使用包里的 TodoList 跑一遍增删查 ===")
    todo = TodoList()
    print(f"已加载 {len(todo.tasks)} 条任务，数据保存在 {todo.data_file}")
    todo.add("学习模块和包")
    todo.add("理解 __init__.py 的作用")
    todo.add("预习 HTTP 基础")
    todo.show()
    todo.find("学习")
    todo.remove(2)
    todo.show()

    print("\n小结：models / storage / service 各司其职，__init__.py 决定对外暴露什么；")
    print("      这就是 Python 组织'模块 -> 包 -> 项目'的方式，")
    print("      也是第二阶段搭 FastAPI 项目骨架（router / schema / 分层）的基础。")


if __name__ == "__main__":
    main()
