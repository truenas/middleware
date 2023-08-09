##################
# TrueNAS filters
##################

# Filter TrueNAS audit-related messages
filter f_tnaudit_smb { program("TNAUDIT_SMB"); };
filter f_tnaudit_all {
  filter(f_tnaudit_smb)
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

# These filters are used for applications that have
# special logging behavior
filter f_k3s { program("k3s"); };
filter f_containerd { program("containerd") or program("dockerd") };
filter f_kube_router { program("kube-router"); };
filter f_app_mounts {
  program("systemd") and match("mount:" value("MESSAGE")) and match("docker" value("MESSAGE")); or
  program("systemd") and match("mount:" value("MESSAGE")) and match("kubelet" value("MESSAGE"));
};

filter f_truenas_exclude {
  not filter(f_tnaudit_all) and
  not filter(f_k3s) and
  not filter(f_containerd) and
  not filter(f_kube_router) and
  not filter(f_app_mounts)
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
  facility(daemon) and not filter(f_dbg);
};

filter f_kern {
  facility(kern) and not filter(f_dbg);
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
