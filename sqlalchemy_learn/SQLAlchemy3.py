# cd e:\python_learn; .\.venv\Scripts\python.exe -X utf8 -c "
from sqlalchemy_config import engine, Base
from sqlalchemy_model import Account
from sqlalchemy.orm import Session
Base.metadata.create_all(engine)          # 只建缺失的表，user 表不受影响
with Session(engine) as s:
    s.add_all([Account(age=20), Account(age=20), Account(age=30)])
    s.commit()
    print('account rows =', s.query(Account).count())
