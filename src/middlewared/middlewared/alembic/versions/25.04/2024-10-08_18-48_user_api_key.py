"""Convert to user-linked tokens

Revision ID: 8ae49ac78d14
Revises: 85e5d349cdb1
Create Date: 2024-10-08 18:48:55.972115+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
import json


# revision identifiers, used by Alembic.
revision = '8ae49ac78d14'
down_revision = '85e5d349cdb1'
branch_labels = None
depends_on = None

DEFAULT_ALLOW_LIST = [{"method": "*", "resource": "*"}]
ENTRY_REVOKED = -1


def upgrade():
    conn = op.get_bind()
    to_revoke = []
    for row in conn.execute(text("SELECT id, allowlist FROM account_api_key")).fetchall():
        row = row._asdict()
        try:
            if json.loads(row['allowlist']) != DEFAULT_ALLOW_LIST:
                to_revoke.append(str(row['id']))
        except Exception:
            to_revoke.append(str(row['id']))

    with op.batch_alter_table('account_api_key', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_identifier', sa.String(length=200), nullable=False, server_default='LEGACY_API_KEY'))
        batch_op.add_column(sa.Column('expiry', sa.Integer(), nullable=False, server_default='0'))
        batch_op.drop_column('allowlist')

    conn.execute(text(f"UPDATE account_api_key SET expiry={ENTRY_REVOKED} WHERE id IN ({', '.join(to_revoke)});"))


def downgrade():
    pass
