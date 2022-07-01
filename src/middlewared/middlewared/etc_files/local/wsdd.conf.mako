<%
    import json

    enabled = middleware.call_sync('network.configuration.config')['service_announcement']['wsd']
    if enabled:
        hamode = middleware.call_sync('smb.get_smb_ha_mode')
        if hamode == 'CLUSTERED':
            pnn = middleware.call_sync('ctdb.general.pnn')
            recmaster = middleware.call_sync('ctdb.general.recovery_masterr')
            if pnn != recmaster:
                enabled = False

    conf = {
        "realm": middleware.call_sync('smb.getparm', 'realm', 'GLOBAL'),
        "netbios_name": middleware.call_sync('smb.getparm', 'netbios name', 'GLOBAL'),
        "workgroup": middleware.call_sync('smb.getparm', 'workgroup', 'GLOBAL'),
        "enabled": middleware.call_sync('network.configuration.config')['service_announcement']['wsd']
    }
%>
${json.dumps(conf)}
