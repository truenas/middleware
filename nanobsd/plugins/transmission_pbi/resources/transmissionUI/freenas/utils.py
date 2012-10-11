from subprocess import Popen, PIPE
import hashlib
import os
import platform

transmission_pbi_path = "/usr/pbi/transmission-" + platform.machine()
transmission_etc_path = os.path.join(transmission_pbi_path, "etc")
transmission_mnt_path = os.path.join(transmission_pbi_path, "mnt")
transmission_fcgi_pidfile = "/var/run/transmission_fcgi_server.pid"
transmission_fcgi_wwwdir = os.path.join(transmission_pbi_path, "www")
transmission_control = "/usr/local/etc/rc.d/transmission"
transmission_icon = os.path.join(transmission_pbi_path, "default.png")
transmission_oauth_file = os.path.join(transmission_pbi_path, ".oauth")


def get_rpc_url(request):
    return 'http%s://%s:%s/plugins/json-rpc/v1/' % (
        's' if request.is_secure() else '',
        request.META.get("SERVER_ADDR"),
        request.META.get("SERVER_PORT"),
        )


def get_transmission_oauth_creds():
    f = open(transmission_oauth_file)
    lines = f.readlines()
    f.close()

    key = secret = None
    for l in lines:
        l = l.strip()

        if l.startswith("key"):
            pair = l.split("=")
            if len(pair) > 1:
                key = pair[1].strip()

        elif l.startswith("secret"):
            pair = l.split("=")
            if len(pair) > 1:
                secret = pair[1].strip()

    return key, secret

transmission_advanced_vars = {
    "logfile": {
        "type": "textbox",
        "opt": "-e",
        },
}

transmission_settings = {
    "download_dir": {
        "field": "download-dir",
        "type": "textbox",
        },
    "watch_dir": {
        "field": "watch-dir",
        "type": "textbox",
        },
    "encryption": {
        "field": "encryption",
        "type": "textbox",
        },
    "rpc_port": {
        "field": "rpc-port",
        "type": "textbox",
        },
    "rpc_auth": {
        "field": "rpc-enabled",
        "type": "checkbox",
        },
    "rpc_auth_required": {
        "field": "rpc-authentication-required",
        "type": "checkbox",
        },
    "rpc_username": {
        "field": "rpc-username",
        "type": "textbox",
        },
    "rpc_password": {
        "field": "rpc-password",
        "type": "textbox",
        "filter": lambda x: '{' + hashlib.sha1(x).hexdigest()
        },
    "rpc_whitelist_enabled": {
        "field": "rpc-whitelist-enabled",
        "type": "textbox",
        },
    "rpc_whitelist": {
        "field": "rpc-whitelist",
        "type": "textbox",
        },
    "dht": {
        "field": "dht-enabled",
        "type": "checkbox",
        },
    "lpd": {
        "field": "lpd-enabled",
        "type": "checkbox",
        },
    "utp": {
        "field": "utp-enabled",
        "type": "checkbox",
        },
    "peer_port": {
        "field": "peer-port",
        "type": "textbox",
        },
    "portmap": {
        "field": "port-forwarding-enabled",
        },
    "peerlimit_global": {
        "field": "peer-limit-global",
        "type": "textbox",
        },
    "peerlimit_torrent": {
        "field": "peer-limit-per-torrent",
        "type": "textbox",
        },
    "global_seedratio": {
        "field": "ratio-limit",
        "type": "textbox",
        "filter": lambda x: str(x)
        }
}
