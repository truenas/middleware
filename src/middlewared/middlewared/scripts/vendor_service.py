import subprocess
import sys

from truenas_api_client import Client


def main():
    with Client() as client:
        vendor_name = client.call("system.vendor.name")
        if vendor_name == "HexOS":
            url = "wss://api.hexos.com"
            systemd_opts = (
                "--description=websocat daemon for HexOS",
                "--on-active=10",
                "--service-type=simple",
                "--uid=www-data",
                f"--setenv=URL={url}",
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

            hostid_hash = subprocess.check_output("sha256sum /etc/hostid", shell=True, text=True).partition(" ")[0]
            ip_address = subprocess.check_output("ip -o -4 route get 8.8.8.8", shell=True, text=True).partition("src")[-1].split()[0]
            remote_server = f"{url}/server/{hostid_hash}/{ip_address}"

            # Start a transient service
            subprocess.run([
                "systemd-run",
                *systemd_opts, "--no-ask-password",
                "/bin/bash",
                "-c",
                " ".join([wsocat_path, *wsocat_opts, local_server, remote_server])
            ])


if __name__ == "__main__":
    try:
        main()
    finally:
        sys.exit(0)  # Never fail
