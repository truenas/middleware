from middlewared.schema import accepts, Bool, Dict, Int, List, Patch, returns, Str
from middlewared.service import SystemServiceService, private, ValidationErrors
import middlewared.sqlalchemy as sa


class DynDNSModel(sa.Model):
    __tablename__ = 'services_dynamicdns'

    id = sa.Column(sa.Integer(), primary_key=True)
    ddns_provider = sa.Column(sa.String(120), default='dyndns@3322.org')
    ddns_domain = sa.Column(sa.String(120))
    ddns_username = sa.Column(sa.String(120))
    ddns_password = sa.Column(sa.EncryptedText())
    ddns_checkip_ssl = sa.Column(sa.Boolean())
    ddns_checkip_server = sa.Column(sa.String(150))
    ddns_checkip_path = sa.Column(sa.String(150))
    ddns_ssl = sa.Column(sa.Boolean())
    ddns_custom_ddns_server = sa.Column(sa.String(150))
    ddns_custom_ddns_path = sa.Column(sa.String(150))
    ddns_period = sa.Column(sa.Integer())


class DynDNSService(SystemServiceService):

    class Config:
        service = "dynamicdns"
        datastore_extend = "dyndns.dyndns_extend"
        datastore_prefix = "ddns_"
        cli_namespace = "service.dyndns"

    ENTRY = Dict(
        'dyndns_entry',
        Str('provider', required=True),
        Bool('checkip_ssl', required=True),
        Str('checkip_server', required=True),
        Str('checkip_path', required=True),
        Bool('ssl', required=True),
        Str('custom_ddns_server', required=True),
        Str('custom_ddns_path', required=True),
        List('domain', items=[Str('domain')], required=True),
        Str('username', required=True),
        Str('password', required=True),
        Int('period', required=True),
        Int('id', required=True),
    )

    @private
    async def dyndns_extend(self, dyndns):
        dyndns["domain"] = dyndns["domain"].replace(',', ' ').replace(';', ' ').split()
        return dyndns

    @accepts()
    @returns(Dict('dynamic_dns_provider_choices', additional_attrs=True))
    async def provider_choices(self):
        """
        List supported Dynamic DNS Service Providers.
        """
        return {
            'default@changeip.com': 'changeip.com',
            'default@cloudxns.net': 'cloudxns.net',
            'default@ddnss.de': 'ddnss.de',
            'default@dhis.org': 'dhis.org',
            'default@dnsexit.com': 'dnsexit.com',
            'default@dnsomatic.com': 'dnsomatic.com',
            'default@dnspod.cn': 'dnspod.cn',
            'default@domains.google.com': 'domains.google.com',
            'default@dtdns.com': 'dtdns.com',
            'default@duckdns.org': 'duckdns.org',
            'default@duiadns.net': 'duiadns.net',
            'default@dyndns.org': 'dyndns.org',
            'default@dynsip.org': 'dynsip.org',
            'default@dynv6.com': 'dynv6.com',
            'default@easydns.com': 'easydns.com',
            'default@freedns.afraid.org': 'freedns.afraid.org',
            'default@freemyip.com': 'freemyip.com',
            'default@gira.de': 'gira.de',
            'default@ipv4.dynv6.com': 'ipv4.dynv6.com',
            'default@loopia.com': 'loopia.com',
            'default@no-ip.com': 'no-ip.com',
            'default@ovh.com': 'ovh.com',
            'default@sitelutions.com': 'sitelutions.com',
            'default@spdyn.de': 'spdyn.de',
            'default@strato.com': 'strato.com',
            'default@tunnelbroker.net': 'tunnelbroker.net',
            'default@tzo.com': 'tzo.com',
            'default@zerigo.com': 'zerigo.com',
            'default@zoneedit.com': 'zoneedit.com',
            'dyndns@3322.org': '3322.org',
            'ipv4@nsupdate.info': 'nsupdate.info',
            'dyndns@he.net': 'he.net'
        }

    @private
    async def validate_data(self, data, schema):
        verrors = ValidationErrors()
        provider = data['provider']
        if provider == 'custom':
            for k in ('custom_ddns_server', 'custom_ddns_path'):
                if not data[k]:
                    verrors.add(
                        f'{schema}.{k}',
                        'Required when using a custom provider.'
                    )
        elif provider not in (await self.provider_choices()):
            verrors.add(
                f'{schema}.provider',
                'Please select a valid provider.'
            )

        verrors.check()

    async def do_update(self, data):
        """
        Update dynamic dns service configuration.

        `period` indicates how often the IP is checked in seconds.

        `ssl` if set to true, makes sure that HTTPS is used for the connection to the server which updates the
        DNS record.
        """
        old = await self.config()

        new = old.copy()
        new.update(data)

        await self.validate_data(new, 'dyndns_update')

        new["domain"] = " ".join(new["domain"])

        await self._update_service(old, new)

        await self.dyndns_extend(new)

        return await self.config()
