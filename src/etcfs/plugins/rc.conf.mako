hostname=""
% for name, iface in ${config.children_dict("network.interface.*")}:
ifconfig_${name}=""
% endfor
% for name, svc in ${config.children_dict("service.*")}:
% if svc.enabled:
${name}_enable="YES"
% endif
% endfor