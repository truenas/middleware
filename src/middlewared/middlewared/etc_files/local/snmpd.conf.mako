<%
    import os
    from middlewared.plugins.snmp_.utils_snmp_user import SNMPSystem
    from middlewared.utils.hardware import HardwareClass, get_hardware_class
    system_user = SNMPSystem.SYSTEM_USER['name']
    uname = os.uname()
    hw_machine = uname.machine
    hw_model = middleware.call_sync("system.cpu_info")["cpu_model"]
    kern_ostype = uname.sysname
    kern_osrelease = uname.release
    kern_osrevision = uname.version
    version = middleware.call_sync('system.version')
    config = middleware.call_sync("snmp.config")
    sys_object_id_suffix = "2" if get_hardware_class() is HardwareClass.TRUENAS_HW else "1"
%>
agentAddress udp:161,udp6:161,unix:/var/run/snmpd.sock
sysLocation ${config["location"] or "unknown"}
sysContact ${config["contact"] or "unknown@localhost"}
sysDescr ${version}. Hardware: ${hw_machine} ${hw_model}. Software: ${kern_ostype} ${kern_osrelease} (revision ${kern_osrevision})
sysObjectID 1.3.6.1.4.1.50536.3.${sys_object_id_suffix}

master agentx

rwuser ${system_user}

% if config["v3"]:
rwuser ${config["v3_username"]}
% else:
rocommunity "${config["community"]}" default
rocommunity6 "${config["community"]}" default
% endif

${config["options"]}
