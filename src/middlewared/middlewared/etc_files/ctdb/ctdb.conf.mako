<%
    from middlewared.utils import ctdb
    if not render_ctx['failover.licensed']:
        raise FileShouldNotExist
%>

[logging]

	location = syslog:nonblocking
	log level = NOTICE


[cluster]

	recovery lock = !${ctdb.RECLOCK_HELPER_SCRIPT}


[database]

	volatile database directory = ${ctdb.VOLATILE_DB}
	persistent database directory = ${ctdb.PERSISTENT_DB}
	state database directory = ${ctdb.STATE_DB}
