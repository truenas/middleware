from subprocess import Popen, PIPE
import os
import platform

firefly_pbi_path = "/usr/pbi/firefly-" + platform.machine()
firefly_etc_path = os.path.join(firefly_pbi_path, "etc")
firefly_mnt_path = os.path.join(firefly_pbi_path, "mnt")
firefly_fcgi_pidfile = "/var/run/firefly_fcgi_server.pid"
firefly_fcgi_wwwdir = os.path.join(firefly_pbi_path, "www")
firefly_control = "/usr/local/etc/rc.d/mt-daapd"
firefly_config = os.path.join(firefly_etc_path, "mt-daapd.conf")

firefly_advanced_vars = {
    "set_cwd": {
        "type": "checkbox",
        "on": "-a",
        },
    "debuglevel": {
        "type": "textbox",
        "opt": "-d",
        },
    "debug_modules": {
        "type": "textbox",
        "opt": "-D",
        },
    "disable_mdns": {
        "type": "checkbox",
        "on": "-m",
        },
    "non_root_user": {
        "type": "checkbox",
        "on": "-y",
        },
    "ffid": {
        "type": "textbox",
        "opt": "-b",
        },
}
