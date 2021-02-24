import copy
import datetime
import errno

from acme import errors, messages

from middlewared.service import Service, ValidationErrors
from middlewared.service_exception import CallError


class ACMEService(Service):

    class Config:
        namespace = 'acme'
        private = True

    def issue_certificate(self, job, progress, data, csr_data):
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
                normalised_san = ':'.join(self.middleware.call_sync('cryptokey.normalize_san', [domain])[0])
                if normalised_san not in dns_mapping_copy:
                    dns_mapping_copy[normalised_san] = domain

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
            if '*' in domain and not domain.startswith('*.'):
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

        acme_client, key = self.middleware.call_sync(
            'acme.get_acme_client_and_key', data['acme_directory_uri'], data['tos']
        )
        try:
            # perform operations and have a cert issued
            order = acme_client.new_order(csr_data['CSR'])
        except messages.Error as e:
            raise CallError(f'Failed to issue a new order for Certificate : {e}')
        else:
            job.set_progress(progress, 'New order for certificate issuance placed')

            dns_mapping = {d.replace('*.', '').split(':', 1)[-1]: v for d, v in dns_mapping_copy.items()}

            try:
                self.handle_authorizations(job, progress, order, dns_mapping, acme_client, key)

                try:
                    # Polling for a maximum of 10 minutes while trying to finalize order
                    # Should we try .poll() instead first ? research please
                    return acme_client.poll_and_finalize(
                        order, datetime.datetime.now() + datetime.timedelta(minutes=10)
                    )
                except errors.TimeoutError:
                    raise CallError('Certificate request for final order timed out')
            finally:
                self.cleanup_authorizations(order, dns_mapping, key)

    def handle_authorizations(self, job, progress, order, dns_mapping, acme_client, key):
        # When this is called, it should be ensured by the function calling this function that for all authorization
        # resource, a domain name dns mapping is available
        # For multiple domain providers in domain names, I think we should ask the end user to specify which domain
        # provider is used for which domain so authorizations can be handled gracefully

        max_progress = (progress * 4) - progress - (progress * 4 / 5)

        for authorization_resource in order.authorizations:
            status = False
            domain = authorization_resource.body.identifier.value
            try:
                progress += (max_progress / len(order.authorizations))
                # BOULDER DOES NOT RETURN WILDCARDS FOR NOW
                # OTHER IMPLEMENTATIONS RIGHT NOW ASSUME THAT EVERY DOMAIN HAS A WILD CARD IN CASE OF DNS CHALLENGE
                challenge = self.get_challenge(authorization_resource.body.challenges)

                if not challenge:
                    raise CallError(f'DNS Challenge not found for domain {domain}', errno=errno.ENOENT)

                self.middleware.call_sync(
                    'acme.dns.authenticator.perform_challenge',
                    self.get_acme_payload(dns_mapping, challenge, domain, key)
                )

                try:
                    status = acme_client.answer_challenge(challenge, challenge.response(key))
                except errors.UnexpectedUpdate as e:
                    raise CallError(f'Error answering challenge for {domain} : {e}')
            finally:
                job.set_progress(progress, f'DNS challenge {"completed" if status else "failed"} for {domain}')

    def get_challenge(self, challenges):
        challenge = None
        for chg in challenges:
            if chg.typ == 'dns-01':
                challenge = chg
        return challenge

    def get_acme_payload(self, dns_mapping, challenge, domain, key):
        return {
            'authenticator': dns_mapping[domain],
            'challenge': challenge.json_dumps(),
            'domain': domain,
            'key': key.json_dumps()
        }

    def cleanup_authorizations(self, order, dns_mapping, key):
        for authorization_resource in order.authorizations:
            domain = authorization_resource.body.identifier.value
            challenge = self.get_challenge(authorization_resource.body.challenges)
            if not challenge:
                continue
            try:
                self.middleware.call_sync(
                    'acme.dns.authenticator.cleanup_challenge',
                    self.get_acme_payload(dns_mapping, challenge, domain, key)
                )
            except Exception:
                self.logger.error('Failed to cleanup challenge for %r domain', domain, exc_info=True)
