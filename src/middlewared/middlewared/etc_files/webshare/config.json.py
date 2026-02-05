import json
import os

from middlewared.plugins.etc import FileShouldNotExist
from middlewared.utils.webshare import WEBSHARE_BULK_DOWNLOAD_PATH


def render(service, middleware):
    if not os.path.exists("/var/db/system/webshare"):
        raise FileShouldNotExist()

    shares = middleware.call_sync2(
        middleware.services.sharing.webshare.query,
        [["enabled", "=", True], ["locked", "=", False]],
    )

    os.makedirs("/etc/webshare-auth", exist_ok=True, mode=0o700)
    return json.dumps({
        "shares": [
            {
                "name": share.name,
                "path": share.path,
                "is_home_base": share.is_home_base,
            }
            for share in shares
        ],
        "home_directory_template": "{{.Username}}",
        "home_directory_perms": "0700",
        "bulk_download_tmp": WEBSHARE_BULK_DOWNLOAD_PATH,
        "filesystem_sync": {
            "force_sync": True,
            "sync_directories": True,
            "fail_on_sync_error": True,
        },
        "url_downloads": {
            "enabled": True,
            "allowed_protocols": ["http", "https", "ftp"],
            "max_file_size": 10737418240,
            "timeout": 300,
            "max_redirects": 10,
            "user_agent": "TrueNAS-FileManager/1.0",
            "domain_allowlist": [],
            "domain_blocklist": ["localhost", "127.0.0.1", "0.0.0.0", "::1", "10.0.0.0/8", "172.16.0.0/12",
                                 "192.168.0.0/16"],
            "rate_limit": {
                "requests_per_minute": 10,
                "concurrent_downloads": 3,
            },
        },
        "storage_admins": True,
    }, indent=2) + "\n"
