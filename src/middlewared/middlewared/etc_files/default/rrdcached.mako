<%
    import os

    if not middleware.call_sync('reporting.setup'):
        # Let's exit this if setup related disk operations fail
        middleware.logger.error('Rrdcached configuration file could not be generated')
        raise FileShouldNotExist()

    systemdatasetconfig = middleware.call_sync('systemdataset.config')
    if not systemdatasetconfig['path']:
        middleware.logger.error('rrdcached: system dataset is not properly configured. '
                                'Disabling journaling.')
        journal_path = None
    else:
        rrd_mount = f'{systemdatasetconfig["path"]}/rrd-{systemdatasetconfig["uuid"]}'
        journal_path = f'{rrd_mount}/journal'
        os.makedirs(journal_path, exist_ok=True)

%>
# Full path to daemon
DAEMON=/usr/bin/rrdcached

# Where journal files are placed.  If left unset, journaling will
# be disabled.
% if journal_path:
JOURNAL_PATH=${journal_path}/
% else:
# WARNING: SYSTEM DATASET IS UNAVAILABLE. JOURNALING DISABLED.
#JOURNAL_PATH=
% endif

# FHS standard placement for process ID file.
PIDFILE=/var/run/rrdcached.pid

# FHS standard placement for local control socket.
SOCKFILE=/var/run/rrdcached.sock
