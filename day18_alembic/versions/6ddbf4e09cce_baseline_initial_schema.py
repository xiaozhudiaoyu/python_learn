"""baseline initial schema

Revision ID: 6ddbf4e09cce
Revises: 
Create Date: 2026-09-18 09:48:24.826016

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6ddbf4e09cce'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ── 手写基线（Day 18）────────────────────────────────
    # 本项目在 Day 15~17 是用 Base.metadata.create_all() 直接建表的，
    # 引入 Alembic 时数据库里 4 张表早已存在。若此刻直接 autogenerate，
    # 它对"已存在且与模型一致"的表不会产出任何 CREATE，得到的基线是空的——
    # 换一台空库跑 upgrade head 就无法重建出 schema，基线失去意义。
    #
    # 因此这里【手写】一份完整的建表基线：按外键依赖顺序 create_table
    # （先被引用的 users、tags，再引用它们的 todos、todo_tags），
    # 列定义严格对照 models.py 与 CreateTable 渲染出的 MySQL DDL。
    # 对现有库我们用 `alembic stamp head` 打标记（只写 alembic_version，
    # 不真跑下面的 CREATE），空库则能靠它从零重建——两种场景都成立。
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False, comment='用户主键，数据库自增'),
        sa.Column('username', sa.String(length=50), nullable=False, comment='登录名，全表唯一'),
        sa.Column('email', sa.String(length=120), nullable=True, comment='邮箱，选填'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False, comment='入库时间，由数据库生成'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
        mysql_engine='InnoDB',
        mysql_charset='utf8mb4',
    )
    op.create_table(
        'tags',
        sa.Column('id', sa.Integer(), nullable=False, comment='标签主键，数据库自增'),
        sa.Column('name', sa.String(length=30), nullable=False, comment='标签名称，全表唯一'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        mysql_engine='InnoDB',
        mysql_charset='utf8mb4',
    )
    op.create_table(
        'todos',
        sa.Column('id', sa.Integer(), nullable=False, comment='任务主键，数据库自增'),
        sa.Column('content', sa.String(length=200), nullable=False, comment='任务内容，1~200 字'),
        sa.Column('done', sa.Boolean(), nullable=False, comment='是否已完成，默认未完成'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False, comment='入库时间，由数据库生成'),
        sa.Column('owner_id', sa.Integer(), nullable=True, comment='所属用户 ID，外键关联 users.id'),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        mysql_engine='InnoDB',
        mysql_charset='utf8mb4',
    )
    op.create_table(
        'todo_tags',
        sa.Column('todo_id', sa.Integer(), nullable=False),
        sa.Column('tag_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['todo_id'], ['todos.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('todo_id', 'tag_id'),
        mysql_engine='InnoDB',
        mysql_charset='utf8mb4',
    )


def downgrade() -> None:
    """Downgrade schema."""
    # 回滚顺序与 upgrade 相反：先删引用别人的表（todo_tags、todos），
    # 再删被引用的表（tags、users）。顺序反了会因外键仍存在而 DROP 失败。
    op.drop_table('todo_tags')
    op.drop_table('todos')
    op.drop_table('tags')
    op.drop_table('users')
