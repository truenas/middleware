import json
import os

from middlewared.plugins.etc import FileShouldNotExist
from middlewared.utils.webshare import WEBSHARE_PATH


def render(service, middleware):
    if not os.path.exists(WEBSHARE_PATH):
        raise FileShouldNotExist()

    os.makedirs("/etc/webshare-auth", exist_ok=True, mode=0o700)
    return json.dumps({
        "server": {
            "socket_path": "/var/run/webshare/webshare-link.sock"
        },
        "security": {
            "rate_limit": "10/minute",
            "max_download_size": "10GB",
            "max_upload_size": "1GB",
            "allowed_origins": ["*"],
            "cors_enabled": True
        },
        "logging": {
            "level": "info",
            "file": "/var/log/webshare-link/access.log",
            "audit_file": "/var/log/webshare-link/audit.log"
        },
        "proxy": {
            "enabled": True,
            "port": 756
        }
    }, indent=2) + "\n"
