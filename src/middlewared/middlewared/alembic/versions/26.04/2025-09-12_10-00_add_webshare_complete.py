"""Add complete WebShare functionality

Revision ID: 12ab58fd8105
Revises: 94d4fd77c063
Create Date: 2025-09-12 10:00:00.000000+00:00

This migration creates the WebShare service with the new shares
configuration structure:
1. Create webshare service configuration table with shares array
2. Add webshare to services list
3. Include home directory configuration fields
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '12ab58fd8105'
down_revision = '94d4fd77c063'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create webshare service configuration table
    op.create_table(
        'services_webshare',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('srv_truenas_host', sa.String(length=255), nullable=False),
        sa.Column('srv_log_level', sa.String(length=20), nullable=False),
        sa.Column('srv_session_log_retention', sa.Integer(), nullable=False),
        sa.Column('srv_enable_web_terminal', sa.Boolean(), nullable=False),
        sa.Column('srv_bulk_download_pool', sa.String(length=255),
                  nullable=True),
        sa.Column('srv_search_index_pool', sa.String(length=255),
                  nullable=True),
        sa.Column('srv_shares', sa.JSON(), nullable=False,
                  server_default='[]'),
        sa.Column('srv_home_directory_template', sa.String(length=255),
                  nullable=False, server_default='{{.Username}}'),
        sa.Column('srv_home_directory_perms', sa.String(length=4),
                  nullable=False, server_default='0700'),
        sa.Column('srv_search_enabled', sa.Boolean(), nullable=False),
        sa.Column('srv_search_directories', sa.JSON(), nullable=False),
        sa.Column('srv_search_max_file_size', sa.Integer(), nullable=False),
        sa.Column('srv_search_supported_types', sa.JSON(),
                  nullable=False),
        sa.Column('srv_search_worker_count', sa.Integer(),
                  nullable=False),
        sa.Column('srv_search_archive_enabled', sa.Boolean(),
                  nullable=False),
        sa.Column('srv_search_archive_max_depth', sa.Integer(),
                  nullable=False),
        sa.Column('srv_search_archive_max_size', sa.Integer(),
                  nullable=False),
        sa.Column('srv_search_index_max_size', sa.Integer(),
                  nullable=False),
        sa.Column('srv_search_index_cleanup_enabled', sa.Boolean(),
                  nullable=False),
        sa.Column('srv_search_index_cleanup_threshold', sa.Integer(),
                  nullable=False),
        sa.Column('srv_search_pruning_enabled', sa.Boolean(),
                  nullable=False),
        sa.Column('srv_search_pruning_schedule', sa.String(length=20),
                  nullable=False),
        sa.Column('srv_search_pruning_start_time', sa.String(length=10),
                  nullable=False),
        sa.Column('srv_pam_service_name', sa.String(length=50),
                  nullable=False, server_default='webshare'),
        sa.Column('srv_allowed_groups', sa.JSON(), nullable=False,
                  server_default='["webshare"]'),
        sa.Column('srv_proxy_port', sa.Integer(), nullable=False,
                  server_default='755'),
        sa.Column('srv_proxy_bind_addrs', sa.JSON(), nullable=False,
                  server_default='["0.0.0.0"]'),
        sa.Column('srv_storage_admins', sa.Boolean(), nullable=False,
                  server_default='false'),
        sa.Column('srv_passkey_mode', sa.String(length=20), nullable=False,
                  server_default='disabled'),
        sa.Column('srv_passkey_rp_origins', sa.JSON(), nullable=False,
                  server_default='[]'),
        sa.PrimaryKeyConstraint('id')
    )

    # 2. Insert default webshare configuration
    supported_types = '["image", "audio", "video", "document", ' \
                      '"archive", "text", "disk_image"]'
    op.execute(f"""
        INSERT INTO services_webshare (
            id,
            srv_truenas_host,
            srv_log_level,
            srv_session_log_retention,
            srv_enable_web_terminal,
            srv_bulk_download_pool,
            srv_search_index_pool,
            srv_shares,
            srv_home_directory_template,
            srv_home_directory_perms,
            srv_search_enabled,
            srv_search_directories,
            srv_search_max_file_size,
            srv_search_supported_types,
            srv_search_worker_count,
            srv_search_archive_enabled,
            srv_search_archive_max_depth,
            srv_search_archive_max_size,
            srv_search_index_max_size,
            srv_search_index_cleanup_enabled,
            srv_search_index_cleanup_threshold,
            srv_search_pruning_enabled,
            srv_search_pruning_schedule,
            srv_search_pruning_start_time,
            srv_pam_service_name,
            srv_allowed_groups,
            srv_proxy_port,
            srv_proxy_bind_addrs,
            srv_storage_admins,
            srv_passkey_mode,
            srv_passkey_rp_origins
        ) VALUES (
            1,
            'localhost',
            'info',
            20,
            false,
            NULL,
            NULL,
            '[]',
            '{{.Username}}',
            '0700',
            false,
            '[]',
            104857600,
            '{supported_types}',
            4,
            true,
            2,
            524288000,
            10737418240,
            true,
            90,
            false,
            'daily',
            '23:00',
            'webshare',
            '["webshare"]',
            755,
            '["0.0.0.0"]',
            false,
            'disabled',
            '[]'
        )
    """)

    # 3. Add webshare to the services_services table
    op.execute(
        "INSERT INTO services_services (srv_service, srv_enable) "
        "VALUES ('webshare', 0)"
    )


def downgrade():
    # Remove webshare from services_services
    op.execute("DELETE FROM services_services WHERE srv_service = 'webshare'")

    # Drop webshare service configuration table
    op.drop_table('services_webshare')
