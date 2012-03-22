from subprocess import Popen, PIPE
import os


def get_arch():
    cmd = "/usr/bin/uname -m"
    pipe = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE,
        shell=True, close_fds=True)

    out = pipe.stdout.read().strip()
    pipe.wait()
    return out

transmission_pbi_path = "/usr/pbi/transmission-" + get_arch()
transmission_etc_path = os.path.join(transmission_pbi_path, "etc")
transmission_mnt_path = os.path.join(transmission_pbi_path, "mnt")
transmission_fcgi_pidfile = "/var/run/transmission_fcgi_server.pid"
transmission_fcgi_wwwdir = os.path.join(transmission_pbi_path, "www")
transmission_control = "/usr/local/etc/rc.d/transmission"

transmission_advanced_vars = {
    'allow': {
        "type": "textbox",
        "opt": "-a",
        },
    "blocklist": {
        "type": "checkbox",
        "on": "-b",
        "off": "-B",
        },
    "logfile": {
        "type": "textbox",
        "opt": "-e",
        },
    "rpc_port": {
        "type": "textbox",
        "opt": "-p",
        },
    "rpc_auth": {
        "type": "checkbox",
        "on": "-t",
        "off": "-T",
        },
    "rpc_username": {
        "type": "textbox",
        "opt": "-u",
        },
    "rpc_password": {
        "type": "textbox",
        "opt": "-v",
        },
    "dht": {
        "type": "checkbox",
        "on": "-o",
        "off": "-O",
        },
    "lpd": {
        "type": "checkbox",
        "on": "-y",
        "off": "-Y",
        },
    "utp": {
        "type": "checkbox",
        "on": "--utp",
        "off": "--no-utp",
        },
    "peer_port": {
        "type": "textbox",
        "opt": "-P",
        },
    "portmap": {
        "type": "checkbox",
        "on": "-m",
        "off": "-M",
        },
    "peerlimit_global": {
        "type": "textbox",
        "opt": "-L",
        },
    "peerlimit_torrent": {
        "type": "textbox",
        "opt": "-l",
        },
    "encryption_required": {
        "type": "checkbox",
        "on": "-er",
        "off": None,
        },
    "encryption_preferred": {
        "type": "checkbox",
        "on": "-ep",
        "off": None,
        },
    "encryption_tolerated": {
        "type": "checkbox",
        "on": "-et",
        "off": None,
        },
    "global_seedratio": {
        "type": "textbox",
        "opt": "-gsr",
        }
}
