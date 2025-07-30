from middlewared.plugins.etc import FileShouldNotExist
from middlewared.utils import mdns

"""
Time Machine (adisk):
-------------------------
sys=adVF=0x100 -- this is required when _adisk._tcp is present on device. When it is
set, the MacOS client will send a NetShareEnumAll IOCTL and shares will be visible.
Otherwise, Finder will only see the Time Machine share. In the absence of _adisk._tcp
MacOS will _always_ send NetShareEnumAll IOCTL.

waMa=0 -- MacOS server uses waMa=0, while embedded devices have it set to their Mac Address.
Speculation in Samba-Technical indicates that this stands for "Wireless ADisk Mac Address".

adVU -- ADisk Volume UUID.

dk(n)=adVF=
0xa1, 0x81 - AFP support
0xa2, 0x82 - SMB support
0xa3, 0x83 - AFP and SMB support

adVN -- AirDisk Volume Name. We set this to the share name.
network analysis indicates that current MacOS Time Machine shares set the port for adisk to 311.
"""


def render(service, middleware, render_ctx):

    conf = render_ctx['smb.config']
    if not render_ctx['service.started_or_enabled']:
        raise FileShouldNotExist()

    shares = middleware.call_sync('sharing.smb.query', [
        ['OR', [['purpose', '=', 'TIMEMACHINE_SHARE'], ['options.timemachine', '=', True]]],
        ['enabled', '=', True], ['locked', '=', False]
    ])

    if not shares:
        raise FileShouldNotExist()

    if conf['bindip']:
        iindexes = mdns.ip_addresses_to_interface_indexes(
            render_ctx['interface.query'], conf['bindip']
        )
    else:
        iindexes = None

    txt_records = ['sys=waMa=0,adVF=0x100']

    for dkno, share in enumerate(shares):
        txt_records.append(
            f'dk{dkno}=adVN={share["name"]},adVF=0x82,adVU={share["options"]["vuid"]}'
        )

    try:
        return mdns.generate_avahi_srv_record('ADISK', iindexes, txt_records=txt_records)
    except Exception:
        middleware.logger.error(
            'Failed to generate mDNS SRV record for the ADISK service',
            exc_info=True
        )

    raise FileShouldNotExist()
