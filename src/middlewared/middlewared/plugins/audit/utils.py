import middlewared.sqlalchemy as sa

from sqlalchemy import Table
from sqlalchemy.ext.declarative import declarative_base

AUDIT_DATASET_PATH = '/audit'
AUDITED_SERVICES = [('SMB', 0.1)]
AUDIT_TABLE_PREFIX = 'audit_'
AUDIT_LIFETIME = 7  # Temporary hard-coded retention until public APIs developed

AuditBase = declarative_base()


def audit_file_path(svc):
    return f'{AUDIT_DATASET_PATH}/{svc}.db'


def audit_table_name(svc, vers):
    return f'{AUDIT_TABLE_PREFIX}{svc}_{str(vers).replace(".", "_")}'


def generate_audit_table(svc, vers):
    """
    NOTE: any changes to audit table schemas should be typically be
    accompanied by a version bump for the audited service and update
    to the guiding design document for structured auditing NEP-041
    and related documents. This will potentially entail changes to
    audit-related code in the above AUDIT_SERVICES independent of the
    middleware auditing backend.
    """
    return Table(
        audit_table_name(svc, vers),
        AuditBase.metadata,
        sa.Column('aid', sa.String(36)),
        sa.Column('msg_ts', sa.Integer()),
        sa.Column('time', sa.String()),
        sa.Column('addr', sa.String()),
        sa.Column('user', sa.String()),
        sa.Column('sess', sa.String()),
        sa.Column('svc', sa.String()),
        sa.Column('svc_data', sa.JSON(dict), nullable=True),
        sa.Column('event', sa.String()),
        sa.Column('event_data', sa.JSON(dict), nullable=True),
        sa.Column('success', sa.Boolean())
    )


AUDIT_TABLES = {svc[0]: generate_audit_table(*svc) for svc in AUDITED_SERVICES}
