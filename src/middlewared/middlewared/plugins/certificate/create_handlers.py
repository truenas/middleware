from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pydantic
from truenas_crypto_utils.csr import generate_certificate_signing_request

from middlewared.api.current import CertificateCreate
from middlewared.service import ServiceContext, ValidationErrors

from .private_models import (
    CertificateCreateACMEPayload,
    CertificateCreateCSRPayload,
    CertificateCreateImportedCertificatePayload,
    CertificateCreateImportedCSRPayload,
)
from .utils import CERT_TYPE_CSR, CERT_TYPE_EXISTING, get_cert_info_from_data, get_private_key

if TYPE_CHECKING:
    from middlewared.job import Job


__all__ = (
    "create_imported_certificate",
    "create_imported_csr",
    "create_csr",
    "create_acme_certificate",
)


def _raise_validation_errors(
    exc: pydantic.ValidationError,
    schema_prefix: str = "certificate_create",
) -> None:
    verrors = ValidationErrors()
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"])
        verrors.add(f"{schema_prefix}.{loc}" if loc else schema_prefix, err["msg"])
    verrors.check()


def _flatten(data: CertificateCreate) -> dict[str, Any]:
    """Unwrap Secret-wrapped fields and nested Pydantic models into a plain dict
    so the per-type private payload models can re-validate the same input."""
    return data.model_dump(context={"expose_secrets": True})


def create_imported_certificate(
    context: ServiceContext,
    job: Job,
    data: CertificateCreate,
) -> dict[str, Any]:
    raw = _flatten(data)
    try:
        payload = CertificateCreateImportedCertificatePayload(
            name=raw["name"],
            certificate=raw["certificate"],
            privatekey=raw["privatekey"],
            passphrase=raw["passphrase"],
        )
    except pydantic.ValidationError as e:
        _raise_validation_errors(e)
        raise

    job.set_progress(90, "Finalizing changes")
    return {
        "certificate": payload.certificate,
        "privatekey": get_private_key(
            {
                "private_key": payload.privatekey,
                "privatekey": payload.privatekey,
                "passphrase": payload.passphrase,
            }
        ),
        "type": CERT_TYPE_EXISTING,
    }


def create_imported_csr(
    context: ServiceContext,
    job: Job,
    data: CertificateCreate,
) -> dict[str, Any]:
    raw = _flatten(data)
    try:
        payload = CertificateCreateImportedCSRPayload(
            name=raw["name"],
            CSR=raw["CSR"],
            privatekey=raw["privatekey"],
            passphrase=raw["passphrase"],
        )
    except pydantic.ValidationError as e:
        _raise_validation_errors(e)
        raise

    # FIXME: Validate private key matches CSR
    job.set_progress(90, "Finalizing changes")
    return {
        "CSR": payload.CSR,
        "privatekey": get_private_key(
            {
                "private_key": payload.privatekey,
                "privatekey": payload.privatekey,
                "passphrase": payload.passphrase,
            }
        ),
        "type": CERT_TYPE_CSR,
    }


def create_csr(
    context: ServiceContext,
    job: Job,
    data: CertificateCreate,
) -> dict[str, Any]:
    raw = _flatten(data)
    try:
        payload = CertificateCreateCSRPayload(
            name=raw["name"],
            key_length=raw["key_length"],
            key_type=raw["key_type"],
            ec_curve=raw["ec_curve"],
            passphrase=raw["passphrase"],
            city=raw["city"],
            common=raw["common"],
            country=raw["country"],
            email=raw["email"],
            organization=raw["organization"],
            organizational_unit=raw["organizational_unit"],
            state=raw["state"],
            digest_algorithm=raw["digest_algorithm"],
            cert_extensions=raw["cert_extensions"],
            san=raw["san"],
        )
    except pydantic.ValidationError as e:
        _raise_validation_errors(e)
        raise

    cert_info = get_cert_info_from_data(payload.model_dump())
    cert_info["cert_extensions"] = payload.cert_extensions
    req, key = generate_certificate_signing_request(cert_info)
    job.set_progress(90, "Finalizing changes")
    return {
        "CSR": req,
        "privatekey": key,
        "type": CERT_TYPE_CSR,
    }


def create_acme_certificate(
    context: ServiceContext,
    job: Job,
    data: CertificateCreate,
) -> dict[str, Any]:
    raw = _flatten(data)
    try:
        payload = CertificateCreateACMEPayload(
            name=raw["name"],
            tos=raw["tos"],
            csr_id=raw["csr_id"],
            renew_days=raw["renew_days"],
            acme_directory_uri=raw["acme_directory_uri"],
            dns_mapping=raw["dns_mapping"],
        )
    except pydantic.ValidationError as e:
        _raise_validation_errors(e)
        raise

    csr_data = context.call_sync2(context.s.certificate.get_instance, payload.csr_id)
    directory_uri = payload.acme_directory_uri
    if not directory_uri.endswith("/"):
        directory_uri = directory_uri + "/"

    final_order = context.call_sync2(
        context.s.acme.protocol.issue_certificate,
        job,
        25,
        {
            "tos": payload.tos,
            "csr_id": payload.csr_id,
            "acme_directory_uri": directory_uri,
            "dns_mapping": payload.dns_mapping,
        },
        csr_data.model_dump(context={"expose_secrets": True}),
    )
    job.set_progress(95, "Final order received from ACME server")

    registration = context.call_sync2(
        context.s.acme.registration.query,
        [["directory", "=", directory_uri]],
    )
    return {
        "acme": registration[0].id,
        "acme_uri": final_order.uri,
        "certificate": final_order.fullchain_pem,
        "CSR": csr_data.CSR,
        "privatekey": csr_data.privatekey.get_secret_value(),
        "name": payload.name,
        "type": CERT_TYPE_EXISTING,
        "domains_authenticators": payload.dns_mapping,
        "renew_days": payload.renew_days,
    }
