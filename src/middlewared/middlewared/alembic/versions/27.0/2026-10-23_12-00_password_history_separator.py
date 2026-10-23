"""Repair the password history separator written by user.set_password

Revision ID: c0b88ffd8a23
Revises: bbce11d3cbd7
Create Date: 2026-10-23 12:00:00.000000+00:00

"""
from alembic import op
from sqlalchemy import text

from middlewared.utils.pwenc import decrypt, encrypt


# revision identifiers, used by Alembic.
revision = 'c0b88ffd8a23'
down_revision = 'bbce11d3cbd7'
branch_labels = None
depends_on = None


def normalize_history(history: str) -> str:
    # user.set_password joined the hashes with ', ' while every reader splits on whitespace, so
    # each hash but the last kept a trailing comma and no longer matched the password that produced
    # it. Commas never appear in a crypt hash, so dropping them recovers the original hash.
    return ' '.join(history.replace(',', ' ').split())


def upgrade():
    conn = op.get_bind()

    for row in conn.execute(text('SELECT id, bsdusr_password_history FROM account_bsdusers')).mappings().all():
        if not (history := decrypt(row['bsdusr_password_history'])):
            continue

        normalized = normalize_history(history)
        if normalized == history:
            continue

        conn.execute(
            text('UPDATE account_bsdusers SET bsdusr_password_history = :history WHERE id = :id'),
            {'history': encrypt(normalized), 'id': row['id']},
        )


def downgrade():
    pass
