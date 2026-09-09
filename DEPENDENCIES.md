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

## 四、决策记录（2026-09-08）

- **pipdeptree：保留在环境中，暂不写入 `requirements-dev.txt`**（即“已装、已锁、未声明”）。因此本次 `requirements-dev.txt` **未作任何改动**，仍为 `-r requirements.txt` + `pyright==1.1.411`。
- 影响：按锁文件安装可完整复刻本机；只按 `requirements.txt` + `requirements-dev.txt` 安装会少 pipdeptree 工具链，但程序运行不受影响（无任何代码 import 它）。
- 后续若决定正式采用：在 `requirements-dev.txt` 补一行 `pipdeptree==4.2.3` 即可，14 个传递依赖不写死。
- 后续若决定弃用：先跑 `pipdeptree -r -p <包名>` 复核无其他引用方，再逐个卸载（卸载属破坏性操作，需单独确认），然后重采 `requirements-dev.lock.txt`（届时仅剩 pyright 链 2 项）。
