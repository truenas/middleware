from time import sleep
from middlewared.test.integration.utils import call, ssh


def test_audit_system_escalation():
    """Generate an ESCALATION event and find it in the TrueNAS audit log."""

    # Run an ESCALATION command as root
    cmd = "systemctl status nfs-server"
    ssh(cmd, check=False)

    # We need to allow some time for audit message to flush via syslog to DB
    sleep(5)

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
    results = call('audit.query', payload)

    # Should find at least one result
    assert len(results) > 0, "Did not find escalation event"


def test_audit_system_rin_operator_simple():
    """Test the 'rin' (contains) operator for substring matching."""

    # Generate a system event with a known proctitle
    cmd = "systemctl status middlewared"
    ssh(cmd, check=False)

    # Allow time for audit message to flush
    sleep(5)

    # Simple 'rin' operator - proctitle contains 'systemctl'
    payload = {
        "services": ["SYSTEM"],
        "query-filters": [
            ["event", "=", "ESCALATION"],
            ["event_data.proctitle", "rin", "systemctl"]  # Contains 'systemctl'
        ],
        "query-options": {
            "order_by": ["-message_timestamp"],
            "limit": 2
        }
    }
    results = call('audit.query', payload)

    # Should find at least one result
    assert len(results) > 0, "No results found with 'rin' operator"

    # Verify all results contain 'systemctl' in proctitle
    for entry in results:
        proctitle = entry.get('event_data', {}).get('proctitle', '')
        assert 'systemctl' in proctitle, f"proctitle '{proctitle}' does not contain 'systemctl'"


def test_audit_system_rin_operator_with_or():
    """Test the 'rin' operator with OR filters."""

    # Generate a system event
    ssh("systemctl status nfs-server", check=False)
    sleep(5)

    # Query with OR containing multiple 'rin' conditions
    payload = {
        "services": ["SYSTEM"],
        "query-filters": [
            ["event", "=", "ESCALATION"],
            ["OR", [
                ["event_data.proctitle", "rin", "systemctl"],
                ["event_data.proctitle", "rin", "init"],
                ["event_data.proctitle", "rin", "shutdown"],
            ]]
        ],
        "query-options": {"order_by": ["-message_timestamp"], "limit": 2}
    }
    results = call('audit.query', payload)

    # Verify each result contains at least one search term
    assert len(results) > 0, "No results found with OR + 'rin' operator"
    for entry in results:
        proctitle = entry.get('event_data', {}).get('proctitle', '')
        has_match = any(term in proctitle for term in ['systemctl', 'init', 'shutdown'])
        assert has_match, f"'{proctitle}' does not contain any search term"
