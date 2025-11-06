from middlewared.test.integration.utils import call, ssh


def test_audit_system_escalation():
    """Generate an ESCALATION event and find it in the TrueNAS audit log."""

    # Run an ESCALATION command as root
    cmd = "systemctl status nfs-server"
    ssh(cmd, check=False)

    # Using SYSTEM filters, find the event
    payload = {
        "services": ["SYSTEM"],
        "query-filters": [
            ["event", "=", "ESCALATION"],
            ["event_data.syscall.AUID", "=", "root"],
            ["event_data.proctitle", "=", cmd]
        ],
        "query-options": {"order_by": ["-message_timestamp"], "limit": 1, "get": True}
    }
    event = call('audit.query', payload)
