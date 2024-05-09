from middlewared.plugins.etc import FileShouldNotExist
from middlewared.utils import mdns

"""
Device Info:
-------------------------
The TXTRecord string here determines the icon that will be displayed in Finder on MacOS
clients. Default is to use MacRack which will display the icon for a rackmounted server.
"""


def render(service, middleware, render_ctx):

    try:
        return mdns.generate_avahi_srv_record(
            'DEV_INFO', txt_records=[f'model={mdns.DevType.MACPRORACK}']
        )
    except Exception:
        middleware.logger.error(
            'Failed to generate mDNS SRV record for the DEV_INFO service',
            exc_info=True
        )

    raise FileShouldNotExist()
