from middlewared.service import private, Service


ref_mapping = {
    'definitions/interface': 'interface'
}


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @private
    async def get_normalised_values(self, item_details, values):
        pass
