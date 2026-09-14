from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from sqlalchemy_config import Base


# 定义User模型类（对应数据库中的user表）
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


# 定义Account模型类（对应数据库中的account表）
# 供 sqlalchemy_service.py 的分组查询示例使用，代码里只用到了 id 与 age 两个字段
class Account(Base):
    # 定义表名（如果不指定，默认用类名小写作为表名）
    __tablename__ = "account"

    # 定义字段：id（主键，自增）
    id = Column(Integer, primary_key=True, autoincrement=True, comment="账户ID")
    # 定义字段：age（年龄，非空，分组查询的分组列）
    age = Column(Integer, nullable=False, comment="年龄")

    # 可选：定义__repr__方法，方便打印实例时查看信息
    def __repr__(self):
        return f"Account(id={self.id}, age={self.age})"