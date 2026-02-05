import json
import os

from middlewared.plugins.etc import FileShouldNotExist
from middlewared.utils.webshare import WEBSHARE_PATH, WEBSHARE_BULK_DOWNLOAD_PATH


def render(service, middleware):
    if not os.path.exists(WEBSHARE_PATH):
        raise FileShouldNotExist()

    config = middleware.call_sync2(middleware.services.webshare.config)
    hostname = middleware.call_sync("system.hostname")
    rp_name = f"TrueNAS WebShare @ {hostname}"

    os.makedirs("/etc/webshare-auth", exist_ok=True, mode=0o700)
    return json.dumps({
        "pam_service_name": "webshare",
        "allowed_groups": ["truenas_webshare"],
        "webshare_config_path": "/etc/webshare/config.json",
        "log_level": "info",
        "data_directory": WEBSHARE_PATH,
        "bulk_download_tmp": WEBSHARE_BULK_DOWNLOAD_PATH,
        "session_log_retention": 20,
        "enable_web_terminal": False,
        "rate_limit": {
            "enabled": True,
            "max_concurrent_downloads": 5,
            "max_concurrent_per_ip": 10,
            "download_rate_limit_mb": 0,
            "burst_size_mb": 0,
            "max_requests_per_minute": 600,
            "request_burst": 20,
        },
        "truesearch": {
            "enabled": config.search,
        },
        "proxy": {
            "enabled": True,
            "port": 755,
            "bind_addrs": ["0.0.0.0"],
            "cert_path": "/etc/certificates",
            "cert_prefix": "truenas_connect",
            "dhparam_path": "/data/dhparam.pem",
            "timeouts": {
                "read_timeout_seconds": 86400,
                "write_timeout_seconds": 86400,
                "idle_timeout_seconds": 86400,
                "stream_timeout_seconds": 86400,
                "header_timeout_seconds": 60,
                "shutdown_timeout_seconds": 30,
            },
        },
        "passkey": {
            "mode": config.passkey.lower(),
            "rp_name": rp_name,
            "rp_display_name": rp_name,
            "rp_id": "truenas.direct",
            "rp_origins": middleware.call_sync("webshare.urls"),
            "timeout": 60000,
            "rate_limit": {
                "max_attempts_per_hour": 10,
                "max_registrations_per_day": 5
            },
            "recovery": {
                "admin_override_enabled": True,
                "emergency_contact_email": "",
                "account_lockout_minutes": 15,
                "max_failures_before_lock": 10,
            },
            "security": {
                "require_resident_key": False,
                "require_user_verification": False,
                "challenge_timeout_minutes": 5,
                "replay_protection_hours": 24,
            }
        },
        "webshare_link": {
            "enabled": True,
            "binary_path": "/usr/bin/truenas-webshare-link",
            "config_path": "/etc/webshare-link/config.json",
            "port": 8443,
            "health_check_url": "https://127.0.0.1:8443/health",
            "startup_timeout_seconds": 30,
            "restart_on_failure": True,
            "max_restarts": 5,
            "restart_delay_seconds": 10,
            "log_level": "info",
            "auto_start": True
        }
    }, indent=2) + "\n"
