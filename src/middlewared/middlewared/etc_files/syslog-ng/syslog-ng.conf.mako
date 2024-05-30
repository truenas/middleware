<%
logger = middleware.logger

def generate_syslog_remote_destination(advanced_config):
    result = ""
    syslog_server = advanced_config["syslogserver"]
    if "]:" in syslog_server or (":" in syslog_server and not "]" in syslog_server): 
        host, port = syslog_server.rsplit(":", 1)
    else:
        host, port = syslog_server, "514"

    host = host.replace("[", "").replace("]", "")

    result += 'destination loghost { '

    if advanced_config["syslog_transport"] == "TLS":
        try:
            certificate_authority = middleware.call_sync(
                "certificateauthority.query", [
                    ("id", "=", advanced_config["syslog_tls_certificate_authority"]), ("revoked", "=", False),
                ],
                {"get": True}
            )
        except IndexError:
            logger.warning("Syslog TLS certificate not available, skipping remote syslog destination")
            return ""

        result += f"syslog(\"{host}\" port({port}) transport(\"tls\") ip-protocol(6) "
        try:
            ca_dir = "/etc/certificates/CA"
            for filename in os.listdir(ca_dir):
                if filename.endswith(".0") and os.path.islink(os.path.join(ca_dir, filename)):
                    os.unlink(os.path.join(ca_dir, filename))
            os.symlink(
                certificate_authority["certificate_path"], os.path.join(
                    ca_dir, "%x.0" % certificate_authority["subject_name_hash"]
                )
            )
        except Exception:
            logger.error("Error symlinking syslog CA, skipping remote syslog destination", exc_info=True)
            return ""
        else:
            result += f"tls(ca-dir(\"{ca_dir}\") "

        certificate = middleware.call_sync(
            "certificate.query", [("id", "=", advanced_config["syslog_tls_certificate"])]
        )
        if certificate and not certificate[0]["revoked"]:
            result += f"key-file(\"{certificate[0]['privatekey_path']}\") " \
                      f"cert-file(\"{certificate[0]['certificate_path']}\")"
        else:
            msg = 'Skipping setting key-file/cert-file for remote syslog as '
            if not certificate:
                msg += 'no certificate configured'
            else:
                msg += 'specified certificate has been revoked'
            logger.debug(msg)

        result += "));"
    else:
        transport = advanced_config["syslog_transport"].lower()
        result += f"syslog(\"{host}\" port({port}) localport(514) transport(\"{transport}\") ip-protocol(6));"


    result += ' };\n'
    result += 'log { source(tn_remote_src_files); filter(f_tnremote); destination(loghost); };\n'
    result += 'log { source(s_src); filter(f_tnremote); destination(loghost); };\n'

    return result
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

source tn_remote_src_files {
  file("/var/log/middlewared.log");
  file("/var/log/failover.log");
  file("/var/log/fenced.log");
  file("/var/log/zettarepl.log");
};

##################
# filters
##################
@include "/etc/syslog-ng/conf.d/tnfilters.conf"

##################
# destinations
##################
@include "/etc/syslog-ng/conf.d/tndestinations.conf"

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


% if render_ctx['system.advanced.config']['syslogserver']:
${generate_syslog_remote_destination(render_ctx['system.advanced.config'])}
% endif
