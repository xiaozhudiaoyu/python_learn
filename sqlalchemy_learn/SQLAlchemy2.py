import os
from sqlalchemy import Integer, String, DateTime, func, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime

##创建Engine（连接数据库）
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
# 1. 新的 Base 定义
# 2.0 起直接继承 DeclarativeBase 类，替代旧版的 declarative_base() 工厂函数
class Base(DeclarativeBase):
    pass

# 2. 模型定义（使用 mapped_column + Mapped 类型注解，2.0 推荐）
# 注意：Mapped[] 里写的是Python类型（int/str/datetime），不是 DateTime 这种SQL列类型
class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="用户ID")
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, comment="用户名")
    password: Mapped[str] = mapped_column(String(100), nullable=False, comment="密码")
    # 默认值有两种给法，这里两个都写（互不冲突）：
    # default=datetime.now      —— Python端默认值，由SQLAlchemy在执行INSERT时填入当前时间
    # server_default=func.now() —— 数据库端默认值，建表时生成 DEFAULT now()，由MySQL自己填
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, server_default=func.now(), comment="创建时间")

    # 可选：定义__repr__方法，方便打印实例时查看信息
    def __repr__(self):
        return f"User(id={self.id}, username={self.username}, create_time={self.create_time})"

##创建数据表
# 3. 建表（保持原逻辑）
# 基于Base类创建所有模型对应的数据库表（绑定Engine）
# create_all 只建“当前还不存在”的表：已存在的表会被跳过，不会执行 ALTER 去改字段
Base.metadata.create_all(bind=engine)

print("数据库表创建成功！")

##插入数据
from sqlalchemy.orm import sessionmaker
# 1. 创建Session工厂（绑定Engine）
SessionFactory = sessionmaker(bind=engine)
# # 2. 创建Session实例（相当于打开一个数据库连接）
# session = SessionFactory()
# # 3. 创建User实例（相当于创建一条数据）
# user = User(username="huba", password="123456")
# # 4. 将实例添加到Session（相当于“暂存”数据，未提交到数据库）
# session.add(user)
# # 5. 提交事务（将暂存的数据提交到数据库，此时才会真正插入数据）
# session.commit()
# # 6. 执行结束关闭会话
# session.close()

##查询数据
# 1. 重新创建Session
session = SessionFactory()
# 2. 查询所有数据（返回列表，元素为User实例）
all_users = session.query(User).all()
for u in all_users:
    print("###",u)
# 3. 执行结束关闭会话
session.close()