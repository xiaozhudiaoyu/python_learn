# Day 11 · Depends 演示路由：/api/depends —— 单独一个 router，方便和 Day 9/10 的接口对比。
#
# 为什么另开一个文件，而不直接改 todos.py：
#   现有 /api/todos 接口是 Day 9~10 的成果，保持原样才好看出差额；
#   等第三阶段接数据库，分页 / 当前用户这些依赖会自然"下沉"进 todos.py 的正式接口。
#
# 依赖注入的三种挂载范围（本文件用到 1、3，第 2 种见 main.py）：
#   1) 接口级：@router.get("/x", dependencies=[Depends(f)])  或   参数写 x: T = Depends(f)
#   2) 应用级：FastAPI(dependencies=[Depends(f)])            —— 全站生效
#   3) 路由级：APIRouter(dependencies=[Depends(f)])          —— 本 router 全部接口生效

from typing import Any

from fastapi import APIRouter, Depends, Request

from todo_api.deps import (
    AdminDep,
    CurrentUserDep,
    OptionalUserDep,
    PageQueryDep,
    SessionDep,
    recent_sessions,
    require_client_tag,
)

router = APIRouter(
    prefix="/api/depends",
    tags=["Day11 · Depends 依赖注入"],
    # 想让本文件所有接口都过某道检查，就在这里加 dependencies=[Depends(...)]
)

# 演示数据（够用即可，重点是"依赖怎么把参数递进来"）
_ITEMS: list[dict[str, Any]] = [
    {"id": i, "title": f"任务 {i}"} for i in range(1, 9)
]


@router.get("/page")
def paging(page: PageQueryDep) -> dict[str, Any]:
    """【依赖嵌套】接口签名里只有一个 page，但它背后跑了两个依赖函数。

    试这些请求，逐条体会"校验是框架做的"：
      /api/depends/page                        → 默认 limit=10、order=asc
      /api/depends/page?limit=2&offset=3       → 第 4~5 条
      /api/depends/page?limit=999              → 422（超出 le=100，依赖层就拦下了）
      /api/depends/page?order=down             → 422（Literal 只认 asc/desc）
    """
    rows = _ITEMS[page.pagination.as_slice()]
    if page.order == "desc":
        rows = list(reversed(rows))
    return {
        "items": rows,
        "limit": page.pagination.limit,
        "offset": page.pagination.offset,
        "order": page.order,
        "total": len(_ITEMS),
    }


@router.get("/session")
def session_note(session: SessionDep) -> dict[str, Any]:
    """【yield 依赖】看资源"创建 → 使用 → 释放"的完整闭环。

    连续调用两次就能验证收尾逻辑真的执行了：
      第一次：本次会话 closed=False，历史里上一个会话 closed=True；
      第二次：同上，id 递增一位 —— 说明每次请求都是一个新资源、用完即关。
    在接口函数里 raise HTTPException 再试一次，finally 依然会 close（不泄漏连接）。
    """
    return {
        "本次会话": {"id": session.id, "note": session.note, "closed": session.closed},
        # 倒序看最近几个会话：除本次外，其余 closed 应当都是 true（证明 finally 跑了）
        "最近会话": [
            {"id": s.id, "closed": s.closed} for s in reversed(recent_sessions())
        ],
    }


@router.get("/me")
def me(user: CurrentUserDep) -> dict[str, Any]:
    """【登录态】不带 X-Token → 401；带 tok-001 / tok-002 → 200。

    身份校验发生在进函数之前：函数体里没有任何 if 判断 token，
    能执行到这一行，就说明 user 一定是个合法用户。
    """
    return {"登录用户": user.model_dump()}


@router.get("/admin")
def admin_only(request: Request, user: CurrentUserDep, admin: AdminDep) -> dict[str, Any]:
    """【依赖复用 + 缓存】user 与 admin 来自同一条依赖链，验证"一个请求只解析一次"。

      无 X-Token            → 401（第一层 api_token 拦的）
      X-Token: tok-bad      → 401（第二层 get_current_user 拦的）
      X-Token: tok-002      → 403（李四不是管理员，第三层 require_admin 拦的）
      X-Token: tok-001      → 200，且 same_instance=true、token_lookups=1
    token_lookups 是我们在依赖里用 request.state 记的次数：
    它等于 1，就证明 get_current_user 没有被 user 和 admin 各跑一遍。
    （测试时把这个依赖 override 掉，它会变成 0 —— 见 run_day11_demo.py 第 6 段。）
    """
    return {
        "以管理员身份操作": f"hello, {admin.name}",
        "same_instance": user is admin,
        "get_current_user 执行次数": getattr(request.state, "token_lookups", 0),
    }


@router.get("/feed")
def feed(user: OptionalUserDep) -> dict[str, Any]:
    """【可选登录】游客也能看，带了有效 token 就个性化。

    传 / 不传 X-Token 各试一次，对比"你好，xxx"是否出现。
    这里用的是 get_optional_user —— 换成 get_current_user 就会变成硬 401。
    """
    return {
        "列表": _ITEMS[:3],
        "问候": f"你好，{user.name}" if user else "游客你好（未登录）",
    }


@router.get("/guarded", dependencies=[Depends(require_client_tag)])
def guarded() -> dict[str, Any]:
    """【只拦不注入】dependencies=[...]：接口签名里看不到这个依赖，也拿不到它的返回值。

      不带 X-Client  → 400
      X-Client: web  → 200
    适合"限流、埋点、统一鉴权"这类只需要动作、不需要结果的检查。
    """
    return {"message": "你通过了 X-Client 检查，但没有接收到它的任何值"}
