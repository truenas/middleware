<%
    global_config = render_ctx['iscsi.global.config']
%>\
ISCSID_OPTIONS="-p ${global_config['listen_port']}"
