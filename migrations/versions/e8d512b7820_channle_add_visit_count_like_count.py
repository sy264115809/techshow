"""channle add visit_count & like_count

Revision ID: e8d512b7820
Revises: 1fa2a3b23f94
Create Date: 2016-01-04 15:13:44.565949

"""

# revision identifiers, used by Alembic.
revision = 'e8d512b7820'
down_revision = '1fa2a3b23f94'

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('channel', sa.Column('like_count', sa.Integer(), nullable=True))
    op.add_column('channel', sa.Column('visit_count', sa.Integer(), nullable=True))
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('channel', 'visit_count')
    op.drop_column('channel', 'like_count')
    ### end Alembic commands ###
