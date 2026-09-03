# Python Web 全栈开发 · 第一阶段练习仓库

本仓库记录 Python Web 全栈学习计划 **【第一阶段：Python 基础】** 的动手练习。
以命令行「待办清单（TodoList）」为载体，按学习日逐步演进：

> 流程控制 → 函数 → 类 → 类型标注 + 静态检查 → JSON 文件持久化 → async/await → 模块化包结构

并使用 Git 进行版本管理，遵循约定式提交（`type(scope): subject`）。

## 一、环境要求

- Python 3.11+（实测运行于 CPython 3.14.7）
- 虚拟环境：`.venv`（不纳入版本管理，需自行创建）
- 平台：Windows / PowerShell

## 二、安装步骤

```powershell
# 1. 创建虚拟环境
python -m venv .venv

# 2. 安装运行时依赖（只有 pydantic 版本需要）
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 3. 安装开发工具：Pyright 静态类型检查（可选）
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

> 只用标准库的版本（`todolist.py`、dataclass 版、async 版、`todo_app` 包）无需安装依赖即可运行；
> 仅 `todolist pydantic.py` 需要 `pydantic`。

## 三、运行方法

```powershell
# 交互式命令行待办清单（增删改查 + JSON 持久化）
.\.venv\Scripts\python.exe todolist.py

# async/await 演示（顺序 await vs 并发 gather 的耗时对比）
.\.venv\Scripts\python.exe "todolist async.py"

# 模块化包结构演示（models / storage / service + __init__.py）
.\.venv\Scripts\python.exe run_todo_app.py
```

## 四、代码演进与文件说明

| 学习日 | 主题 | 对应文件 |
|--------|------|----------|
| Day 1 | 环境 / 变量 / 数据类型 / 流程控制 | `hello.py`、`todolist.py`（雏形） |
| Day 2 | 函数 + 常用集合操作 | `todolist def.py` |
| Day 3 | 类 + 模块 / 包 / 项目结构 | `todolist class.py`、`todo_app/` 包 |
| Day 4 | 类型标注 + typing + 异常 + 静态检查 | `todolist class typing.py`、`todolist.py` |
| Day 5 | JSON + 文件读写 + async/await | `todolist.py`、`todolist async.py` |
| 拓展 | dataclass / pydantic 对照版本 | `todolist dataclass.py`、`todolist pydantic.py` |

### 包结构 `todo_app/`

```
todo_app/
├── __init__.py    # 包入口：标识包 + 对外暴露 Task / TodoList
├── models.py      # 数据模型 Task
├── storage.py     # JSON 持久化读写（相对导入 models）
└── service.py     # 业务逻辑 TodoList（组合 models + storage）
run_todo_app.py    # 顶层入口脚本（演示从包外绝对导入）
```

## 五、静态类型检查

```powershell
.\.venv\Scripts\pyright.exe "todolist.py"
.\.venv\Scripts\pyright.exe todo_app run_todo_app.py
```

## 六、其他说明

- 运行时数据文件（`tasks*.json`）、虚拟环境（`.venv/`）、IDE 配置（`.idea/`）、学习文档（`*.docx`）与个人笔记（`structure`）均在 `.gitignore` 中忽略，不纳入版本管理。
- 本仓库为学习用途，代码附带中文注释，帮助理解每一步的设计取舍。
