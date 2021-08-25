<%
    systemdatasetconfig = middleware.call_sync('systemdataset.config')
    path = f'{systemdatasetconfig["path"]}/syslog-{systemdatasetconfig["uuid"]}'
%>
# If a variable is not set here, then the corresponding
# parameter will not be changed.
# If a variables is set, then every invocation of
# syslog-ng's init script will set them using dmesg.

# log level of messages which should go to console
# see syslog(3) for details
#
#CONSOLE_LOG_LEVEL=1

# Command line options to syslog-ng
SYSLOGNG_OPTS="--persist-file ${path}/syslog-ng.persist"
