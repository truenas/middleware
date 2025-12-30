# WARNING: DO NOT PUT THINGS IN HERE OTHER THAN TABLE
# INFORMATION. At time of writing, the 2 sqlalchemy
# imports ALONE cause roughly 20MB of heap use.
from sqlalchemy import Table
from sqlalchemy.orm import declarative_base

from middlewared.sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    NativeJSON,
    String
)
from .utils import AUDITED_SERVICES

TABLE_PREFIX = "audit_"
AUDIT_BASE = declarative_base()

__all__ = ("AUDIT_TABLES",)


def audit_table_name(svc, vers):
    return f"{TABLE_PREFIX}{svc}_{str(vers).replace('.', '_')}"


def generate_audit_table(svc, vers):
    """
    NOTE: any changes to audit table schemas should be typically be
    accompanied by a version bump for the audited service and update
    to the guiding design document for structured auditing NEP-041
    and related documents. This will potentially entail changes to
    audit-related code in the above AUDIT_SERVICES independent of the
    middleware auditing backend.

    Currently the DateTime() does not give us fractional second
    precision, but for the purpose of our query interfaces, this
    should be sufficient to figure out when events happened.
    """
    return Table(
        audit_table_name(svc, vers),
        AUDIT_BASE.metadata,
        Column("audit_id", String(36)),
        Column("message_timestamp", Integer()),
        Column("timestamp", DateTime()),
        Column("address", String()),
        Column("username", String()),
        Column("session", String()),
        Column("service", String()),
        Column("service_data", NativeJSON(), nullable=True),
        Column("event", String()),
        Column("event_data", NativeJSON(), nullable=True),
        Column("success", Boolean()),
    )


AUDIT_TABLES = {svc[0]: generate_audit_table(*svc) for svc in AUDITED_SERVICES}
