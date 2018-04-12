from middlewared.schema import accepts, Bool, Dict, Int, Str
from middlewared.validators import Email, Match, Or, Range
from middlewared.service import SystemServiceService, ValidationErrors


class SNMPService(SystemServiceService):

    class Config:
        service = "snmp"
        datastore_prefix = "snmp_"

    @accepts(Dict(
        'snmp_update',
        Str('location'),
        Str('contact', validators=[Or(Email(), Match(r'^[-_a-zA-Z0-9\s]+$'))]),
        Bool('traps'),
        Bool('v3', default=False),
        Str('community', validators=[Match(r'^[-_.a-zA-Z0-9\s]*$')]),
        Str('v3_username'),
        Str('v3_authtype', enum=['', 'MD5', 'SHA']),
        Str('v3_password'),
        Str('v3_privproto', enum=[None, 'AES', 'DES']),
        Str('v3_privpassphrase'),
        Int('loglevel', validators=[Range(min=0, max=7)]),
        Str('options'),
    ))
    async def do_update(self, data):
        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        if not data["v3"] and not data["community"]:
            verrors.add("snmp_update.community", "This field is required when SNMPv3 is disabled")

        if data["v3_authtype"] and not data["v3_password"]:
            verrors.add("snmp_update.v3_password", "This field is requires when SNMPv3 auth type is specified")

        if data["v3_password"] and len(data["v3_password"]) < 8:
            verrors.add("snmp_update.v3_password", "Password must contain at least 8 characters")

        if data["v3_privproto"] and not data["v3_privpassphrase"]:
            verrors.add("snmp_update.v3_privpassphrase", "This field is requires when SNMPv3 private protocol is specified")

        if verrors:
            raise verrors

        await self._update_service(old, new)

        return new
