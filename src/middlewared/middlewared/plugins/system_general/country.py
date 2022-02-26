import csv

from middlewared.schema import accepts, Dict, returns
from middlewared.service import private, Service


class SystemGeneralService(Service):

    COUNTRY_CHOICES = None

    class Config:
        namespace = 'system.general'
        cli_namespace = 'system.general'

    @accepts()
    @returns(Dict('country_choices', additional_attrs=True, register=True))
    async def country_choices(self):
        """
        Returns country choices.
        """
        if not self.COUNTRY_CHOICES:
            self.COUNTRY_CHOICES = await self.middleware.call('system.general.get_country_choices')

        return self.COUNTRY_CHOICES

    @private
    def get_country_choices(self):
        def _get_index(country_columns, column):
            index = -1
            i = 0
            for c in country_columns:
                if c.lower() == column.lower():
                    index = i
                    break

                i += 1
            return index

        country_file = '/etc/iso_3166_2_countries.csv'
        cni, two_li = None, None
        country_choices = {}
        with open(country_file, 'r', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)

            for index, row in enumerate(reader):
                if index != 0:
                    if row[cni] and row[two_li]:
                        if row[two_li] in country_choices:
                            # If two countries in the iso file have the same key, we concatenate their names
                            country_choices[row[two_li]] += f' + {row[cni]}'
                        else:
                            country_choices[row[two_li]] = row[cni]
                else:
                    # ONLY CNI AND TWO_LI ARE BEING CONSIDERED FROM THE CSV
                    cni = _get_index(row, 'Common Name')
                    two_li = _get_index(row, 'ISO 3166-1 2 Letter Code')

        return country_choices
