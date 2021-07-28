<%
    import json

    conf = {
        "realm": middleware.call_sync('smb.getparm', 'realm', 'GLOBAL'),
        "netbios_name": middleware.call_sync('smb.getparm', 'netbiosname', 'GLOBAL'),
        "workgroup": middleware.call_sync('smb.getparm', 'workgroup', 'GLOBAL'),
        "enabled": middleware.call_sync('network.configuration.config')['service_announcement']['wsd']
    }
%>
${json.dumps(conf)}
