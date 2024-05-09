from middlewared.plugins.etc import FileShouldNotExist
from middlewared.utils import filter_list
from middlewared.utils import mdns


def render(service, middleware, render_ctx):

    conf = render_ctx['smb.config']
    if not render_ctx['service.started_or_enabled']:
        raise FileShouldNotExist()

    shares = middleware.call_sync('sharing.smb.query', [
        ['OR', [['purpose', 'in', ['TIMEMACHINE', 'ENHANCED_TIMEMACHINE']], ['timemachine', '=', True]]],
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
            f'dk{dkno}=adVN={share["name"]},adVF=0x82,adVU={share["vuid"]}'
        )

    try:
        return mdns.generate_avahi_srv_record('ADISK', iindexes, txt_records=txt_records)
    except Exception:
        middleware.logger.error(
            'Failed to generate mDNS SRV record for the HTTP service',
            exc_info=True
        )

    raise FileShouldNotExist()
