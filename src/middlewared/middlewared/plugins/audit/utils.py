import os

from sqlalchemy import Table
from sqlalchemy.orm import declarative_base

import middlewared.sqlalchemy as sa
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
        sa.Column('service_data', sa.JSON(dict), nullable=True),
        sa.Column('event', sa.String()),
        sa.Column('event_data', sa.JSON(dict), nullable=True),
        sa.Column('success', sa.Boolean())
    )


def parse_query_filters(
    services: list,
    filters: list,
    skip_sql_filters: bool
) -> tuple:
    """
    NOTE: this method should only be called by audit.query

    This method tries to optimize audit query based on provided filter.
    Optimizations are:

    1. limit databases queried
    2. generate sql filters where appropriate

    returns a tuple of services that should be queried on backend and validated
    SQL-safe filters.

    We err on side of caution here since we're dealing with audit results.
    This means that we skip optimized filters if the field is a JSON one, and
    do not try to pass disjunctions to sqlalchemy. In future if needed we
    can loosen these restrictions with appropriate levels of testing and
    validation in auditbackend plugin.
    """
    services_to_check = services_in = set(services)
    filters_out = []

    for f in filters:
        if len(f) != 3:
            continue

        if f[0] == 'service':
            # we are potentially limiting which services may be audited

            if isinstance(f[2], str):
                svcs = set([f[2]])
            else:
                svcs = set(f[2])

            match f[1]:
                case '=' | 'in':
                    if services_in == services_to_check:
                        services_to_check = svcs
                    else:
                        services_to_check = services_to_check & svcs
                case '!=' | 'nin':
                    services_to_check = services_to_check - svcs
                case _:
                    # Other filters quite unlikely to be used
                    # by end-users so we'll just skip optimization
                    # and rely on filter_list later on
                    pass

            if not services_to_check:
                # These filters are guaranteed to have no results. Bail
                # early and let caller handle it.
                break

        if skip_sql_filters:
            # User has manually specified to pass all these filters to datastore
            continue

        if f[0] not in SQL_SAFE_FIELDS:
            # Keys that contain JSON data are not currently supported
            continue

        filters_out.append(f)

    return (services_to_check, filters_out)


def requires_python_filtering(
    services: list,
    filters_in: list,
    filters_for_sql: list,
    options: dict
) -> bool:
    """
    There are situations where we have to perform additional audit filtering
    in python via `filter_list`.

    1. Not all user specified filters could be converted directly into an SQL
       statement for auditbackend.query.

    2. We are selecting a subkey within a JSON object.

    3. Multiple services are being queried and pagination options are being used
       or a specific ordering is specified.
    """
    if filters_in != filters_for_sql:
        # We will need to do additional filtering after retrieval
        return True

    if (to_investigate := set(options.get('select', [])) - SQL_SAFE_FIELDS):
        # Field is being selected that may not be safe for SQL select
        for entry in to_investigate:
            # Selecting subkey in entry is not currently supported
            if '.' in entry or isinstance(entry, tuple):
                return True

    if len(services) > 1:
        # When we have more than one database being queried we
        # often need to pass the aggregated results to filter_list
        if options.get('offset') or options.get('limit'):
            # We need to do pagination on total results.
            return True
        if options.get('order_by'):
            return True

    return False


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
