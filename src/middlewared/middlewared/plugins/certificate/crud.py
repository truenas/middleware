from __future__ import annotations

from typing import Any, TYPE_CHECKING

from truenas_crypto_utils.read import load_certificate, load_certificate_request
from truenas_crypto_utils.utils import RE_CERTIFICATE
from truenas_crypto_utils.validation import validate_certificate_with_key, validate_private_key

from middlewared.api.current import (
    CertificateCreate,
    CertificateEntry,
    CertificateUpdate,
)
from middlewared.async_validators import validate_country
from middlewared.service import CallError, CRUDServicePart, ValidationErrors
from middlewared.utils.lang import undefined
import middlewared.sqlalchemy as sa

from .create_handlers import (
    create_acme_certificate,
    create_csr,
    create_imported_certificate,
    create_imported_csr,
)
from .cert_extensions import validate_extensions
from .query_utils import normalize_cert_attrs

if TYPE_CHECKING:
    from collections.abc import Callable

    from middlewared.job import Job
    from middlewared.service import ServiceContext


__all__ = ('CertificateModel', 'CertificateServicePart')


_CREATE_DISPATCH: dict[str, Callable[[ServiceContext, Job, CertificateCreate], dict[str, Any]]] = {
    'CERTIFICATE_CREATE_IMPORTED': create_imported_certificate,
    'CERTIFICATE_CREATE_IMPORTED_CSR': create_imported_csr,
    'CERTIFICATE_CREATE_CSR': create_csr,
    'CERTIFICATE_CREATE_ACME': create_acme_certificate,
}


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

    async def do_create(self, job: Job, data: CertificateCreate) -> CertificateEntry:
        await self._validate_common_attributes(data, 'certificate_create')
        if data.add_to_trusted_store and data.create_type in (
            'CERTIFICATE_CREATE_IMPORTED_CSR', 'CERTIFICATE_CREATE_CSR',
        ):
            verrors = ValidationErrors()
            verrors.add(
                'certificate_create.add_to_trusted_store',
                'Cannot add CSR to trusted store',
            )
            verrors.check()

        job.set_progress(10, 'Initial validation complete')

        handler = _CREATE_DISPATCH[data.create_type]
        # Handlers are sync (and create_acme_certificate does network I/O); run in a thread.
        # `self` is a ServicePart which IS-a ServiceContext (see service/part.py).
        db_payload: dict[str, Any] = await self.middleware.run_in_thread(
            handler, self, job, data,
        )
        db_payload = {
            **db_payload,
            'name': data.name,
            'add_to_trusted_store': data.add_to_trusted_store,
        }
        cert_entry = await self._create(db_payload)
        await (await self.middleware.call('service.control', 'START', 'ssl')).wait(raise_error=True)
        job.set_progress(100, 'Certificate created successfully')
        return cert_entry

    async def do_update(self, job: Job, id_: int, data: CertificateUpdate) -> CertificateEntry:
        old = await self.get_instance(id_)
        new = old.updated(data)

        if any(
            getattr(new, k) != getattr(old, k)
            for k in ('name', 'renew_days', 'add_to_trusted_store')
        ):
            verrors = ValidationErrors()
            tnc_config = await self.middleware.call('tn_connect.config')
            if tnc_config['certificate'] == id_:
                verrors.add(
                    'certificate_update.name',
                    'This certificate is being used by TrueNAS Connect service '
                    'and cannot be modified',
                )
                verrors.check()

            if new.name != old.name:
                await self._validate_cert_name(new.name, 'certificate_update', verrors)

            # TODO: Test this validation properly
            if new.acme is None and getattr(data, 'renew_days') is not undefined:
                verrors.add(
                    'certificate_update.renew_days',
                    'Certificate renewal days is only supported for ACME certificates',
                )
            if new.add_to_trusted_store and new.cert_type_CSR:
                verrors.add(
                    'certificate_update.add_to_trusted_store',
                    "A CSR cannot be added to the system's trusted store",
                )
            verrors.check()

            update_fields: dict[str, Any] = {
                'name': new.name,
                'add_to_trusted_store': new.add_to_trusted_store,
            }
            if getattr(data, 'renew_days') is not undefined:
                update_fields['renew_days'] = new.renew_days

            await self._update(id_, update_fields)
            await (await self.middleware.call('service.control', 'START', 'ssl')).wait(raise_error=True)

        job.set_progress(90, 'Finalizing changes')
        return await self.get_instance(id_)

    def do_delete(self, job: Job, id_: int, force: bool) -> bool:
        certificate = self.get_instance__sync(id_)
        # FIXME: Port this properly
        self.middleware.call_sync('certificate.check_cert_deps', id_)

        if certificate.acme and not certificate.expired:
            # `certificate.certificate` is a LongStringWrapper here; revoke_certificate
            # takes a plain str. ACME-issued certs always have the cert PEM populated,
            # but guard against None defensively.
            cert_pem = certificate.certificate.value if certificate.certificate else ''
            try:
                self.call_sync2(
                    self.s.acme.protocol.revoke_certificate,
                    self.call_sync2(
                        self.s.acme.protocol.get_acme_client_and_key_payload,
                        certificate.acme['directory'], True,
                    ),
                    cert_pem,
                )
            except CallError:
                if not force:
                    raise

        response: bool = self.middleware.call_sync('datastore.delete', self._datastore, id_)
        self.middleware.call_sync('service.control', 'START', 'ssl').wait_sync(raise_error=True)
        self.call_sync2(self.s.alert.alert_source_clear_run, 'CertificateChecks')
        job.set_progress(100)
        return response

    async def _validate_common_attributes(
        self, data: CertificateCreate, schema: str,
    ) -> None:
        verrors = ValidationErrors()

        # Flatten Secret/LongStringWrapper-typed fields into raw dict[str, Any]
        # so we can hand plain strings to the truenas_crypto_utils helpers.
        raw = data.model_dump(context={'expose_secrets': True})
        certificate: str | None = raw['certificate']
        privatekey: str | None = raw['privatekey']
        csr: str | None = raw['CSR']
        passphrase: str | None = raw['passphrase']

        await self._validate_cert_name(data.name, schema, verrors)

        if data.country:
            await validate_country(
                self.middleware, data.country, verrors, f'{schema}.country',
            )

        if certificate:
            matches = RE_CERTIFICATE.findall(certificate)
            if not matches or not await self.to_thread(
                load_certificate, certificate,
            ):
                verrors.add(f'{schema}.certificate', 'Not a valid certificate')

        if privatekey:
            err = await self.to_thread(validate_private_key, privatekey, passphrase)
            if err:
                verrors.add(f'{schema}.privatekey', err)

        if csr:
            if not await self.to_thread(load_certificate_request, csr):
                verrors.add(f'{schema}.CSR', 'Please provide a valid CSR')

        if data.csr_id is not None:
            existing = await self.call2(
                self.s.certificate.query, [['id', '=', data.csr_id], ['cert_type_CSR', '=', True]]
            )
            if not existing:
                verrors.add(f'{schema}.csr_id', 'Please provide a valid csr_id')

        if not verrors and data.create_type == 'CERTIFICATE_CREATE_IMPORTED':
            err = await self.to_thread(
                validate_certificate_with_key,
                certificate or '', privatekey or '', passphrase,
            )
            if err:
                verrors.add(
                    f'{schema}.privatekey',
                    f'Private key does not match certificate: {err}',
                )

        if data.create_type == 'CERTIFICATE_CREATE_CSR':
            # `key_type` and `digest_algorithm` always have values in the typed
            # CertificateCreate model (Literal default 'RSA' / 'SHA256')
            # We still need to require `key_length` for non-EC keys.
            if data.key_type != 'EC' and data.key_length is None:
                verrors.add(
                    f'{schema}.key_length',
                    'RSA-based keys require an entry in this field.',
                )

            ext_errors = validate_extensions(
                data.cert_extensions.model_dump(),
                schema,
            )
            verrors.extend(ext_errors)

        verrors.check()

    async def _validate_cert_name(
        self, name: str, schema: str, verrors: ValidationErrors,
    ) -> None:
        existing = await self.middleware.call(
            'datastore.query', self._datastore, [('cert_name', '=', name)],
        )
        if existing:
            verrors.add(f'{schema}.name', 'A certificate with this name already exists')
