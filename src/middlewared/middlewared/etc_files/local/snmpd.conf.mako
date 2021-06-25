<%
    if IS_FREEBSD:
        import sysctl

        hw_machine = sysctl.filter("hw.machine")[0].value
        hw_model = f'{sysctl.filter("hw.model")[0].value} running at {sysctl.filter("hw.clockrate")[0].value} MHz'
        kern_ostype = sysctl.filter("kern.ostype")[0].value
        kern_osrelease = sysctl.filter("kern.osrelease")[0].value
        kern_osrevision = sysctl.filter("kern.osrevision")[0].value
    else:
        import os

        uname = os.uname()

        hw_machine = uname.machine
        hw_model = middleware.call_sync("system.cpu_info")["cpu_model"]
        kern_ostype = uname.sysname
        kern_osrelease = uname.release
        kern_osrevision = uname.version

    with open("/etc/version") as f:
        freenas_version = f.read().strip()

    config = middleware.call_sync("snmp.config")
%>
agentAddress udp:161,udp6:161,unix:/var/run/snmpd.sock
sysLocation ${config["location"] or "unknown"}
sysContact ${config["contact"] or "unknown@localhost"}
sysDescr ${freenas_version}. Hardware: ${hw_machine} ${hw_model}. Software: ${kern_ostype} ${kern_osrelease} (revision ${kern_osrevision})
sysObjectID 1.3.6.1.4.1.50536.3.${"1" if not middleware.call_sync("system.is_enterprise") else "2"}

master agentx

% if config["v3"]:
    % if config["v3_username"] and config["v3_password"]:
createUser ${config["v3_username"]} ${config["v3_authtype"]} "${config["v3_password"]}" \
        % if config["v3_privproto"] and config["v3_privpassphrase"]:
${config["v3_privproto"]} "${config["v3_privpassphrase"]}"
        % else:

        % endif

rwuser ${config["v3_username"]}
    % endif
% else:
rocommunity "${config["community"]}" default
rocommunity6 "${config["community"]}" default
% endif

${config["options"]}
