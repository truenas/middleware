from middlewared.schema import accepts, Dict, returns
from middlewared.service import Service
from middlewared.utils.country_codes import get_country_codes

class SystemGeneralService(Service):

    class Config:
        namespace = 'system.general'
        cli_namespace = 'system.general'

    @accepts()
    @returns(Dict('country_choices', additional_attrs=True, register=True))
    def country_choices(self):
        """Return a dictionary whose keys represent the
        ISO 3166-1 alpha 2 country code and values represent
        the English short name (used in ISO 3166/MA)"""
        return get_country_codes()
