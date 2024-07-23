import hashlib
import subprocess
import sys
import time

from middlewared.utils.vendor import Vendors
from truenas_api_client import Client


def load_envvars(envvars_file: str):
    try:
        envvars = []
        with open(envvars_file, "r") as f:
            for line in f:
                l = line.strip()
                if l and not l.startswith("#"):
                    envvars.append(l.split("=", 1))
        return dict(envvars)
    except (OSError, ValueError):
        return dict()


def get_hostid() -> str | None:
    try:
        with open("/etc/hostid", "rb") as f:
            return hashlib.file_digest(f, "sha256").hexdigest()
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
        "--buffer-size 1048576",
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

    # Start a transient service
    subprocess.run([
        "systemd-run",
        *systemd_opts,
        "/bin/bash",
        "-c",
        " ".join([wsocat_path, *wsocat_opts, local_server, remote_server])
    ])


def get_vendor_name(max_tries=30):
    """Wait for client to open and for system to be ready before returning system.vendor.name().

    Wait one second after each failed attempt. Raise an exception after failing the maximum allowed number of attempts.

    """
    tries = max_tries
    while tries > 0:
        try:
            with Client() as c:
                for _ in range(tries):
                    if c.call("system.ready"):
                        return c.call("system.vendor.name")
                    else:
                        time.sleep(1)
                else:
                    raise Exception(f"Failed to get vendor name after {max_tries} attempts: system not ready.")
        except Exception:
            time.sleep(1)
        tries -= 1
    else:
        raise Exception(f"Failed to open client after {max_tries} attempts.")


def main():
    vendor_name = get_vendor_name()

    if vendor_name == Vendors.HEXOS:
        start_hexos_websocat()


if __name__ == "__main__":
    try:
        main()
    finally:
        sys.exit(0)  # Never fail
