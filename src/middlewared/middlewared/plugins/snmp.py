from middlewared.schema import Bool, Dict, Int, Str
from middlewared.validators import Email, Match, Or, Range
from middlewared.service import SystemServiceService, ValidationErrors
import middlewared.sqlalchemy as sa


class SNMPModel(sa.Model):
    __tablename__ = 'services_snmp'

    id = sa.Column(sa.Integer(), primary_key=True)
    snmp_location = sa.Column(sa.String(255))
    snmp_contact = sa.Column(sa.String(120))
    snmp_traps = sa.Column(sa.Boolean(), default=False)
    snmp_v3 = sa.Column(sa.Boolean(), default=False)
    snmp_community = sa.Column(sa.String(120), default='public')
    snmp_v3_username = sa.Column(sa.String(20))
    snmp_v3_authtype = sa.Column(sa.String(3), default='SHA')
    snmp_v3_password = sa.Column(sa.EncryptedText())
    snmp_v3_privproto = sa.Column(sa.String(3), nullable=True)
    snmp_v3_privpassphrase = sa.Column(sa.EncryptedText(), nullable=True)
    snmp_options = sa.Column(sa.Text())
    snmp_loglevel = sa.Column(sa.Integer(), default=3)
    snmp_zilstat = sa.Column(sa.Boolean(), default=False)
    snmp_iftop = sa.Column(sa.Boolean(), default=False)


class SNMPService(SystemServiceService):

    class Config:
        service = 'snmp'
        datastore_prefix = 'snmp_'
        cli_namespace = 'service.snmp'

    ENTRY = Dict(
        'snmp_entry',
        Str('location', required=True),
        Str('contact', required=True, validators=[Or(Email(), Match(r'^[-_a-zA-Z0-9\s]*$'))]),
        Bool('traps', required=True),
        Bool('v3', required=True),
        Str('community', validators=[Match(r'^[-_.a-zA-Z0-9\s]*$')], default='public', required=True),
        Str('v3_username', max_length=20, required=True),
        Str('v3_authtype', enum=['', 'MD5', 'SHA'], required=True),
        Str('v3_password', required=True),
        Str('v3_privproto', enum=[None, 'AES', 'DES'], null=True, required=True),
        Str('v3_privpassphrase', required=True, null=True),
        Int('loglevel', validators=[Range(min=0, max=7)], required=True),
        Str('options', max_length=None, required=True),
        Bool('zilstat', required=True),
        Bool('iftop', required=True),
        Int('id', required=True),
    )

    async def do_update(self, data):
        """
        Update SNMP Service Configuration.

        `v3` when set enables SNMP version 3.

        `v3_username`, `v3_authtype`, `v3_password`, `v3_privproto` and `v3_privpassphrase` are only used when `v3`
        is enabled.
        """
        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        if not new['v3'] and not new['community']:
            verrors.add('snmp_update.community', 'This field is required when SNMPv3 is disabled')

        if new['v3_authtype'] and not new['v3_password']:
            verrors.add(
                'snmp_update.v3_password',
                'This field is requires when SNMPv3 auth type is specified',
            )

        if new['v3_password'] and len(new['v3_password']) < 8:
            verrors.add('snmp_update.v3_password', 'Password must contain at least 8 characters')

        if new['v3_privproto'] and not new['v3_privpassphrase']:
            verrors.add(
                'snmp_update.v3_privpassphrase',
                'This field is requires when SNMPv3 private protocol is specified',
            )

        if verrors:
            raise verrors

        await self._update_service(old, new)

        return await self.config()
