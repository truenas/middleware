from middlewared.test.integration.utils import call, ssh


def test_audit_system_escalation():
    """Generate an ESCALATION event and find it in the TrueNAS audit log."""

    # Run an ESCALATION command as root
    cmd = "systemctl status nfs-server"
    ssh(cmd, check=False)

    # Using SYSTEM filters, find the event
    payload = {
        "services": ["SYSTEM"],
        "query-filters": [["event", "=", "ESCALATION"], ["event_data.syscall.AUID", "=", "root"]],
        "query-options": {"count": True}
    }
    count = call('audit.query', payload)

    # Get and confirm the event
    payload['query-options'] = {"offset": count - 1, "limit": 1000}
    event = call('audit.query', payload)
    assert len(event) == 1
    proctitle = event[0]['event_data']['proctitle']
    assert proctitle == cmd, f"Expected {cmd!r} but found {proctitle!r}"
