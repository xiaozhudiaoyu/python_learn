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

**属项目需要的运行时依赖，不是垃圾包，但尚未登记到声明文件。**

- 使用证据：`SQLAlchemy.py` 第 1–2 行 `import sqlalchemy` / `import pymysql`，第 4–5 行打印二者版本号。
- 来源佐证：`_学习指南.txt` 第 91、93 行标注“第二阶段：SQLAlchemy ORM + Alembic + 数据库”“Day 15：SQLAlchemy 2 入门”，即学习计划下一阶段的预备安装。
- `greenlet` 非独立安装，是 `SQLAlchemy` 的传递依赖（`Requires: greenlet>=1`，`pipdeptree -r -p greenlet` 可证）。
- 依赖树显示 `PyMySQL` 为顶层根节点，无任何包 `Requires` 它 —— 符合预期：它是数据库驱动，由 SQLAlchemy 在运行时按连接串动态加载，不写在元数据依赖里。

### 待办：声明缺口

截至 2026-09-11，`requirements.txt` 仍只声明 `pydantic` / `fastapi` / `uvicorn[standard]` 三项，**SQLAlchemy 与 PyMySQL 属“已装、已锁、未声明”**，与第二节 pipdeptree 曾经的漂移同类。另 `SQLAlchemy.py` 的 git 状态为 `??`（untracked），尚无提交记录。

补齐方式（未在本次授权范围内执行，待确认）：在 `requirements.txt` 追加两行，`greenlet` 作为传递依赖不写死：

```
SQLAlchemy==2.0.52
PyMySQL==1.2.0
```

## 七、锁文件重采结果（2026-09-11）

| 文件 | 收录 | 项数 | 构成 |
|---|---|---|---|
| `requirements.lock.txt` | 运行时 + pip | **22** | 5 直接（pydantic / fastapi / uvicorn[standard] / SQLAlchemy / PyMySQL）+ 16 传递 + pip |
| `requirements-dev.lock.txt` | 开发工具链 | **2** | pyright 1.1.411 + nodeenv 1.10.0 |
| 合计 | 两份互斥无重叠 | **24** | 经 `Compare-Object` 与 `pip freeze --all` 逐项比对，**无差异** |

项数演进：36（9-08）→ 38（9-11 10:08 装 SQLAlchemy 链）→ **24**（9-11 卸载 14 项孤儿）。
