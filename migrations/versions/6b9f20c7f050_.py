"""empty message

Revision ID: 6b9f20c7f050
Revises: b25fae3aaf8c
Create Date: 2023-05-16 17:30:43.682948

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6b9f20c7f050'
down_revision = 'b25fae3aaf8c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('device',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('secret', sa.String(length=8), nullable=False),
    sa.Column('name', sa.String(length=20), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('secret')
    )
    op.create_table('appliance',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=8), nullable=False),
    sa.Column('type', sa.String(length=10), nullable=False),
    sa.Column('value', sa.Float(), nullable=False),
    sa.Column('mode', sa.Integer(), nullable=False),
    sa.Column('mode_time', sa.Integer(), nullable=False),
    sa.Column('device_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['device_id'], ['device.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('appliance')
    op.drop_table('device')
    # ### end Alembic commands ###
