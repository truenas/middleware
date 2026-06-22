"""Restrict per-user TOTP interval to liboath-supported values (30/60)

Revision ID: b3f0a9c41d7e
Revises: 7d3a1f9c2e84
Create Date: 2026-06-19 00:00:00.000000+00:00

"""

import logging

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = "b3f0a9c41d7e"
down_revision = "7d3a1f9c2e84"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")


def upgrade():
    conn = op.get_bind()

    # liboath's usersfile parser only accepts HOTP/T30 and HOTP/T60 time-steps. An interval
    # other than 30 or 60 renders the user's /etc/users.oath entry unparseable, so the user
    # looks unknown to pam_oath and 2FA breaks. The API historically allowed any interval >= 5,
    # so stray rows may exist. Clear the secret and normalize the interval for those rows; the
    # affected users must re-enroll 2FA via user.renew_2fa_secret.
    for row in conn.execute(
        text(
            "SELECT t.id, b.bsdusr_username, t.interval FROM account_twofactor_user_auth t "
            "JOIN account_bsdusers b ON b.id = t.user_id WHERE t.interval NOT IN (30, 60)"
        )
    ).fetchall():
        logger.warning(
            "Clearing unsupported TOTP interval %r for local user %r (row %r); user must re-enroll 2FA.",
            row[2],
            row[1],
            row[0],
        )

    for row in conn.execute(
        text(
            "SELECT id, user_sid, interval FROM account_twofactor_user_auth "
            "WHERE interval NOT IN (30, 60) AND user_id IS NULL AND user_sid IS NOT NULL"
        )
    ).fetchall():
        logger.warning(
            "Clearing unsupported TOTP interval %r for directory user SID %r (row %r); user must re-enroll 2FA.",
            row[2],
            row[1],
            row[0],
        )

    conn.execute(
        text("UPDATE account_twofactor_user_auth SET secret = NULL, interval = 30 WHERE interval NOT IN (30, 60)")
    )


def downgrade():
    pass
