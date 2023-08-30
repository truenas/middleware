<%
logger = middleware.logger

def generate_syslog_remote_destination(advanced_config):
    result = ""
    if ":" in advanced_config["syslogserver"]:
        host, port = advanced_config["syslogserver"].rsplit(":", 1)
    else:
        host, port = advanced_config["syslogserver"], "514"

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

        result += f"syslog(\"{host}\" port({port}) transport(\"tls\") "
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
        result += f'{transport}("{host}" port({port}) localport(514));'

    result += ' };\n'
    result += f'log {{ source(s_src); filter(f_tnremote_{advanced_config["sysloglevel"].lower()}); '
    result += 'destination(loghost); };\n'

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
  use_fqdn(no);
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

##################
# filters
##################
@include "/etc/syslog-ng/conf.d/tnfilters.conf"

##################
# destinations
##################
@include "/etc/syslog-ng/conf.d/tndestinations.conf"

#######################
# Log paths
########################
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

log {
  source(s_src);
  filter(f_k3s);
  destination { file("/var/log/k3s_daemon.log"); };
};
log {
  source(s_src);
  filter(f_containerd);
  destination { file("/var/log/containerd.log"); };
};
log {
  source(s_src);
  filter(f_kube_router);
  destination { file("/var/log/kube_router.log"); };
};
log {
  source(s_src);
  filter(f_app_mounts);
  destination { file("/var/log/app_mounts.log"); };
};

% if render_ctx['system.advanced.config']['syslogserver']:
${generate_syslog_remote_destination(render_ctx['system.advanced.config'])}
% endif
