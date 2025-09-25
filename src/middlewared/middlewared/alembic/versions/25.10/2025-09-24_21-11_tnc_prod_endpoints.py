"""
Moving tn_connect url from staging to production

Revision ID: 53193fbee3ee
Revises: 5ea9f662ced4
Create Date: 2025-09-24 16:44:06.551471+00:00
"""
from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '53193fbee3ee'
down_revision = '5ea9f662ced4'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    production_urls = {
        'account_service_base_url': 'https://account-service.tys1.truenasconnect.net/',
        'leca_service_base_url': 'https://dns-service.tys1.truenasconnect.net/',
        'tnc_base_url': 'https://web.truenasconnect.net/',
        'heartbeat_url': 'https://heartbeat-service.tys1.truenasconnect.net/'
    }

    result = conn.execute(text(
        'SELECT id, account_service_base_url, leca_service_base_url, tnc_base_url, heartbeat_url FROM truenas_connect'
    )).fetchall()

    if not result:
        return

    row = result[0]
    row_id = row[0]
    current_urls = {
        'account_service_base_url': row[1],
        'leca_service_base_url': row[2],
        'tnc_base_url': row[3],
        'heartbeat_url': row[4]
    }

    all_non_prod = all(
        current_urls.get(column) and ('.dev.' in current_urls[column] or '.staging.' in current_urls[column])
        for column in production_urls.keys()
    )

    if all_non_prod:
        set_clauses = []
        for column, new_url in production_urls.items():
            set_clauses.append(f"{column} = {new_url!r}")

        update_sql = text(f"UPDATE truenas_connect SET {', '.join(set_clauses)} WHERE id = {row_id}")
        conn.execute(update_sql)


def downgrade():
    pass
