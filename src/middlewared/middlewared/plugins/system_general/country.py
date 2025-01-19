from middlewared.schema import accepts, Dict, returns
from middlewared.service import Service
from middlewared.utils.country_codes import get_iso_3166_2_country_codes

class SystemGeneralService(Service):

    class Config:
        namespace = 'system.general'
        cli_namespace = 'system.general'

    @accepts()
    @returns(Dict('country_choices', additional_attrs=True, register=True))
    def country_choices(self):
        """Return the ISO 3166-2 representation of countries."""
        return get_iso_3166_2_country_codes()
