# 简单的任务清单程序（async/await 模拟异步任务的对照版本）
#
# 与其他 todolist 版本的区别：这一版不追求功能完整，而是专门用来"感受异步 IO"。
# 真实的保存/加载属于磁盘 IO 或网络 IO——耗时但不占 CPU；async/await 让我们在
# 等待一条任务保存时不必干等，可以并发去推进别的任务，这正是 Day 5 要体会的点。
#
# 本文件演示三件事（对应 Day 5 的 async/await 入门）：
#   1. async def 定义协程函数、await 等待一个"耗时操作"（用 asyncio.sleep 模拟）；
#   2. 顺序 await 与 asyncio.gather 并发的耗时对比，直观看到异步的价值；
#   3. asyncio.run(...) 作为异步世界的入口，驱动整个事件循环。
#
# 说明：这里的"保存/加载"是假的，只用 sleep 模拟耗时，不会真的读写文件，
# 目的是把注意力放在 async/await 的调度上，而不是文件细节（文件读写已在 todolist.py 练过）。
#
# 只用标准库，不需要安装任何依赖，直接运行：
#     .\.venv\Scripts\python.exe "todolist async.py"

import asyncio
import time


# 模拟"异步保存一条任务"：真实场景是写磁盘或发网络请求，这里用 sleep 假装它很慢。
# async def 定义的函数叫"协程函数"，直接调用它不会执行，而是返回一个协程对象，
# 必须交给事件循环（被 await，或放进 asyncio.run / gather）才会真正运行。
async def save_task(name: str, seconds: float) -> str:
    print(f"  [{name}] 开始保存，预计耗时 {seconds} 秒 ...")
    # await 的关键作用：在这里"让出"控制权，事件循环趁这段等待时间去跑别的任务
    await asyncio.sleep(seconds)
    print(f"  [{name}] 保存完成。")
    return f"{name} 已保存"


# 演示一：顺序执行——一条保存完再保存下一条，总耗时 = 各条相加
async def run_sequential() -> None:
    print("\n=== 演示一：顺序 await（一条接一条）===")
    start = time.perf_counter()
    await save_task("写周报", 1.0)
    await save_task("买牛奶", 1.0)
    await save_task("交电费", 1.0)
    cost = time.perf_counter() - start
    print(f"顺序执行总耗时：{cost:.2f} 秒（约等于 1 + 1 + 1 = 3）")


# 演示二：并发执行——用 gather 同时发起三条保存，总耗时 ≈ 最慢的那一条
async def run_concurrent() -> None:
    print("\n=== 演示二：asyncio.gather 并发（同时进行）===")
    start = time.perf_counter()
    # gather 把多个协程一起交给事件循环：谁 await（让出）时就切去推进别人，
    # 三条"保存"因此在同一段时间里一起等待，而不是排队
    results = await asyncio.gather(
        save_task("写周报", 1.0),
        save_task("买牛奶", 1.0),
        save_task("交电费", 1.0),
    )
    cost = time.perf_counter() - start
    print(f"并发执行总耗时：{cost:.2f} 秒（约等于最慢的一条 = 1）")
    print(f"三条返回结果：{results}")


# 演示三：并发"加载"任务列表——贴近真实场景，且拿到每条协程的返回值
async def load_tasks_demo() -> None:
    print("\n=== 演示三：模拟异步加载任务列表 ===")

    # 协程函数也可以定义在函数内部，作用域仅限这里使用
    async def fetch_task(title: str) -> dict[str, object]:
        await asyncio.sleep(0.5)          # 模拟从"远程/磁盘"读取数据的延迟
        return {"content": title, "done": False}

    tasks = await asyncio.gather(
        fetch_task("学习 async/await"),
        fetch_task("预习 FastAPI"),
    )
    print(f"加载到 {len(tasks)} 条任务：")
    for index, task in enumerate(tasks, start=1):
        print(f"{index}. {task}")


# 异步世界的主流程：把三个演示依次 await 串起来
async def main() -> None:
    await run_sequential()
    await run_concurrent()
    await load_tasks_demo()
    print("\n小结：IO 密集操作（保存/加载/网络请求）用 async 并发能显著省时间；")
    print("      这也是第二阶段 FastAPI 里 async def 接口能扛并发的底层原理。")


# 程序入口：asyncio.run 会新建一个事件循环，跑完主协程再关闭它。
# 注意：asyncio.run 必须在"同步"代码里调用（比如这里的 __main__ 块），
# 不能在一个已经在运行的事件循环内部再调用它。
if __name__ == "__main__":
    asyncio.run(main())
