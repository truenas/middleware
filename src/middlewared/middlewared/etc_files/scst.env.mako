<%
    global_config = middleware.call_sync('iscsi.global.config')
%>\
ISCSID_OPTIONS="-p ${global_config['listen_port']}}"
