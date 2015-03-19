hostname="${config.get("system.hostname")}"
local_startup="/etc/ix.rc.d /usr/local/etc/rc.d"
root_rw_mount="YES"
clear_tmpX="NO"
background_fsck="NO"
fsck_y_enable="YES"
synchronous_dhclient="YES"

# middleware10
dispatcher_flags="--log-level=DEBUG"
datastore_dbdir="/data"
datastore_driver="mongodb"
etcd_flags="/etc"
#Disabling syslogd
syslogd_enable="NO"
# turbo boost
performance_cpu_freq="HIGH"

% for svc in ds.query("service_definitions"):
    % if config.get("service.{0}.enable".format(svc["name"])):
        ${svc['rcng']['rc-scripts']}_enable="YES"
    % endif
% endfor
