<%
    if not middleware.call_sync('iscsi.global.direct_config_enabled'):
        raise FileShouldNotExist()
%>
