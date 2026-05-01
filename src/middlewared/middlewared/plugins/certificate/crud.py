from __future__ import annotations

from typing import Any, TYPE_CHECKING

from middlewared.api.current import (
    CertificateEntry,
)
from middlewared.service import CallError, CRUDServicePart, ValidationErrors
import middlewared.sqlalchemy as sa

from .query_utils import normalize_cert_attrs

if TYPE_CHECKING:
    from middlewared.job import Job


class CertificateModel(sa.Model):
    __tablename__ = 'system_certificate'

    id = sa.Column(sa.Integer(), primary_key=True)
    cert_type = sa.Column(sa.Integer())
    cert_name = sa.Column(sa.String(120), unique=True)
    cert_certificate = sa.Column(sa.Text(), nullable=True)
    cert_privatekey = sa.Column(sa.EncryptedText(), nullable=True)
    cert_CSR = sa.Column(sa.Text(), nullable=True)
    cert_acme_uri = sa.Column(sa.String(200), nullable=True)
    cert_domains_authenticators = sa.Column(sa.JSON(dict, encrypted=True), nullable=True)
    cert_renew_days = sa.Column(sa.Integer(), nullable=True, default=10)
    cert_acme_id = sa.Column(sa.ForeignKey('system_acmeregistration.id'), index=True, nullable=True)
    cert_add_to_trusted_store = sa.Column(sa.Boolean(), default=False, nullable=False)


class CertificateServicePart(CRUDServicePart[CertificateEntry]):
    _datastore = 'system.certificate'
    _datastore_prefix = 'cert_'
    _entry = CertificateEntry

    def extend(self, data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        normalize_cert_attrs(data)
        return data
