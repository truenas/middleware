from __future__ import annotations

import copy
from typing import Any, TYPE_CHECKING

from truenas_acme_utils.event import event_callbacks
from truenas_acme_utils.exceptions import CallError as AcmeUtilsCallError
from truenas_acme_utils.issue_cert import issue_certificate as _issue_cert
from truenas_crypto_utils.generate_utils import normalize_san

from middlewared.service import ServiceContext, ValidationErrors
from middlewared.service_exception import CallError

from .utils import get_acme_client_and_key_payload

if TYPE_CHECKING:
    from middlewared.job import Job


def issue_certificate(
    context: ServiceContext, job: Job[Any], progress: int,
    data: dict[str, Any], csr_data: dict[str, Any],
) -> Any:
    context.middleware.call_sync('network.general.will_perform_activity', 'acme')
    verrors = ValidationErrors()

    domains: list[Any] = context.middleware.call_sync('certificate.get_domain_names', csr_data['id'])
    dns_authenticator_ids = [
        o.id for o in context.call_sync2(context.s.acme.dns.authenticator.query)
    ]

    dns_mapping_copy: dict[str, Any] = copy.deepcopy(data['dns_mapping'])
    for domain in data['dns_mapping']:
        if ':' in domain and domain.split(':', 1)[-1] not in dns_mapping_copy:
            dns_mapping_copy[domain.split(':', 1)[-1]] = dns_mapping_copy[domain]
        elif ':' not in domain:
            normalised_san = ':'.join(normalize_san([domain])[0])
            if normalised_san not in dns_mapping_copy:
                dns_mapping_copy[normalised_san] = dns_mapping_copy[domain]

    for domain in domains:
        if domain not in dns_mapping_copy:
            verrors.add(
                'acme_create.dns_mapping',
                f'Please provide DNS authenticator id for {domain}',
            )
        elif dns_mapping_copy[domain] not in dns_authenticator_ids:
            verrors.add(
                'acme_create.dns_mapping',
                f'Provided DNS Authenticator id for {domain} does not exist',
            )
        if domain.endswith('.'):
            verrors.add(
                'acme_create.dns_mapping',
                f'Domain {domain} name cannot end with a period',
            )
        if '*' in domain and not domain.split(':', 1)[-1].startswith('*.'):
            verrors.add(
                'acme_create.dns_mapping',
                'Wildcards must be at the start of domain name followed by a period',
            )
    for domain in data['dns_mapping']:
        if domain not in domains:
            verrors.add(
                'acme_create.dns_mapping',
                f'{domain} not specified in the CSR',
            )

    verrors.check()

    acme_client_key_payload = get_acme_client_and_key_payload(
        context, data['acme_directory_uri'], data['tos'],
    )
    return issue_certificate_impl(
        context, job, progress, acme_client_key_payload, csr_data['CSR'], dns_mapping_copy,
    )


def issue_certificate_impl(
    context: ServiceContext, job: Job[Any], progress: int,
    acme_client_key_payload: dict[str, Any], csr: str, dns_mapping_copy: dict[str, Any],
) -> Any:
    dns_auth = context.middleware.services.acme.dns.authenticator
    authenticators = {
        o.id: o
        for o in context.call_sync2(
            dns_auth.query, [['id', 'in', list(dns_mapping_copy.values())]]
        )
    }
    for domain, authenticator_id in dns_mapping_copy.items():
        auth_details = authenticators[authenticator_id]
        attrs = auth_details.attributes.get_secret_value()
        authenticator_cls = context.call_sync2(
            dns_auth.get_authenticator_internal, attrs.authenticator,
        )
        dns_mapping_copy[domain] = authenticator_cls(
            context.middleware, attrs.model_dump(context={'expose_secrets': True}),
        )

    def progress_callback(progress_int: int, description: str) -> None:
        job.set_progress(progress_int, description)

    event_callbacks.register(progress_callback)
    try:
        return _issue_cert(acme_client_key_payload, csr, dns_mapping_copy, progress)
    except AcmeUtilsCallError as e:
        raise CallError(str(e))
    finally:
        event_callbacks.remove_callback(progress_callback)
