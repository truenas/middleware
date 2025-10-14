import json
import os

from middlewared.plugins.etc import FileShouldNotExist
from middlewared.utils.smb import TRUESEARCH_ES_PATH


def render(service, middleware):
    if not os.path.exists("/var/db/system/truesearch"):
        raise FileShouldNotExist()

    directories = middleware.call_sync("truesearch.directories")
    if not directories:
        raise FileShouldNotExist()

    os.makedirs("/etc/truesearch", exist_ok=True, mode=0o700)
    return json.dumps({
        "directories": directories,
        "index_path": "/var/db/system/truesearch/index",
        "log_level": "info",
        "max_file_size": 104857600,
        "worker_count": 0,
        "batch_size": 1000,
        "archive": {
            "max_depth": 2,
            "max_entries": 1000,
            "max_archive_size": 524288000,
            "index_contents": True,
            "extract_text": False,
            "supported_formats": ["zip", "tar", "gz", "bz2", "xz", "rar", "7z"]
        },
        "index_settings": {
            "max_index_size": 10737418240,
            "max_document_count": 1000000
        },
        "maintenance": {
            "enabled": True,
            "schedule": "0 2 * * *"
        },
        "reindex": {
            "enabled": False,
            "schedule": "weekly",
            "interval_hours": 168,
            "start_time": "02:00",
            "max_duration_minutes": 240,
            "clean_index": False
        },
        "service": {
            "socket_path": "/run/truesearch/truesearch.sock",
            "capability_mode": "read_only",
            "required_capabilities": ["CAP_DAC_READ_SEARCH"],
            "optional_capabilities": []
        },
        "security": {
            "processing_timeout_seconds": 300,
            "max_compression_ratio": 100.0,
            "max_decompressed_size": 10737418240,
            "max_memory_per_file": 104857600,
            "enable_panic_recovery": True,
            "validate_archive_paths": True,
            "max_text_file_size": 10485760,
            "restart_workers_on_panic": True,
            "validate_capabilities": True,
            "fail_without_capabilities": True,
            "monitor_capability_changes": True,
            "max_file_descriptors": 65536,
            "enable_seccomp": False
        },
        "audit": {
            "enabled": False,
            "log_path": "/var/log/truesearch/audit.log",
            "max_log_size": 104857600,
            "sensitive_paths": ["/etc", "/root", "/home/*/.ssh"],
            "log_file_access": False,
            "log_security_events": True
        },
        "elasticsearch": {
            "enabled": True,
            "socket_path": TRUESEARCH_ES_PATH,
            "index": "files",
            "max_results": 10000
        }
    }, indent=2) + "\n"
