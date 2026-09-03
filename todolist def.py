# 简单的任务清单程序

import json
import os

# 任务数据保存的 JSON 文件（固定与脚本放在同一目录）
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks.json")

# 定义函数来读取任务数据
def load_tasks():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        print(f"读取任务文件失败（{error}），本次以空清单开始.")
        return []
    if not isinstance(data, list):
        print("任务文件格式不正确，本次以空清单开始.")
        return []
    return [str(task) for task in data]

# 定义函数来保存任务数据
def save_tasks():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as file:
            json.dump(tasks, file, ensure_ascii=False, indent=2)
    except OSError as error:
        print(f"保存任务文件失败（{error}）.")

# 从 JSON 文件读取任务列表（文件不存在时为空清单）
tasks = load_tasks()

# 定义函数来添加任务
def add_task(task):
    tasks.append(task)
    save_tasks()
    print(f"任务 '{task}' 已添加.")

# 定义函数来显示任务列表
def show_tasks():
    if not tasks:
        print("任务清单是空的.")
    else:
        print("任务清单:")
        for index, task in enumerate(tasks, start=1):
            print(f"{index}. {task}")

# 定义函数来删除任务
def remove_task(index):
    if index < 1 or index > len(tasks):
        print("无效的任务编号.")
    else:
        removed = tasks.pop(index - 1)
        save_tasks()
        print(f"任务 '{removed}' 已删除.")

# 定义函数来查询任务
def find_task(keyword):
    result = [task for task in tasks if keyword in task]
    if not result:
        print(f"没有找到包含 '{keyword}' 的任务.")
    else:
        print(f"查询结果 (共 {len(result)} 条):")
        for task in result:
            print(f"- {task}")

# 定义函数来修改任务
def update_task(index, new_task):
    if index < 1 or index > len(tasks):
        print("无效的任务编号.")
    else:
        old_task = tasks[index - 1]
        tasks[index - 1] = new_task
        save_tasks()
        print(f"任务 '{old_task}' 已修改为 '{new_task}'.")

# 程序启动时提示已加载的任务数量和数据文件位置
print(f"已加载 {len(tasks)} 条任务，数据保存在 {DATA_FILE}")

# 主程序循环
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
        add_task(new_task)
    elif choice == "2":
        show_tasks()
    elif choice == "3":
        show_tasks()
        number = input("输入要删除的任务编号: ")
        if number.isdigit():
            remove_task(int(number))
        else:
            print("请输入数字编号.")
    elif choice == "4":
        keyword = input("输入要查询的关键词: ")
        find_task(keyword)
    elif choice == "5":
        show_tasks()
        number = input("输入要修改的任务编号: ")
        if not number.isdigit():
            print("请输入数字编号.")
        elif int(number) < 1 or int(number) > len(tasks):
            print("无效的任务编号.")
        else:
            new_content = input("输入新的任务内容: ")
            update_task(int(number), new_content)
    elif choice == "6":
        print("退出程序.")
        break
    else:
        print("无效的选项，请重新输入.")