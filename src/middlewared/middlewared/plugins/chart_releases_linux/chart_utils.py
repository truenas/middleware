from middlewared.service import private, Service


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @private
    async def get_latest_version_from_item_versions(self, item_versions):
        return sorted(item_versions or ['latest'], reverse=True)[0]
