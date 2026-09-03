# 路由模块：/api/users —— 用户接口（起步版，内存数据）。

from fastapi import APIRouter

router = APIRouter(prefix="/api/users", tags=["users"])

_FAKE_USERS: list[dict[str, object]] = [
    {"id": 1, "name": "张三"},
    {"id": 2, "name": "李四"},
    {"id": 3, "name": "王五"},
]


@router.get("")
def list_users(limit: int = 10) -> list[dict[str, object]]:   # ② 标量参数且不在路径 → 查询参数
    """返回用户列表，演示【查询参数】与默认值。

    取值规则：limit 不在路径 {..} 里、且是标量(int)，FastAPI 便按"查询参数"取值，
    于是 /api/users?limit=2 → limit=2；默认值 =10 表示"可选"，不传就用 10。
    想加范围校验：from fastapi import Query，写 limit: int = Query(default=10, ge=1, le=100)。
    """
    return _FAKE_USERS[:limit]   # ③ 切片取前 limit 个，返回列表 → 自动序列化 JSON
