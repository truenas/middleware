from middlewared.schema import Bool, Dict, Str, accepts, ValidationErrors
from middlewared.service import SystemServiceService
import middlewared.sqlalchemy as sa


class LLDPModel(sa.Model):
    __tablename__ = 'services_lldp'

    id = sa.Column(sa.Integer(), primary_key=True)
    lldp_intdesc = sa.Column(sa.Boolean(), default=True)
    lldp_country = sa.Column(sa.String(2))
    lldp_location = sa.Column(sa.String(200))


class LLDPService(SystemServiceService):
    class Config:
        service = 'lldp'
        datastore_prefix = 'lldp_'
        cli_namespace = 'service.lldp'

    @accepts()
    async def country_choices(self):
        """
        Returns country choices for LLDP.
        """
        return await self.middleware.call('system.general.country_choices')

    @accepts(Dict(
        'lldp_update',
        Bool('intdesc'),
        Str('country', max_length=2),
        Str('location'),
        update=True
    ))
    async def do_update(self, data):
        """
        Update LLDP Service Configuration.

        `country` is a two letter ISO 3166 country code required for LLDP location support.

        `location` is an optional attribute specifying the physical location of the host.
        """
        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()
        if new['country'] not in await self.country_choices():
            verrors.add('lldp_update.country', f'{new["country"]} not in countries recognized by the system.')
        verrors.check()

        await self._update_service(old, new)

        return new
