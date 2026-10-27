import hashlib
import shlex
import subprocess
import sys

from middlewared.plugins.system_vendor.vendor import get_vendor
from middlewared.utils.db import query_config_table
from middlewared.utils.vendor import Vendors


def load_envvars(envvars_file: str):
    try:
        envvars = []
        with open(envvars_file, "r") as f:
            for line in f:
                if (line := line.strip()) and line[0] != "#":
                    envvars.append(line.split("=", 1))
        return dict(envvars)
    except (OSError, ValueError):
        return dict()


def get_hostid() -> str | None:
    try:
        with open("/etc/hostid", "rb") as f:
            return hashlib.file_digest(f, "sha256").hexdigest()
    except Exception:
        pass


def get_system_id() -> str | None:
    try:
        return query_config_table("system_globalid")["system_uuid"]
    except Exception:
        pass


def start_hexos_websocat():
    url = "wss://api.hexos.com"
    envvars_file = "/etc/default/websocat"
    envvars = load_envvars(envvars_file)

    systemd_opts = (
        "--unit=websocat",
        "--description=websocat daemon for HexOS",
        "--property=Restart=always",
        "--property=RestartSec=10",
        "--uid=www-data",
        f"--setenv=URL={url}",
        *[f"--setenv={name}={value}" for name, value in envvars.items()]
    )

    wsocat_path = "/usr/local/libexec/wsocat"
    wsocat_opts = (
        "--buffer-size 4194304",
        "--ping-interval 30",
        "--ping-timeout 60",
        "--exit-on-eof",
        "--text",
    )
    local_server = "ws://127.0.0.1:6000/websocket"

    hostid_hash = get_hostid()
    if hostid_hash is None:
        return

    ip_output = subprocess.check_output("ip -o -4 route get 8.8.8.8", shell=True, text=True)
    ip_address = ip_output.partition("src")[-1].split()[0]

    remote_server = f"{url}/server/{hostid_hash}/{ip_address}"
    # Hostids collide across installs; system_id is a random UUID made on first boot.
    # The hostid hash stays in the path so HexOS can match servers it already knows by it.
    if system_id := get_system_id():
        remote_server += f"?system_id={system_id}"

    # Start a transient service
    subprocess.run([
        "systemd-run",
        *systemd_opts,
        "/bin/bash",
        "-c",
        " ".join([wsocat_path, *wsocat_opts, local_server, shlex.quote(remote_server)])
    ])


def main():
    if get_vendor() == Vendors.HEXOS:
        start_hexos_websocat()


if __name__ == "__main__":
    try:
        main()
    finally:
        sys.exit(0)  # Never fail
