<%
from middlewared.logger import DEFAULT_SYSLOG_PATH, ALL_LOG_FILES

logger = middleware.logger

# The messages coming in via middleware are already formatted by logger
# and so we don't want to do additional formatting.
syslog_template = 'template("${MESSAGE}\\n")'


def generate_syslog_remote_destination(advanced_config):
    syslog_server = advanced_config["syslogserver"]
    if "]:" in syslog_server or (":" in syslog_server and not "]" in syslog_server): 
        host, port = syslog_server.rsplit(":", 1)
    else:
        host, port = syslog_server, "514"

    host = host.replace("[", "").replace("]", "")
    transport = advanced_config["syslog_transport"].lower()
    cert_id = advanced_config["syslog_tls_certificate"]

    remotelog_stanza = 'destination loghost {\n'
    remotelog_stanza += '  syslog(\n'
    remotelog_stanza += f'    "{host}"\n'
    remotelog_stanza += f'    port({port})\n'
    remotelog_stanza += '    ip-protocol(6)\n'
    remotelog_stanza += f'    transport("{transport}")\n'

    if advanced_config["syslog_transport"] == "TLS":
        # Both mutual and one-way TLS require this
        remotelog_stanza += '    tls(\n'
        remotelog_stanza += '      ca-file("/etc/ssl/certs/ca-certificates.crt")\n'

        if cert_id is not None:
            # Mutual TLS
            certificate = []
            certificate = middleware.call_sync(
                "certificate.query", [["id", "=", cert_id]]
            )
            if certificate is not []:
                remotelog_stanza += f'      key-file(\"{certificate[0]["privatekey_path"]}\")\n'
                remotelog_stanza += f'      cert-file(\"{certificate[0]["certificate_path"]}\")\n'
        remotelog_stanza += '    )\n'

    remotelog_stanza += '  );\n};\n'    
    remotelog_stanza += 'log { source(tn_middleware_src); filter(f_tnremote); destination(loghost); };\n'
    remotelog_stanza += 'log { source(tn_auditd_src); filter(f_tnremote); destination(loghost); };\n'
    remotelog_stanza += 'log { source(s_src); filter(f_tnremote); destination(loghost); };'

    return remotelog_stanza
%>\
@version: 3.38
@include "scl.conf"

##################
# GLOBAL options
##################
options {
  chain_hostnames(off);
  flush_lines(0);
  use_dns(no);
  use_fqdn(${'yes' if render_ctx['system.advanced.config']['fqdn_syslog'] else 'no'});
  dns_cache(no);
  owner("root");
  group("adm");
  perm(0640);
  stats_freq(0);
  bad_hostname("^gconfd$");
};

##################
# DEFAULT SOURCES
##################
source s_src { system(); internal(); };

source tn_middleware_src {
  unix-stream("${DEFAULT_SYSLOG_PATH}" create-dirs(yes) perm(0600));
};

source tn_auditd_src {
  unix-stream("/var/run/syslog-ng/auditd.sock" create-dirs(yes) perm(0600));
};

##################
# filters
##################
@include "/etc/syslog-ng/conf.d/tnfilters.conf"

##################
# destinations
##################
@include "/etc/syslog-ng/conf.d/tndestinations.conf"

## Remote syslog stanza needs to here _before_ the audit-related configuration
% if render_ctx['system.advanced.config']['syslogserver']:
##################
# remote logging
##################
${generate_syslog_remote_destination(render_ctx['system.advanced.config'])}
% endif

##################
# audit-related configuration
##################
@include "/etc/syslog-ng/conf.d/tnaudit.conf"

#######################
# Log paths
########################
log {
  source(s_src);
  filter(f_scst);
  destination { file("/var/log/scst.log"); };
  flags(final);
};

#######################
# Middlewared-related log files
########################
% for tnlog in ALL_LOG_FILES:
log {
  source(tn_middleware_src); filter(f_${tnlog.name or "middleware"});
  destination { file(${tnlog.logfile} ${syslog_template}); };
};
% endfor

log { source(s_src); filter(f_auth); destination(d_auth); };
log { source(s_src); filter(f_cron); destination(d_cron); };
log { source(s_src); filter(f_daemon); destination(d_daemon); };
log { source(s_src); filter(f_kern); destination(d_kern); };
log { source(s_src); filter(f_syslog3); destination(d_syslog); };
log { source(s_src); filter(f_user); destination(d_user); };
log { source(s_src); filter(f_uucp); destination(d_uucp); };
log { source(s_src); filter(f_mail); destination(d_mail); };
log { source(s_src); filter(f_debug); destination(d_debug); };
log { source(s_src); filter(f_error); destination(d_error); };
log { source(s_src); filter(f_messages); destination(d_messages); };
log { source(s_src); filter(f_console); destination(d_console_all); destination(d_xconsole); };
log { source(s_src); filter(f_crit); destination(d_console); };
