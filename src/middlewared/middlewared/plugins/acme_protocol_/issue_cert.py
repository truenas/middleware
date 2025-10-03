import copy

from acme.messages import OrderResource
from truenas_acme_utils.client_utils import ACMEClientAndKeyData
from truenas_acme_utils.event import event_callbacks
from truenas_acme_utils.exceptions import CallError as AcmeUtilsCallError
from truenas_acme_utils.issue_cert import issue_certificate
from truenas_crypto_utils.generate_utils import normalize_san

from middlewared.service import Service, ValidationErrors
from middlewared.service_exception import CallError


class ACMEService(Service):

    class Config:
        namespace = 'acme'
        private = True

    def issue_certificate(self, job, progress: int, data: dict, csr_data: dict) -> OrderResource:
        """
        How we would like to proceed with issuing an ACME cert is as follows:
        1) Decide domains which are involved
        2) Validate we have valid authenticators for domains involved
        3) Place Order
        4) Handle Authorizations
        5) Clean up challenge ( we should do this even if 3/4 fail to ensure there are no leftovers )
        """
        self.middleware.call_sync('network.general.will_perform_activity', 'acme')
        verrors = ValidationErrors()

        # TODO: Add ability to complete DNS validation challenge manually

        # Validate domain dns mapping for handling DNS challenges
        # Ensure that there is an authenticator for each domain in the CSR
        domains = self.middleware.call_sync('certificate.get_domain_names', csr_data['id'])
        dns_authenticator_ids = [o['id'] for o in self.middleware.call_sync('acme.dns.authenticator.query')]

        dns_mapping_copy = copy.deepcopy(data['dns_mapping'])
        # We will normalise domain authenticators to ensure consistency between SAN "DNS:*" prefixes
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
                    f'Please provide DNS authenticator id for {domain}'
                )
            elif dns_mapping_copy[domain] not in dns_authenticator_ids:
                verrors.add(
                    'acme_create.dns_mapping',
                    f'Provided DNS Authenticator id for {domain} does not exist'
                )
            if domain.endswith('.'):
                verrors.add(
                    'acme_create.dns_mapping',
                    f'Domain {domain} name cannot end with a period'
                )
            if '*' in domain and not domain.split(':', 1)[-1].startswith('*.'):
                verrors.add(
                    'acme_create.dns_mapping',
                    'Wildcards must be at the start of domain name followed by a period'
                )
        for domain in data['dns_mapping']:
            if domain not in domains:
                verrors.add(
                    'acme_create.dns_mapping',
                    f'{domain} not specified in the CSR'
                )

        verrors.check()

        acme_client_key_payload = self.middleware.call_sync(
            'acme.get_acme_client_and_key_payload', data['acme_directory_uri'], data['tos']
        )
        return self.issue_certificate_impl(
            job,
            progress,
            acme_client_key_payload,
            csr_data['CSR'].encode(),
            dns_mapping_copy,
        )

    def issue_certificate_impl(
        self, job, progress: int, acme_client_key_payload: ACMEClientAndKeyData, csr: bytes, dns_mapping_copy: dict
    ) -> OrderResource:
        # Let's make sure for dns mapping, we have authenticator objects in place
        authenticators = {
            o['id']: o
            for o in self.middleware.call_sync(
                'acme.dns.authenticator.query', [['id', 'in', list(dns_mapping_copy.values())]]
            )
        }
        for domain, authenticator_id in dns_mapping_copy.items():
            auth_details = authenticators[authenticator_id]
            dns_mapping_copy[domain] = self.middleware.call_sync(
                'acme.dns.authenticator.get_authenticator_internal', auth_details['attributes']['authenticator'],
            )(self.middleware, auth_details['attributes'])

        def progress_callback(progress_int, description):
            job.set_progress(progress_int, description)

        event_callbacks.register(progress_callback)
        try:
            return issue_certificate(acme_client_key_payload, csr, dns_mapping_copy, progress)
        except AcmeUtilsCallError as e:
            raise CallError(str(e))
        finally:
            event_callbacks.remove_callback(progress_callback)
