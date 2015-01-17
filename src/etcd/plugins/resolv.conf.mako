# WARNING: This file is auto-generated on every open. Don't bother trying to edit it.
% for address in config.get("network.dns.addresses"):
nameserver ${address}
% endfor
% for name in config.get("network.dns.search"):
search ${name}
% endfor