# 路由模块：/api/users —— 用户接口（起步版，内存数据）。

from fastapi import APIRouter

router = APIRouter(prefix="/api/users", tags=["users"])

_FAKE_USERS: list[dict[str, object]] = [
    {"id": 1, "name": "张三"},
    {"id": 2, "name": "李四"},
    {"id": 3, "name": "王五"},
]


@router.get("")
def list_users(limit: int = 10) -> list[dict[str, object]]:
    """返回用户列表，演示【查询参数】与默认值。

    注意：limit 不在路径里，FastAPI 会自动把它当作查询参数（query string），
    于是 /api/users?limit=2 会取前 2 条；不写 limit 时默认返回全部（≤10）。
    """
    return _FAKE_USERS[:limit]
