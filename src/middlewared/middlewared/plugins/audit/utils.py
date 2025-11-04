import os

from sqlalchemy import Table
from sqlalchemy.orm import declarative_base

import middlewared.sqlalchemy as sa
from middlewared.utils.jsonpath import query_filters_json_path_parse
from truenas_verify import mtree_verify

AUDIT_DATASET_PATH = '/audit'
AUDITED_SERVICES = [('MIDDLEWARE', 0.1), ('SMB', 0.1), ('SUDO', 0.1), ('SYSTEM', 0.1)]
AUDIT_TABLE_PREFIX = 'audit_'
AUDIT_LIFETIME = 7
AUDIT_DEFAULT_RESERVATION = 0
AUDIT_DEFAULT_QUOTA = 0
AUDIT_DEFAULT_FILL_CRITICAL = 95
AUDIT_DEFAULT_FILL_WARNING = 75
AUDIT_REPORTS_DIR = os.path.join(AUDIT_DATASET_PATH, 'reports')
SQL_SAFE_FIELDS = frozenset([
    'audit_id',
    'message_timestamp',
    'address',
    'username',
    'session',
    'service',
    'event',
    'success',
])
AUDIT_LOG_PATH_NAME = mtree_verify.LOG_PATH_NAME
# Number of entries yielded by our batched iterator. This should match
# the max limit for audit pagination so that we only ever have to deal
# with one batch
AUDIT_CHUNK_SZ = 10000  # number of audit entries yielded by iterator

AuditBase = declarative_base()


def audit_program(svc):
    if svc == 'SUDO':
        return 'sudo'
    else:
        return f'TNAUDIT_{svc}'


def audit_custom_section(svc, section):
    """
    Can be used to control whether generic SVC mako rendering applies for this section/service.
    """
    if svc == 'SUDO' and section == 'log':
        return True
    return False


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

    Currently the sa.DateTime() does not give us fractional second
    precision, but for the purpose of our query interfaces, this
    should be sufficient to figure out when events happened.
    """
    return Table(
        audit_table_name(svc, vers),
        AuditBase.metadata,
        sa.Column('audit_id', sa.String(36)),
        sa.Column('message_timestamp', sa.Integer()),
        sa.Column('timestamp', sa.DateTime()),
        sa.Column('address', sa.String()),
        sa.Column('username', sa.String()),
        sa.Column('session', sa.String()),
        sa.Column('service', sa.String()),
        sa.Column('service_data', sa.NativeJSON(), nullable=True),
        sa.Column('event', sa.String()),
        sa.Column('event_data', sa.NativeJSON(), nullable=True),
        sa.Column('success', sa.Boolean())
    )


def parse_filter(filter_in, filters_out):
    # handle OR
    if len(filter_in) == 2:
        if filter_in[0] != 'OR':
            raise ValueError(f'{filter_in}: invalid filter')

        for f in filter_in[1]:
            parse_filter(f, filters_out)

        return

    if len(filter_in) != 3:
        raise ValueError(f'{filter_in}: invalid filter')

    # check operation field
    if filter_in[0] == 'service':
        # Since we are now limiting to a single service we'll
        # just ignore filters that try to change what service
        # we're querying. The filter would either have no effect at
        # all or change the query to have no results. Neither option
        # is particularly useful
        return

    if filter_in[0] not in SQL_SAFE_FIELDS:
        if not filter_in[0].startswith(('service_data', 'event_data')):
            raise ValueError(
                f'{filter_in[0]}: specified filter field may not be '
                'specified for filtering on audit queries'
            )

    filters_out.append(filter_in)


def parse_query_filters(filters: list) -> list:
    """
    NOTE: this method should only be called by audit.query

    This method parses the user-provided query-filters and determines
    whether they're safe to pass directly to the SQL backend. Non-safe
    query-fiters will raise a ValueError that call site will change to
    ValidationError. Filters nested JSON fields will be converted into
    JSONPath notation and passed to sqlalchemy for optimized query.
    """
    filters_out = []

    for f in filters:
        parse_filter(f, filters_out)

    return query_filters_json_path_parse(filters_out)


AUDIT_TABLES = {svc[0]: generate_audit_table(*svc) for svc in AUDITED_SERVICES}


async def setup_truenas_verify(middleware, sysver: str) -> int:
    """
    Called by audit setup to generate the initial truenas_verify
    file for an updated or initial TrueNAS version.
    """
    if os.path.exists('/data/skip-truenas-verify'):
        # Takes too much time on developer middleware restart
        return 0

    verify_rc = await middleware.run_in_thread(mtree_verify.do_verify, ['init', sysver])

    return verify_rc
