from __future__ import annotations

from typing import Any, TYPE_CHECKING

from middlewared.service import Service

from .issue_cert import issue_certificate as _issue_certificate, issue_certificate_impl as _issue_certificate_impl
from .revoke_cert import revoke_certificate as _revoke_certificate
from .utils import (
    get_acme_client_and_key as _get_acme_client_and_key,
    get_acme_client_and_key_payload as _get_acme_client_and_key_payload,
)

if TYPE_CHECKING:
    from middlewared.job import Job


__all__ = ('ACMEProtocolService',)


class ACMEProtocolService(Service):

    class Config:
        namespace = 'acme.protocol'
        private = True

    def get_acme_client_and_key_payload(
        self, acme_directory_uri: str, tos: bool = False,
    ) -> dict[str, Any]:
        return _get_acme_client_and_key_payload(self.context, acme_directory_uri, tos)

    def get_acme_client_and_key(
        self, acme_directory_uri: str, tos: bool = False,
    ) -> tuple[Any, Any]:
        return _get_acme_client_and_key(self.context, acme_directory_uri, tos)

    def issue_certificate(
        self, job: Job[Any], progress: int, data: dict[str, Any], csr_data: dict[str, Any],
    ) -> Any:
        return _issue_certificate(self.context, job, progress, data, csr_data)

    def issue_certificate_impl(
        self, job: Job[Any], progress: int, acme_client_key_payload: dict[str, Any],
        csr: str, dns_mapping_copy: dict[str, Any],
    ) -> Any:
        return _issue_certificate_impl(
            self.context, job, progress, acme_client_key_payload, csr, dns_mapping_copy,
        )

    def revoke_certificate(self, acme_client_key_payload: dict[str, Any], certificate: str) -> None:
        _revoke_certificate(self.context, acme_client_key_payload, certificate)
