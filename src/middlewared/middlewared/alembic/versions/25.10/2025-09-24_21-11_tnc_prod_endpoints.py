"""
Moving tn_connect url from staging to production

Revision ID: 53193fbee3ee
Revises: 5ea9f662ced4
Create Date: 2025-09-24 16:44:06.551471+00:00
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '53193fbee3ee'
down_revision = '5ea9f662ced4'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    staging_to_production = {
        'account_service_base_url': {
            'staging': 'https://account-service.staging.truenasconnect.net/',
            'production': 'https://account-service.tys1.truenasconnect.net/'
        },
        'leca_service_base_url': {
            'staging': 'https://dns-service.staging.truenasconnect.net/',
            'production': 'https://dns-service.tys1.truenasconnect.net/'
        },
        'tnc_base_url': {
            'staging': 'https://web.staging.truenasconnect.net/',
            'production': 'https://web.truenasconnect.net/'
        },
        'heartbeat_url': {
            'staging': 'https://heartbeat-service.staging.truenasconnect.net/',
            'production': 'https://heartbeat-service.tys1.truenasconnect.net/'
        }
    }

    result = conn.execute(
        'SELECT id, account_service_base_url, leca_service_base_url, tnc_base_url, heartbeat_url FROM truenas_connect'
    ).fetchall()

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

    all_staging = all(
        current_urls.get(column) == mapping['staging']
        for column, mapping in staging_to_production.items()
    )

    if all_staging:
        set_clauses = []
        for column, mapping in staging_to_production.items():
            set_clauses.append(f"{column} = {mapping['production']!r}")

        update_sql = f"UPDATE truenas_connect SET {', '.join(set_clauses)} WHERE id = {row_id}"
        conn.execute(update_sql)


def downgrade():
    pass
