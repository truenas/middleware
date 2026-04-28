from truenas_pymdns.server.config import ServiceConfig, generate_service_config

from middlewared.plugins.etc import FileShouldNotExist
from middlewared.utils.mdns import ip_addresses_to_interface_names

# Time Machine (adisk) TXT records:
#   sys=adVF=0x100   -- required when _adisk._tcp is advertised; without it
#                       the macOS client only sees the Time Machine share.
#   waMa=0           -- "Wireless ADisk Mac Address"; macOS servers use 0.
#   dk<n>=adVN=<share-name>,adVF=0x82,adVU=<share-uuid>
#     adVF values: 0xa1/0x81 = AFP, 0xa2/0x82 = SMB, 0xa3/0x83 = both.
# Current macOS advertises adisk on port 311; we don't bind to a listening
# port here (_adisk._tcp is a discovery record, not a connect target), so
# port 9 (discard) is used as a placeholder.


def render(service, middleware, render_ctx):
    if render_ctx['failover.status'] not in ('SINGLE', 'MASTER'):
        raise FileShouldNotExist()

    if not render_ctx['service.started_or_enabled']:
        raise FileShouldNotExist()

    shares = middleware.call_sync('sharing.smb.query', [
        ['OR', [['purpose', '=', 'TIMEMACHINE_SHARE'], ['options.timemachine', '=', True]]],
        ['enabled', '=', True], ['locked', '=', False],
    ])
    if not shares:
        raise FileShouldNotExist()

    smb_config = render_ctx['smb.config']
    interfaces: list[str] = []
    if smb_config['bindip']:
        interfaces = ip_addresses_to_interface_names(
            render_ctx['interface.query'], smb_config['bindip'],
        )

    txt = {'sys': 'waMa=0,adVF=0x100'}
    for dkno, share in enumerate(shares):
        txt[f'dk{dkno}'] = (
            f'adVN={share["name"]},adVF=0x82,adVU={share["options"]["vuid"]}'
        )

    try:
        cfg = ServiceConfig(
            service_type='_adisk._tcp',
            port=9,
            interfaces=interfaces,
            txt=txt,
        )
        return generate_service_config(cfg)
    except Exception:
        middleware.logger.error(
            'Failed to generate ADISK discovery service config',
            exc_info=True,
        )
        raise FileShouldNotExist()
