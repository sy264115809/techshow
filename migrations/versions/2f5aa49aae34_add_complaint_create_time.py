"""add complaint create time

Revision ID: 2f5aa49aae34
Revises: 19a2c55adb6c
Create Date: 2016-01-15 15:29:55.391572

"""

# revision identifiers, used by Alembic.
revision = '2f5aa49aae34'
down_revision = '19a2c55adb6c'

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('complaint', sa.Column('created_at', sa.DateTime(), nullable=True))
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('complaint', 'created_at')
    ### end Alembic commands ###
