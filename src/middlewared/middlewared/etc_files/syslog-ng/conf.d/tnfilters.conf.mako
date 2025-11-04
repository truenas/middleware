<%
    from middlewared.plugins.audit.utils import audit_program, AUDITED_SERVICES
    from middlewared.logger import ALL_LOG_FILES

    adv_conf = render_ctx['system.advanced.config']

    audit_filters = [f'filter(f_tnaudit_{svc.lower()});' for svc, vers in AUDITED_SERVICES]

    nfs_conf = render_ctx['nfs.config']
%>\
##################
# TrueNAS filters
##################

# Filter TrueNAS audit-related messages
% for svc, vers in AUDITED_SERVICES:
filter f_tnaudit_${svc.lower()} { program("${audit_program(svc)}") };
% endfor
filter f_tnaudit_all {
  ${' or\n  '.join(audit_filters)}
};

# These filters are used for remote syslog
filter f_tnremote_f_emerg { level(emerg); };
filter f_tnremote_f_alert { level(alert..emerg); };
filter f_tnremote_f_crit { level(crit..emerg); };
filter f_tnremote_f_err { level(err..emerg); };
filter f_tnremote_f_warning { level(warning..emerg); };
filter f_tnremote_f_notice { level(notice..emerg); };
filter f_tnremote_f_info { level(info..emerg); };
filter f_tnremote_f_is_info { level(info); };
filter f_tnremote_f_debug { level(debug..emerg); };

filter f_tnremote {
    filter(f_tnremote_${adv_conf["sysloglevel"].lower()})
## syslog_audit is associated with remote logging only
% if not adv_conf['syslog_audit']:
    and not filter(f_tnaudit_all)
% endif
};

# These filters are used for applications that have
# special logging behavior
filter f_nfs_mountd {
  program("rpc.mountd") and level(debug..notice);
};
filter f_scst {
  program("iscsi-scstd") or
  program("scst") or
  program("dlm") or
  program("kernel") and match("scst:" value("MESSAGE")); or
  program("kernel") and match("iscsi-scst:" value("MESSAGE")); or
  program("kernel") and match("dev_vdisk:" value("MESSAGE")); or
  program("kernel") and match("dev_disk:" value("MESSAGE")); or
  program("kernel") and match("dlm:" value("MESSAGE"));
};

# TrueNAS middleware filters
% for tnlog in ALL_LOG_FILES:
filter f_${tnlog.name or "middleware"} { program("${tnlog.get_ident()[:-2]}"); };
% endfor

# Temporary SNMP filter: NAS-129124
filter f_snmp {
  program("snmpd") and match("unexpected header length" value("MESSAGE"));
};

filter f_truenas_exclude {
% if not nfs_conf['mountd_log']:
  not filter(f_nfs_mountd) and
% endif
  not filter(f_tnaudit_all) and
  not filter(f_scst) and
  # Temporary SNMP filter: NAS-129124
  not filter(f_snmp)
};

#####################
# filters - these are default Debian filters with some minor alterations
#####################
filter f_dbg { level(debug); };
filter f_info { level(info); };
filter f_notice { level(notice); };
filter f_warn { level(warn); };
filter f_err { level(err); };
filter f_crit { level(crit .. emerg); };

filter f_debug {
  level(debug) and not facility(auth, authpriv, news, mail);
};

filter f_error { level(err .. emerg) ; };

filter f_messages {
  filter(f_truenas_exclude) and
  level(info,notice,warn) and
  not facility(auth,authpriv,cron,daemon,mail,news);
};

filter f_auth {
  facility(auth, authpriv) and not filter(f_dbg);
};

filter f_cron {
  facility(cron) and not filter(f_dbg);
};

filter f_daemon {
  facility(daemon) and 
% if not nfs_conf['mountd_log']:
  not filter(f_nfs_mountd) and
% endif
  not filter(f_dbg);
};

filter f_kern {
  facility(kern) and not filter(f_dbg) and not filter(f_scst);
};


filter f_local {
  facility(local0, local1, local3, local4, local5, local6, local7) and not filter(f_dbg);
};

filter f_mail {
  facility(mail) and not filter(f_dbg);
};

filter f_syslog3 {
  filter(f_truenas_exclude) and
  not facility(auth, authpriv, mail) and
  not filter(f_dbg);
};

filter f_user {
  facility(user) and not filter(f_dbg);
};

filter f_uucp {
  facility(uucp) and not filter(f_dbg);
};

filter f_cother {
  level(debug, info, notice, warn) or facility(daemon, mail);
};

filter f_ppp {
  facility(local2) and not filter(f_dbg);
};

filter f_console { filter(f_truenas_exclude) and level(warn .. emerg); };
