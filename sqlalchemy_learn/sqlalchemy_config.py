import os

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

# 1. 定义MySQL连接字符串（格式：数据库驱动://用户名:密码@主机:端口/数据库名?参数）
# 以pymysql驱动为例
# 连接串改为从环境变量 DB_URL 读取，不在源码里硬编码账号口令：
# 口令一旦提交就永久留在 Git 历史里，事后删文件也取不回来（本仓库已踩过这个坑）。
# 本文件会被 sqlalchemy_model / _service / _Create / _Update / _Delete 导入，
# 所以跑那几个脚本前都要先设好 DB_URL。PowerShell 临时设置（仅当前会话有效）：
#     $env:DB_URL = "mysql+pymysql://用户名:口令@localhost:3306/python_learn?charset=utf8mb4"
# 未设置时下面这行会抛 KeyError: 'DB_URL'，是故意的快速失败，好过默默连到错的库。
db_url = os.environ["DB_URL"]

# 2. 创建Engine（echo=True表示打印执行的SQL语句，方便调试，生产环境可关闭）
engine = create_engine(db_url, echo=True)
# 3. 创建Session工厂（绑定Engine）
SessionFactory = sessionmaker(bind=engine)
# 4. 创建Base基类（所有模型类必须继承此类）
Base = declarative_base()