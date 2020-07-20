from certbot.plugins import dns_common
from CloudFlare.cloudflare import CloudFlare, CloudFlareAPIError

from middlewared.service import CallError, private, Service


class DNSAuthenticatorService(Service):

    class Config:
        namespace = 'acme.dns.authenticator'

    @private
    def cloudflare_txt_record_update(self, domain, challenge, key, cloudflare_email, api_key):
        cf = CloudFlare(cloudflare_email, api_key)
        zone_id = self.find_cloudflare_zone_id(domain)
        record_name = challenge.validation_domain_name(domain)
        record_content = f'"{challenge.validation(key)}"'
        data = {'type': 'TXT', 'name': record_name, 'content': record_content, 'ttl': 3600}

        try:
            self.middleware.logger.debug('Attempting to add record to zone %s: %s', zone_id, data)
            cf.zones.dns_records.post(zone_id, data=data)
        except CloudFlareAPIError as e:
            code = int(e)
            hint = None

            if code == 1009:
                hint = 'Does your API token have "Zone:DNS:Edit" permissions?'

            self.middleware.logger.error('Encountered CloudFlareAPIError adding TXT record: %d %s', e, e)
            raise CallError(
                f'Error communicating with the Cloudflare API: {e}{f"({hint})" if hint else ""}'
            )

        record_id = self.find_txt_record_id(cf, zone_id, record_name, record_content)
        if record_id:
            self.middleware.logger.debug('Successfully added TXT record with record_id: %s', record_id)
        else:
            raise CallError('Unable to find inserted text record via cloudflare API.')

    @private
    def find_cloudflare_zone_id(self, cf, domain):
        zone_name_guesses = dns_common.base_domain_name_guesses(domain)
        zones = []
        code = msg = None

        for zone_name in zone_name_guesses:
            params = {'name': zone_name, 'per_page': 1}

            try:
                zones = cf.zones.get(params=params)
            except CloudFlareAPIError as e:
                code = int(e)
                msg = str(e)
                hint = None

                if code == 6003:
                    hint = 'Did you copy your entire API token/key?'
                elif code == 9103:
                    hint = 'Did you enter the correct email address and Global key?'
                elif code == 9109:
                    hint = 'Did you enter a valid Cloudflare Token?'

                if hint:
                    raise CallError(
                        f'Error determining zone_id: {code} {msg}. Please confirm that you have supplied '
                        f'valid Cloudflare API credentials. ({hint})'
                    )
                else:
                    self.middleware.logger.debug(
                        'Unrecognised CloudFlareAPIError while finding zone_id: %d %s. '
                        'Continuing with next zone guess...', e, e
                    )

            if zones:
                zone_id = zones[0]['id']
                self.middleware.logger.debug('Found zone_id of %s for %s using name %s', zone_id, domain, zone_name)
                return zone_id

        common_msg = f'Unable to determine zone_id for {domain} using zone names: {zone_name_guesses}'
        if msg is not None:
            if 'com.cloudflare.api.account.zone.list' in msg:
                raise CallError(
                    f'{common_msg}. Please confirm that the domain name has been entered correctly '
                    'and your Cloudflare Token has access to the domain.'
                )
            else:
                raise CallError(f'{common_msg}. The error from Cloudflare was: {code} {msg}.')
        else:
            raise CallError(
                f'{common_msg}. Please confirm that the domain name has been entered correctly '
                'and is already associated with the supplied Cloudflare account.'
            )

    @private
    def find_txt_record_id(self, cf, zone_id, record_name, record_content):
        params = {'type': 'TXT', 'name': record_name, 'content': record_content, 'per_page': 1}
        try:
            records = cf.zones.dns_records.get(zone_id, params=params)
        except CloudFlareAPIError as e:
            self.middleware.logger.debug('Encountered CloudFlareAPIError getting TXT record_id: %s', e)
            records = []

        if records:
            # Cleanup is returning the system to the state we found it. If, for some reason,
            # there are multiple matching records, we only delete one because we only added one.
            return records[0]['id']
        self.middleware.logger.debug('Unable to find TXT record.')
