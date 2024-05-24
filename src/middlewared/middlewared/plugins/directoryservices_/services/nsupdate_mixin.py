import dns
import ipaddress

from middlewared.service_exception import CallError
from typing import Optional


class NsupdateMixin:
    """
    Base directory services class. This provides common status-related code
    for directory
    """

    def _get_fqdn(self) -> str:
        """ Retrieve server hostname for DNS register / unregister """
        ngc = self.call_sync('network.configuration.config')
        return f'{ngc["hostname"]}.{ngc["domain"]}.'

    def _get_current_ips(self) -> set:
        """
        This method is used to restrict the list of IP addresses to register
        in via nsupdate.
        """

        return set(list(self.call_sync('smb.bindip_choices').keys()))

    def _get_ip_updates(self, fqdn: str, force: Optional[bool] = False) -> list:
        """ Retrieve list of IPs to register in DNS """
        validated_ips = set()
        to_remove_ips = set()

        to_check = self._get_current_ips()

        for ip in to_check:
            try:
                result = self.call_sync('dnsclient.reverse_lookup', {
                    'addresses': [ip]
                })
            except dns.resolver.NXDOMAIN:
                # Reverse entry doesn't exist and so we're safe
                validated_ips.add(ip)
                continue

            except dns.resolver.LifetimeTimeout:
                # Exceeding lifetime timeout may often mean that administrator has
                # not configured a reverse zone. This may lead to semi-broken kerberos
                # environment.
                self.logger.warning(
                    '%s: DNS operation timed out while trying to resolve reverse pointer '
                    'for IP address.',
                    ip
                )

            except dns.resolver.NoNameservers:
                self.logger.warning(
                    'No nameservers configured to handle reverse pointer for %s. '
                    'Omitting from list of addresses to register.',
                    ip
                )
                continue

            except Exception:
                # DNS for this IP may be simply wildly misconfigured and time out
                self.logger.warning(
                    'Reverse lookup of %s failed, omitting from list '
                    'of addresses to use for Active Directory purposes.',
                    ip, exc_info=True
                )
                continue

            else:
                if result[0]['target'].casefold() != fqdn.casefold():
                    self.logger.warning(
                        'Reverse lookup of %s points to %s, expected %s',
                        ip, result[0]['target'], fqdn
                    )
                    if not force:
                        continue

                validated_ips.add(ip)

        if force:
            try:
                current_addresses = set([
                    x['address'] for x in
                    self.call_sync('dnsclient.forward_lookup', {
                       'names': [fqdn]
                    })
                ])
            except dns.resolver.NXDOMAIN:
                current_addresses = set()

            to_remove_ips = current_addresses - validated_ips

        return {
            'to_add': validated_ips,
            'to_remove': to_remove_ips,
        }

    def register_dns(
        self,
        force: Optional[bool] = False
    ) -> None:
        """
        Use existing kerberos ticket to register our server
        in DNS for the domain via `nsupdate` + TSIG.
        """
        if not self._has_dns_update:
            raise NotImplementedError

        self._assert_is_active()

        config = self.config
        if not config['allow_dns_updates']:
            # DNS updates have been disabled
            return

        fqdn = self._get_fqdn()
        if force:
            self.unregister_dns(force)

        payload = []
        ip_updates = self._get_ip_updates(fqdn, force)
        for ip in ip_updates['to_remove']:
            addr = ipaddress.ip_address(ip)
            payload.append({
                'command': 'DELETE',
                'name': fqdn,
                'address': str(addr),
                'type': 'A' if addr.version == 4 else 'AAAA'
            })

        for ip in ip_updates['to_add']:
            addr = ipaddress.ip_address(ip)
            payload.append({
                'command': 'ADD',
                'name': fqdn,
                'address': str(addr),
                'type': 'A' if addr.version == 4 else 'AAAA'
            })

        try:
            self.call_sync('dns.nsupdate', {'ops': payload})
        except CallError as e:
            self.logger.warning(
                'Failed to update DNS with payload [%s]: %s',
                payload, e.errmsg
            )
            return None

        return payload

    def unregister_dns(self, force: Optional[bool] = False) -> None:
        """
        Use existing kerberos ticket to remove our DNS entries.
        This is performed as part of leaving a domain (IPA or AD).
        """
        if not self._has_dns_update:
            raise NotImplementedError

        self._assert_is_active()

        config = self.config
        if not config['allow_dns_updates']:
            # DNS updates have been disabled
            return

        fqdn = self._get_fqdn()
        try:
            dns_addresses = set([x['address'] for x in self.call_sync('dnsclient.forward_lookup', {
                'names': [fqdn]
            })])
        except dns.resolver.NXDOMAIN:
            self.logger.warning(
                f'DNS lookup of {fqdn}. failed with NXDOMAIN. '
                'This may indicate that DNS entries for the TrueNAS server have '
                'already been deleted; however, it may also indicate the '
                'presence of larger underlying DNS configuration issues.'
            )
            return

        ips_in_use = set([x['address'] for x in self.call_sync('interface.ip_in_use')])
        if not dns_addresses & ips_in_use:
            # raise a CallError here because we don't want someone fat-fingering
            # input and removing an unrelated computer in the domain.
            raise CallError(
                f'DNS records indicate that {fqdn} may be associated '
                'with a different computer in the domain. Forward lookup returned the '
                f'following results: {", ".join(dns_addresses)}.'
            )

        payload = []

        for ip in dns_addresses:
            addr = ipaddress.ip_address(ip)
            payload.append({
                'command': 'DELETE',
                'name': fqdn,
                'address': str(addr),
                'type': 'A' if addr.version == 4 else 'AAAA'
            })

        try:
            self.call_sync('dns.nsupdate', {'ops': payload})
        except CallError as e:
            self.logger.warning(
                'Failed to update DNS with payload [%s]: %s',
                payload, e.err_msg
            )
