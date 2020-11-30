<%
    from middlewared.plugins.smb import SMBHAMODE

    clustered = SMBHAMODE[middleware.call_sync('smb.get_smb_ha_mode')] == SMBHAMODE.CLUSTERED
    if not clustered:
        return

    data = middleware.call_sync('ctdb.public.ips.query')
    if not data:
        raise FileShouldNotExist()

%>\
% for i in data:
${i['ip']}/${i['netmask']} ${i['interface']}
% endfor
