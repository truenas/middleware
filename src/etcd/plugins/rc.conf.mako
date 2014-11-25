hostname="${config.get("system.hostname")}"
local_startup="/etc/ix.rc.d /usr/local/etc/rc.d"
root_rw_mount="YES"
clear_tmpX="NO"
background_fsck="NO"
fsck_y_enable="YES"
synchronous_dhclient="YES"

# middleware10
datastore_dbdir="/data"
datastore_driver="mongodb"
etcd_flags="/etc"

# turbo boost
performance_cpu_freq="HIGH"

% if config.get("network.autoconfiguration", True):
% for iface in dispatcher.call_sync("system.device.get_devices", "network"):
ifconfig_${iface["name"]}="DHCP"
% endfor
% else:
% for name, iface in config.children_dict("network.interface").items():
ifconfig_${name}=""
% endfor
% endif
% for svc in ds.query("service_definitions"):
% if config.get("service.{0}.enable".format(svc['name'])):
${svc['service-name']}_enable="YES"
% endif
% endfor