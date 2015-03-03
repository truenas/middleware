[Global]
    uam list = uams_dhx.so uams_dhx2.so uams_guest.so
    guest account = ${config.get("services.afp.guest_account")}
    afp listen =
    mimic model = RackMac

% for share in dispatcher.call_sync("shares.query", [("type", "=", "afp")]):
[${share["id'"]}]
    path = ${share["target"]}
    % if share["properties"].get("allow"):
    valid users = ${", ".join(share["properties"]["allow"])}
    % endif
    % if share["properties"].get("deny"):
    invalid users = ${", ".join(share["properties"]["allow"])}
    % endif
    ttime machine = ${share["properties"].get("time-machine", "no")}

% endfor