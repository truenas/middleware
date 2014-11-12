<%doc>
hostname=""
% if config.get("network.autoconfiguration", True):
    % for iface in dispatcher.call_sync("system.device.get_devices", "network"):
        ifconfig_${iface["name"]}="DHCP"
    % endfor
% else:
    % for name, iface in config.children_dict("network.interface"):
        ifconfig_${name}=""
    % endfor
% endif
% for name, svc in config.children_dict("service"):
    % if svc["enabled"]:
        ${name}_enable="YES"
    % endif
    % if svc["flags"]:
        ${name}_flags="${svc["flags"]}
    % endif
% endfor
</%doc>