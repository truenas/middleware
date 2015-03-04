<%def name="opt(name, val)">\
% if val:
% if type(val) is list:
    ${name} = ${", ".join(val)}
% else:
    ${name} = ${val}
% endif
% endif
</%def>\
\
[Global]
    uam list = uams_dhx.so uams_dhx2.so uams_guest.so
    guest account = ${config.get("services.afp.guest_account")}
    afp listen = 0.0.0.0
    mimic model = RackMac

% for share in dispatcher.call_sync("shares.query", [("type", "=", "afp")]):
[${share["id"]}]
${opt("path", share["target"])}\
${opt("invalid users", share["properties"].get("users-allow"))}\
${opt("hosts allow", share["properties"].get("users-deny"))}\
${opt("hosts deny", share["properties"].get("hosts-allow"))}\
${opt("rolist", share["properties"].get("ro-list"))}\
${opt("rwlist", share["properties"].get("rw-list"))}\
${opt("time machine", share["properties"].get("time-machine", "no"))}\

% endfor