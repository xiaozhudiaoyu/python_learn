##创建Engine（连接数据库）
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

# 1. 定义MySQL连接字符串（格式：数据库驱动://用户名:密码@主机:端口/数据库名?参数）
# 以pymysql驱动为例
db_url = "mysql+pymysql://sqlalchemy:StrongPass!123@localhost:3306/python_learn?charset=utf8mb4"

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