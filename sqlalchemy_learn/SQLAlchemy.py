##创建Engine（连接数据库）
import os
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

# 1. 定义MySQL连接字符串（格式：数据库驱动://用户名:密码@主机:端口/数据库名?参数）
# 以pymysql驱动为例
# 连接串改为从环境变量 DB_URL 读取，不在源码里硬编码账号口令：
# 口令一旦提交就永久留在 Git 历史里，事后删文件也取不回来（本仓库已踩过这个坑）。
# PowerShell 临时设置（仅当前会话有效）：
#     $env:DB_URL = "mysql+pymysql://用户名:口令@localhost:3306/python_learn?charset=utf8mb4"
# 未设置时下面这行会抛 KeyError: 'DB_URL'，是故意的快速失败，好过默默连到错的库。
db_url = os.environ["DB_URL"]

# 2. 创建Engine（echo=True表示打印执行的SQL语句，方便调试，生产环境可关闭）
engine = create_engine(db_url, echo=True)

##创建Base基类和Model模型
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime

# 1. 创建Base基类（所有模型类必须继承此类）
Base = declarative_base()


# 2. 定义User模型类（对应数据库中的user表）
class User(Base):
    # 定义表名（如果不指定，默认用类名小写作为表名）
    __tablename__ = "user"

    # 定义字段：id（主键，自增）
    id = Column(Integer, primary_key=True, autoincrement=True, comment="用户ID")
    # 定义字段：username（用户名，非空，唯一）
    username = Column(String(50), nullable=False, unique=True, comment="用户名")
    # 定义字段：password（密码，非空）
    password = Column(String(100), nullable=False, comment="密码")
    # 定义字段：create_time（创建时间，默认当前时间）
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")

    # 可选：定义__repr__方法，方便打印实例时查看信息
    def __repr__(self):
        return f"User(id={self.id}, username={self.username}, create_time={self.create_time})"

##创建数据表
# 基于Base类创建所有模型对应的数据库表（绑定Engine）
Base.metadata.create_all(engine)

print("数据库表创建成功！")