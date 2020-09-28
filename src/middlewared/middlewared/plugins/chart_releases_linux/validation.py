import copy

from middlewared.service import private, Service


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @private
    async def validate_values(self, item_version_details, values):
        default_values = item_version_details['values']
        new_values = copy.deepcopy(default_values)
        new_values.update(values)

