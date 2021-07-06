import errno

from pkg_resources import parse_version

from middlewared.service import CallError, private, Service


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @private
    async def get_latest_version_from_item_versions(self, item_versions):
        if not item_versions:
            raise CallError('No versions found', errno=errno.ENOENT)
        elif all(not item_version['healthy'] for item_version in item_versions.values()):
            raise CallError('No healthy item version found', errno=errno.ENOENT)

        return str(sorted(map(parse_version, item_versions) or ['latest'], reverse=True)[0])
