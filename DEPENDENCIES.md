# 依赖变更台账

> 记录 `.venv` 环境与依赖声明文件（`requirements.txt` / `requirements-dev.txt` / `requirements.lock.txt`）的变化。
> 每条均标注证据来源（`pyvenv.cfg`、`site-packages` 内 `dist-info` 的 NTFS 时间戳、包元数据 `Requires`/`Required-by`、git 提交），不做推断。
> 维护约定：每次增删依赖后补一节；刷新锁文件时同步更新「时间线总览」。

## 一、时间线总览

| 日期时间 | 事件 | 包数变化 | 证据 |
|---|---|---|---|
| 2026-09-02 17:17:55 | 建环境（`python -m virtualenv`，PyCharm 风格调用），17:18:01 装入 pip | 0 → 1 | `pyvenv.cfg` 的 `command` 行 |
| 2026-09-03 10:12:04 | 第一批：pydantic 及其依赖 | 1 → 6 | `dist-info` 时间戳 |
| 2026-09-03 11:35:09 | 第二批：pyright 静态检查器 | 6 → 8 | `dist-info` 时间戳 |
| 2026-09-03 15:41:24 | 第三批：fastapi + uvicorn[standard] 全家桶 | 8 → 21 | `dist-info` 时间戳 |
| 2026-09-04 15:50 | 生成 `requirements.lock.txt`（21 项）并提交 `075660c` | 21（持平） | `git log` |
| 2026-09-07 15:06:18–15:06:48 | **第四批：pipdeptree，未登记**（本次盘点发现） | 21 → **36** | `dist-info` 时间戳 + `pipdeptree` 元数据 |
| 2026-09-08 11:27 | 提交 `2906e03`（Depends 演示），代码新增 `deps.py`/`exceptions.py` 等 | 36（持平） | `git log --name-only`；新增代码只 import `fastapi`/`pydantic`/`starlette`，无越界依赖 |
| 2026-09-08 | 依赖盘点：本次发现 9/7 未登记新增；锁文件拆为运行时/开发两份；建立本台账 | 36（持平） | 本次操作，`pip freeze --all` 逐项比对 |
| 2026-09-11 10:08:10–10:08:51 | **第五批：SQLAlchemy + PyMySQL + greenlet，未登记**（本次盘点发现） | 36 → **38** | `dist-info` 时间戳；`SQLAlchemy.py` 第 1–2 行实际 import |
| 2026-09-11 | **pipdeptree 本体已迁往系统 Python，其 14 个传递依赖从 `.venv` 卸载**；两份锁文件重采 | 38 → **24** | `pip freeze --all` 卸载前后比对；`pipdeptree -r -p` 反查；`pip check` |
| 2026-09-14 | 按规则 2.6 补齐声明缺口：`requirements.txt` 追加 `SQLAlchemy==2.0.52`、`PyMySQL==1.2.0` 两行；`requirements.lock.txt` 第 5 条注释同步；本文件第六节“待办：声明缺口”改为“声明缺口补齐记录” | 24（持平，仅声明层变更，未动 `.venv`） | `pip show SQLAlchemy PyMySQL` 实测输出（SQLAlchemy 2.0.52 / PyMySQL 1.2.0）；`requirements.lock.txt` 第 42/45 行；本文件第六节 `dist-info` 时间戳表格 |
| 2026-09-18 09:25:32–09:25:33 | **第八批：Alembic 链（Day 18 迁移）**：`pip install alembic -i 清华镜像`，新增 alembic + Mako + MarkupSafe；同步写入 `requirements.txt`、`requirements.lock.txt` | 24 → **27** | `dist-info` 创建时间戳；`pip show alembic`（Requires: Mako, SQLAlchemy, typing-extensions）；`pip freeze --all` 实测 27 项；`pip check` 无断裂 |
| 2026-09-28 10:08:01–10:08:05 | **环境结构变更：迁移至 uv 托管**：删除旧 `.venv`（virtualenv 20.38.0 + pip），新建 `pyproject.toml` 后 `uv sync` 重建环境并生成 `uv.lock`；旧 `requirements*.txt` 四份全部保留（双轨并存） | 27 → **26**（uv 重解析全部依赖，无 pip 自身及历史残留；详见第九节） | 新 `pyvenv.cfg` 的 `uv = 0.12.8` 行；`.venv`/`uv.lock` NTFS 创建时间戳；`uv sync` 安装清单输出 |
| 2026-09-28 10:52–10:54（同日后续，文件修改时间实测） | **双轨改单轨：删除 pip 侧四份声明/锁文件**（`requirements.txt` / `requirements-dev.txt` / `requirements.lock.txt` / `requirements-dev.lock.txt`）；`pyproject.toml` + `uv.lock` 成为唯一依赖声明；同步改 README、dev.bat、pyproject.toml 注释中的引用 | 环境未动（仅声明层变更） | `git status` 四个 `D` 状态 + `Test-Path` 实测均 False；`git grep` 引用扫描（详见第九节补记） |

## 二、2026-09-07 新增批次（15 项，全部来自一次 `pip install pipdeptree`）

### 定性结论

**不是恶意包，也不是项目运行时依赖。** 5 个 `nab-*` 包同属 `https://github.com/notatallshaw/nab`（版本齐为 0.0.17），是 pipdeptree 4.x 的依赖解析引擎；其 `Required-by` 字段直接指回 `pipdeptree`。

装 pipdeptree 的动机在本仓库无任何记录（`requirements*.txt`、`README.md`、`run_todo_api.bat` 均未提及），属临时排障/查看依赖树用途 —— 这正是它与环境声明文件产生漂移的原因。

### 依赖归属树（依据各包元数据 `Requires` 还原）

```
pipdeptree==4.2.3                    ← 唯一直接安装的包（根因）
├── nab-index==0.0.17
│   ├── nab-provider==0.0.17
│   │   ├── nab-markersets==0.0.17   （无依赖）
│   │   └── nab-resolver==0.0.17     （无依赖）
│   ├── truststore==0.10.4
│   └── urllib3==2.7.0
└── nab-project==0.0.17
    ├── build==1.6.0
    │   └── colorama==0.4.6
    ├── installer==1.0.1
    ├── pyproject_hooks==1.2.0
    ├── tomli==2.4.1
    ├── tomli_w==1.2.0
    └── packaging==26.3
```

`nab-index` 与 `nab-project` 还要求 `typing-extensions`，但环境里已有 4.16.0 且满足约束，故未新增、未升级。

### 影响面评估

| 维度 | 结果 |
|---|---|
| 原有 21 项版本漂移 | **0 项**（`Compare-Object` 锁文件 vs 当前 freeze，仅有"新增"方向差异，无版本变更、无移除） |
| 运行时链（fastapi / pydantic / uvicorn） | 未受影响，版本与锁文件完全一致 |
| `pip check` | No broken requirements found |
| 体积成本 | 新增 15 个顶层模块，约 **12.2 MB**（最大几项：pipdeptree 4.1 MB、nab_provider 2.3 MB、nab_project 1.0 MB、packaging 1.0 MB、installer 1.0 MB、urllib3 0.9 MB） |
| 自动执行钩子检查 | `site-packages` 下仅 `_virtualenv.pth`（9/2 建环境时生成，virtualenv 自带），**无 9/7 新增的 `.pth` 启动钩子** |

### 归类结论

按运行时/开发分离原则，这 15 项**全部属开发工具链**，一个都不进 `requirements.txt`。归属已落到锁文件里（见第三节）。

## 三、锁文件拆分（2026-09-08 落地）

| 文件 | 收录 | 项数 | 构成 |
|---|---|---|---|
| `requirements.lock.txt` | 运行时 + pip | **19** | 3 直接（pydantic / fastapi / uvicorn）+ 15 传递 + pip；已剥除 pyright、nodeenv |
| `requirements-dev.lock.txt` | 开发工具链 | **17** | pyright 链 2 项 + pipdeptree 链 15 项 |
| 合计 | 两份互斥无重叠 | **36** | 与 `pip freeze --all` 实测逐项一致 |

> 上表为 **2026-09-08 快照**，保留作历史记录。该拆分已于 2026-09-11 重采，最新项数为
> 运行时 **22** + 开发工具链 **2** = **24**，详见第七节。

## 四、决策记录（2026-09-08）

- **pipdeptree：保留在环境中，暂不写入 `requirements-dev.txt`**（即“已装、已锁、未声明”）。因此本次 `requirements-dev.txt` **未作任何改动**，仍为 `-r requirements.txt` + `pyright==1.1.411`。
- 影响：按锁文件安装可完整复刻本机；只按 `requirements.txt` + `requirements-dev.txt` 安装会少 pipdeptree 工具链，但程序运行不受影响（无任何代码 import 它）。
- 后续若决定正式采用：在 `requirements-dev.txt` 补一行 `pipdeptree==4.2.3` 即可，14 个传递依赖不写死。
- 后续若决定弃用：先跑 `pipdeptree -r -p <包名>` 复核无其他引用方，再逐个卸载（卸载属破坏性操作，需单独确认），然后重采 `requirements-dev.lock.txt`（届时仅剩 pyright 链 2 项）。

> **本节决策已被推翻**：2026-09-11 pipdeptree 迁往系统 Python，`.venv` 内的 14 个传递依赖
> 按上述“弃用”路径卸载完毕，`requirements-dev.lock.txt` 已重采为 2 项。执行记录与验证证据见第五节。

## 五、2026-09-11 pipdeptree 迁出与 14 项孤儿依赖卸载

### 背景

pipdeptree 本体已改装到系统 Python（`D:\Program Files\Python\Python314\Scripts\pipdeptree.exe`，版本 **4.2.5**，高于原 `.venv` 内的 4.2.3）。迁出后 `.venv` 里只剩它的传递依赖，本体消失导致这批包失去唯一引用方，成为孤儿。

迁出的具体时间未在仓库留痕；本次盘点时以 `importlib.util.find_spec('pipdeptree')` 返回 `False`、且 `pip freeze --all` 无 pipdeptree 条目为证，确认本体已不在 `.venv`。

### 卸载前的孤儿判定（三重证据）

| 验证项 | 命令 / 依据 | 结果 |
|---|---|---|
| 本体是否还在 | `find_spec('pipdeptree')` | `False`；`pip freeze --all` 亦无该条目 |
| 是否还有引用方 | `pipdeptree --python .\.venv\Scripts\python.exe -r -p <包名>` 逐个反查 | `nab-project` 返回 **(NONE - orphan)**；其余 13 项只被链内互相引用 |
| 代码是否 import | grep 全仓 `*.py` 的 `import`/`from` 语句 | 实际只 import 6 个第三方顶层包：`fastapi`/`pydantic`/`starlette`/`uvicorn`/`sqlalchemy`/`pymysql`，无一指向这 14 项 |
| 安装批次 | `dist-info` 创建时间戳 | 均为 `2026-09-07 15:06`，与第二节记载的那次 `pip install pipdeptree` 同批 |

卸载前实测体积：14 项共 **8.27 MB**（不含已于早前随本体移除的 pipdeptree 4.1 MB）。

### 已卸载的 14 项

```
build==1.6.0            installer==1.0.1        packaging==26.3
colorama==0.4.6         nab-index==0.0.17       pyproject_hooks==1.2.0
tomli==2.4.1            nab-markersets==0.0.17  tomli_w==1.2.0
truststore==0.10.4      nab-project==0.0.17     urllib3==2.7.0
                        nab-provider==0.0.17
                        nab-resolver==0.0.17
```

### 明确保留、不得误删的包

卸载前已逐项排除下列“看似孤儿实为必需”的包：

| 包 | 保留理由（证据） |
|---|---|
| `httptools` / `python-dotenv` / `PyYAML` / `watchfiles` / `websockets` | `uvicorn[standard]` 的 extras 依赖；freeze 与依赖树均丢失 extras 标记才显得无归属方。uvicorn 元数据 `Requires-Dist` 已证 `extra == 'standard'` 列出此 5 项。其中 **watchfiles 为硬需求**——`run_todo_api.bat` 使用 `--reload` |
| `typing_extensions` | 虽也出现在 nab 链的 requires 中，但同时被 `pydantic_core`/`starlette`/`anyio`/`fastapi`/`SQLAlchemy`/`pyright`/`typing-inspection` 依赖 |
| `greenlet` | `SQLAlchemy` 的直接依赖（`pipdeptree -r -p greenlet` 可证） |

### 卸载后验证（证据式验收）

| 验证项 | 命令 | 结果 |
|---|---|---|
| 项数归位 | `pip freeze --all \| Measure-Object -Line` | 38 → **24** |
| 孤儿清零 | `pip freeze --all \| Select-String "nab\|build\|installer\|^packaging\|tomli\|truststore\|urllib3\|colorama\|pyproject"` | **无任何匹配** |
| 依赖无断裂 | `pip check` | `No broken requirements found.` |
| 运行时链完整 | `pipdeptree --python .\.venv\Scripts\python.exe --warn silence` | fastapi → pydantic/starlette/anyio 链、uvicorn → click/h11 链、SQLAlchemy → greenlet 链、pyright → nodeenv 链均完整无缺 |
| 实际导入冒烟 | `python -c "import sqlalchemy,pymysql,pydantic,fastapi,uvicorn,starlette,watchfiles; from todo_api.main import app"` | `all imports OK; routes= 9` —— FastAPI 应用正常加载 9 条路由 |
| 锁文件一致性 | `Compare-Object`（两份锁文件条目 vs `pip freeze --all`） | `lock entries=24  freeze entries=24`，**无差异** |

### 执行过程中遇到的两个障碍（已排除）

1. **多包一次性卸载会在首个包后中止**：`pip uninstall -y a b c ...` 只处理了 `build` 便返回，其余 13 项未动。改为单包命令以 `;` 串联后正常，每批 4 个。
2. **`build` 与 `tomli` 卸载中途失败**：输出停在 `Uninstalling xxx:` 而无 `Successfully uninstalled`，且 `python.exe` 一度报“拒绝访问”。根因是 `.venv\Scripts\python.exe` 有残留进程（PID 23324）持有文件锁；提权重试后 `tomli` 卸载成功。

### 遗留待清理项（未完成）

`build` 卸载中断在 `site-packages` 留下两个 pip 临时残留目录，共 **33 个文件、约 215 KB**：

```
~uild                    27 files, 205.75 KB
~uild-1.6.0.dist-info     6 files,   8.96 KB
```

影响：`pip` 每次执行都报 `WARNING: Ignoring invalid distribution ~uild`；`pipdeptree` 因读到 `~uild-1.6.0.dist-info` 的元数据，会多显示一个幽灵 `build==1.6.0` 节点及其 3 个 `installed: ?` 的空依赖。**不影响 `pip freeze` 结果与程序运行**（freeze 会忽略 `~` 开头目录，24 项统计不含它）。

清理属删除操作，未在本次授权范围内，需人工执行：

```powershell
Remove-Item -Recurse -Force "e:\python_learn\.venv\Lib\site-packages\~uild"
Remove-Item -Recurse -Force "e:\python_learn\.venv\Lib\site-packages\~uild-1.6.0.dist-info"
```

回退手段：系统环境已有 pipdeptree 4.2.5，若日后需要在 `.venv` 内复查依赖树，重装即可连带拉回这 14 项：
`.\.venv\Scripts\python.exe -m pip install pipdeptree -i https://pypi.tuna.tsinghua.edu.cn/simple`

## 六、2026-09-11 新增批次（3 项，SQLAlchemy 链）

| 包 | 版本 | `dist-info` 创建时间 |
|---|---|---|
| `greenlet` | 3.5.5 | 2026-09-11 10:08:10 |
| `SQLAlchemy` | 2.0.52 | 2026-09-11 10:08:13 |
| `PyMySQL` | 1.2.0 | 2026-09-11 10:08:51 |

### 定性结论

**属项目需要的运行时依赖，不是垃圾包；已于 2026-09-14 登记到 `requirements.txt`（参见本节末尾“声明缺口补齐记录”）。**

- 使用证据：`SQLAlchemy.py` 第 1–2 行 `import sqlalchemy` / `import pymysql`，第 4–5 行打印二者版本号。
- 来源佐证：`_学习指南.txt` 第 91、93 行标注“第二阶段：SQLAlchemy ORM + Alembic + 数据库”“Day 15：SQLAlchemy 2 入门”，即学习计划下一阶段的预备安装。
- `greenlet` 非独立安装，是 `SQLAlchemy` 的传递依赖（`Requires: greenlet>=1`，`pipdeptree -r -p greenlet` 可证）。
- 依赖树显示 `PyMySQL` 为顶层根节点，无任何包 `Requires` 它 —— 符合预期：它是数据库驱动，由 SQLAlchemy 在运行时按连接串动态加载，不写在元数据依赖里。

### 声明缺口补齐记录（2026-09-14）

2026-09-11 盘点时，`requirements.txt` 仍只声明 `pydantic` / `fastapi` / `uvicorn[standard]` 三项，**SQLAlchemy 与 PyMySQL 属“已装、已锁、未声明”**，与第二节 pipdeptree 曾经的漂移同类。本次按规则 2.6 补齐声明，`greenlet` 作为传递依赖不写死：

```
SQLAlchemy==2.0.52
PyMySQL==1.2.0
```

#### 版本核对证据（三处一致）

| 来源 | SQLAlchemy | PyMySQL |
|---|---|---|
| `.venv` 实测：`.\.venv\Scripts\python.exe -m pip show SQLAlchemy PyMySQL`（2026-09-14） | 2.0.52 | **1.2.0** |
| `requirements.lock.txt` 第 42 / 45 行 | 2.0.52 | **1.2.0** |
| 本节顶部表格（`dist-info` 创建时间戳） | 2.0.52（10:08:13） | **1.2.0**（10:08:51） |

> 变更记录：本次任务发起时需求描述中的 `PyMySQL==1.1.2` 与上述三处证据均不一致，按规则 2.1 / 3.4 已向用户澄清，用户确认“以锁文件为准”后再写入，无推断成分。

#### 同步更新位置

| 文件 | 变更 |
|---|---|
| `requirements.txt` | 追加两行直接依赖声明；同时补一段“第三阶段（SQLAlchemy ORM）”注释，与现有“第二阶段（FastAPI）”注释风格对齐 |
| `requirements.lock.txt` | 仅第 5 条注释：将“截至 2026-09-11 仍未写入 requirements.txt 声明”改为“2026-09-14 已补写入”；锁定条目本体未动 |
| `DEPENDENCIES.md` 第一节 | 时间线总览追加 2026-09-14 记录 |
| `DEPENDENCIES.md` 第六节 | 定性结论由“尚未登记到声明文件”改为“已于 2026-09-14 登记”；本小节由“待办：声明缺口”重写为“声明缺口补齐记录” |

#### 本次未变更项（明确划线）

- `.venv` 实装版本未动——本次仅为声明层补齐，不涉及 `pip install` / `pip uninstall`。
- `requirements.lock.txt` 与 `requirements-dev.lock.txt` 的锁定条目本体未动，24 项总数持平。
- `requirements-dev.txt` 未动（SQLAlchemy 链属运行时，与开发工具链无关）。
- `SQLAlchemy.py` 的 git untracked 状态与本任务无关，本次不处理。

## 七、锁文件重采结果（2026-09-11）

| 文件 | 收录 | 项数 | 构成 |
|---|---|---|---|
| `requirements.lock.txt` | 运行时 + pip | **22** | 5 直接（pydantic / fastapi / uvicorn[standard] / SQLAlchemy / PyMySQL）+ 16 传递 + pip |
| `requirements-dev.lock.txt` | 开发工具链 | **2** | pyright 1.1.411 + nodeenv 1.10.0 |
| 合计 | 两份互斥无重叠 | **24** | 经 `Compare-Object` 与 `pip freeze --all` 逐项比对，**无差异** |

项数演进：36（9-08）→ 38（9-11 10:08 装 SQLAlchemy 链）→ **24**（9-11 卸载 14 项孤儿）→ **27**（9-18 装 Alembic 链）。

## 八、2026-09-18 新增批次（3 项，Alembic 链 / Day 18 迁移）

### 安装命令与动机

```
.\.venv\Scripts\python.exe -m pip install alembic -i https://pypi.tuna.tsinghua.edu.cn/simple
```

动机：学习计划第三阶段「Day 18：Alembic 迁移」（`_学习指南.txt` 第 112–116 行）要求初始化 Alembic、创建与执行迁移脚本；`_Python_Web全栈开发学习计划要求.txt` 第 10 行将 Alembic 列为后端技术栈之一。按规则 2.6 安装前已向用户说明，用户确认（「继续拍板」）后执行。

### 新增的 3 项（证据）

| 包 | 版本 | `dist-info` 创建时间 | 归属 |
|---|---|---|---|
| `alembic` | 1.20.0 | 2026-09-18 09:25:33 | 直接依赖 |
| `Mako` | 1.4.1 | 2026-09-18 09:25:32 | 传递（alembic Requires: Mako） |
| `MarkupSafe` | 3.0.3 | 2026-09-18 09:25:32 | 传递（Mako Requires: MarkupSafe） |

- `pip show alembic` 实测：`Requires: Mako, SQLAlchemy, typing-extensions`；`Required-by:`（空，无其他包依赖它）。
- SQLAlchemy 2.0.52、typing-extensions 4.16.0、greenlet 3.5.5 环境已存在且满足约束，未升级、未新增。

### 归类结论

**属项目直接依赖，已写入 `requirements.txt`。** alembic 是数据库迁移工具，不被应用运行时代码链（`todo_api` / `todo_app` / `day15_orm` 等）`import`，但按学习计划属后端技术栈的一等成员、部署时执行迁移，故与运行时同列入 `requirements.txt` / `requirements.lock.txt`，而非归到开发工具链（`requirements-dev.txt`）。理由已同步写入 `requirements.lock.txt` 第 6 条注释。

### 同步更新位置

| 文件 | 变更 |
|---|---|
| `requirements.txt` | 追加 `alembic==1.20.0`；补一段「第四阶段（数据库迁移，Day 18）」注释，与既有阶段注释风格对齐 |
| `requirements.lock.txt` | 追加 alembic / Mako / MarkupSafe 三项（按 case-insensitive 字母序插入）；头部计数 22→25（运行时）、24→27（合计）；补第 6 条注释说明归类依据 |
| `DEPENDENCIES.md` 第一节 | 时间线总览追加 2026-09-18 记录 |
| `DEPENDENCIES.md` 第八节 | 本节，记录安装命令、动机、证据与归类 |

### 安装后验证（证据式验收）

| 验证项 | 命令 | 结果 |
|---|---|---|
| 可导入 | `python -c "import alembic, mako, markupsafe; print(...版本)"` | alembic 1.20.0 / mako 1.4.1 / markupsafe 3.0.3 |
| 项数 | `pip freeze --all \| Measure-Object -Line` | 24 → **27** |
| 依赖无断裂 | `pip check` | `No broken requirements found.` |

> 遗留：安装过程中 pip 仍报 `WARNING: Ignoring invalid distribution ~uild`，为第五节记录的 `~uild` 幽灵残留目录所致，与本次无关，不影响 freeze 结果与运行。
> 回退手段：alembic 为新增独立依赖，无其他包 `Required-by` 它，若日后弃用可 `pip uninstall alembic Mako MarkupSafe`（卸载属破坏性操作，需单独确认），再重采锁文件回到 24 项。

## 九、2026-09-28 环境结构变更：迁移至 uv 托管

### 变更内容与动机

用户要求「使用 UV 重建项目」。按规则 2.2（M 档）先出方案经确认后执行；旧依赖文件处置经询问，用户选择「全部保留」（与 pipeline-fault-tracker 先例的删除做法不同，本项目双轨并存）。

| 动作 | 详情 |
|---|---|
| 新建 `pyproject.toml` | `[project].dependencies` 照抄 `requirements.txt` 的 6 个锁定版本；pyright 归入 `[dependency-groups].dev`（对应 `requirements-dev.txt`）；`[tool.uv] package = false`（纯脚本仓库不构建分发）；`[[tool.uv.index]]` 设清华镜像为默认源（本机默认 PyPI 连不上，见 `requirements.txt` 注释） |
| 删除旧 `.venv` | 原为 virtualenv 20.38.0 创建 + pip 26.0.1 管理（旧 `pyvenv.cfg` 已随删除消失，本行依据为迁移前实测 `pip --version` 输出与既有台账记录） |
| `uv sync` 重建 | uv 0.12.8，使用系统 CPython 3.14.7（`D:\Program Files\Python\Python314`）；新 `pyvenv.cfg` 含 `uv = 0.12.8` 行；生成 `uv.lock`（28 个包解析，26 个安装） |

### 证据（时间戳与输出）

- `.venv\pyvenv.cfg` NTFS 创建时间：2026-09-28 10:08:01；`uv.lock` 创建时间：10:08:05。
- `uv sync` 安装清单（26 项，含 dev 组）：alembic 1.20.0 / annotated-doc 0.0.5 / annotated-types 0.8.0 / anyio 4.15.1 / click 8.5.0 / fastapi 0.141.1 / greenlet 3.5.6 / h11 0.16.0 / httptools 0.8.0 / idna 3.20 / mako 1.4.3 / markupsafe 3.0.3 / nodeenv 1.11.0 / pydantic 2.13.5 / pydantic-core 2.46.5 / pymysql 1.2.0 / pyright 1.1.411 / python-dotenv 1.2.3 / pyyaml 6.0.3 / sqlalchemy 2.0.52 / starlette 1.7.0 / typing-extensions 4.16.0 / typing-inspection 0.4.4 / uvicorn 0.52.4 / watchfiles 1.3.0 / websockets 17.1。
- 与旧环境 27 项的差异属工具链自身而非业务依赖：旧环境含 pip 及其历史残留（如第五节 `~uild` 幽灵目录），uv 环境不装 pip；6 个直接依赖版本与 `requirements.txt` 声明逐一相符。

### 同步更新位置

| 文件 | 变更 |
|---|---|
| `pyproject.toml` | 新建（uv 侧依赖声明，双轨中新增的一轨） |
| `uv.lock` | 新生成（uv 侧锁文件；旧 `requirements.lock.txt` / `requirements-dev.lock.txt` 保留不动，但已不再反映当前 `.venv` 实况） |
| `requirements*.txt` 四份 | 未动（用户选择保留） |
| `.gitignore` | 未动（既有 `.venv/` 规则对 uv 环境同样生效；`uv.lock` 不在忽略之列，应纳入版本管理） |
| `DEPENDENCIES.md` | 时间线总览追加 2026-09-28 行 + 本节 |

### 迁移后验证（证据式验收）

| 验证项 | 命令 | 结果 |
|---|---|---|
| 环境托管方 | `Get-Content .\.venv\pyvenv.cfg` | `uv = 0.12.8`，`version_info = 3.14.7` |
| 六个直接依赖可导入 | `uv run python -c "import pydantic, fastapi, uvicorn, sqlalchemy, pymysql, alembic"` | `imports OK 2.0.52 0.141.1` |
| 脚本冒烟 | `uv run python "todolist pydantic.py"` | 正常加载 tasks-pydantic.json 并显示菜单，管道无 stdin 时 `input()` 报 EOFError 退出（预期行为，非环境缺陷） |
| dev 组 | `uv run pyright --version` | pyright 1.1.411 |
| 旧调用路径兼容 | `.\.venv\Scripts\python.exe -c "import fastapi"`、`.\.venv\Scripts\pyright.exe --version` | 均正常（README/既有文档中的启动命令无需改写） |

> 未验证项：`run_day15/16/17/19_demo.py` 等依赖 MySQL 的 demo 未跑（需本地数据库在线，与本次环境迁移无关；导入链已由上表第 2 行覆盖）。
> 回退手段：四份 `requirements*.txt` 均在，可用 `python -m virtualenv .venv` + `pip install -r requirements.lock.txt -r requirements-dev.lock.txt -i 清华镜像` 回到迁移前状态；或删除 `pyproject.toml` + `uv.lock` 后重建。注意旧锁文件采集于 2026-09-18，回退后环境为彼时的 27 项。
> 双轨维护约定：此后新增依赖应同时更新 `pyproject.toml`（跑 `uv sync` 刷新 `uv.lock`）与 `requirements*.txt`，或经用户确认后废弃双轨改为单轨。**→ 已于同日按用户指示废弃双轨，见下方补记。**

### 补记（2026-09-28 同日）：双轨改单轨，删除 pip 侧四份文件

用户指示「将 pip 那套移除」，即删除 `requirements.txt` / `requirements-dev.txt` / `requirements.lock.txt` / `requirements-dev.lock.txt`。

**删除前证据链扫描（规则 3.1）**：`git grep` 全仓引用仅四处——README.md（安装命令）、dev.bat（报错提示文案）、pyproject.toml（注释）、DEPENDENCIES.md（历史台账，保留不动）；无任何 `.py` 代码、无反射/动态调用、无配置引用。四份文件均有 git 提交版本，可回退。

**同步修改**：

| 文件 | 变更 |
|---|---|
| `README.md` 第二节 | 安装步骤改为 `winget install astral-sh.uv` + `uv sync`，并注明旧文件已移除 |
| `dev.bat` | 报错提示改为 pyproject.toml + uv sync 两步；因该文件为 GBK/UTF-8 混合编码，采用字节级替换（Latin1 载体）仅改 ASCII 目标串，GBK 字节原样保留（diff 仅 4 行变更已验证） |
| `pyproject.toml` | 三处注释中「双轨并存/见 requirements.txt」表述改为「已删除，历史可经 git 回溯」 |
| 本文件第一至八节 | 未动（历史台账保留对已删除文件的记述） |

**删除后实测校验（规则 4.3）**：`Test-Path` 四份文件均返回 False；`git status` 显示四个 `D`；临时脚本 `_fix_devbat.ps1` 同样实测已删。

**回退手段**：`git checkout <提交> -- requirements.txt requirements-dev.txt requirements.lock.txt requirements-dev.lock.txt` 可恢复四份文件（最后一次完整版本在提交 `e4e72c1` 及其父提交）；注意旧锁文件采集于 2026-09-18，恢复后不代表当前 `.venv` 实况。

**单轨维护约定（取代上方双轨约定）**：此后新增/升级依赖只改 `pyproject.toml`，跑 `uv sync` 刷新 `uv.lock`，并按规则 2.5 在本台账补节。
