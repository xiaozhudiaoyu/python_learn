# 模块：数据模型（models）。
#
# 这里只回答"一条任务长什么样"，不涉及文件读写，也不涉及菜单交互。
# 把数据结构单独放一个模块的好处：业务逻辑(service)和持久化(storage)都能复用同一个 Task，
# 将来要增删任务的字段，只需要改这一个文件，其他模块不用动。

from datetime import datetime
from typing import Any

# 创建时间的保存格式（放在模型模块，作为整个包共用的常量）
TIME_FORMAT: str = "%Y-%m-%d %H:%M:%S"


# 定义任务类，表示清单中的一条任务
class Task:
    # 实例属性的类型声明，只写注解不赋值，不影响运行时行为
    content: str
    done: bool
    created_at: str

    # created_at 传 None 表示新建任务，自动记录当前时间；
    # 传空字符串表示旧版数据没有记录创建时间，保持"未知"
    def __init__(self, content: str, done: bool = False, created_at: str | None = None) -> None:
        self.content = content
        self.done = done
        if created_at is None:
            self.created_at = datetime.now().strftime(TIME_FORMAT)
        else:
            self.created_at = created_at

    def __repr__(self) -> str:
        return f"Task(content={self.content!r}, done={self.done!r}, created_at={self.created_at!r})"

    # 完成状态的标记，用于清单显示
    def mark(self) -> str:
        return "√" if self.done else " "

    # 创建时间的显示文本，旧版数据显示为"未知"
    def created_text(self) -> str:
        return self.created_at or "未知"

    # 转换成可以写入 JSON 的字典
    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "done": self.done,
            "created_at": self.created_at,
        }

    # 从 JSON 数据还原任务，兼容旧版的纯字符串格式；数据无法识别时返回 None
    @classmethod
    def from_dict(cls, data: object) -> "Task | None":
        if isinstance(data, str):
            return cls(content=data, created_at="")
        if isinstance(data, dict):
            return cls(content=str(data.get("content", "")),
                       done=bool(data.get("done", False)),
                       created_at=data.get("created_at", ""))
        return None
