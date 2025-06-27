import time

from middlewared.test.integration.utils.client import client
from middlewared.test.integration.utils.ssh import ssh


def wait_for_events(events_list, expected_count=1, timeout=5.0, interval=0.5):
    """Wait for events with retry logic and early exit"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if len(events_list) >= expected_count:
            return True
        time.sleep(interval)
    return False


def test_ipaddress_change_events_add_single():
    """Test IP address being added and shows up in available_ips array"""
    dummy_if = "dummy0"
    test_ip = "192.168.100.1/24"

    try:
        # Create dummy interface
        ssh(f"ip link add {dummy_if} type dummy")
        ssh(f"ip link set {dummy_if} up")
        events = []

        def callback(event_type, **message):
            nonlocal events
            if message["fields"]["iface"] == dummy_if:
                events.append(message["fields"])

        with client(py_exceptions=False) as c:
            c.subscribe("ipaddress.change", callback, sync=True)
            # Add IP address
            ssh(f"ip addr add {test_ip} dev {dummy_if}")
            # Wait for event
            assert wait_for_events(events, 1), "Expected 1 event but got none"
            # Verify event was received
            assert len(events) == 1
            event = events[0]
            assert event["event"] == "add"
            assert event["iface"] == dummy_if
            assert event["ip"] == test_ip
            assert event["family"] == "inet"
            assert "192.168.100.1" in event["available_ips"]
    finally:
        # Cleanup
        ssh(f"ip link delete {dummy_if}", check=False)


def test_ipaddress_change_events_remove_single():
    """Test IP address being removed and available_ips array contains only IPv6 link-local"""
    dummy_if = "dummy1"
    test_ip = "192.168.101.1/24"
    try:
        # Create dummy interface and add IP
        ssh(f"ip link add {dummy_if} type dummy")
        ssh(f"ip link set {dummy_if} up")
        ssh(f"ip addr add {test_ip} dev {dummy_if}")
        events = []

        def callback(event_type, **message):
            nonlocal events
            if message["fields"]["iface"] == dummy_if:
                events.append(message["fields"])

        with client(py_exceptions=False) as c:
            c.subscribe("ipaddress.change", callback, sync=True)
            # Remove IP address
            ssh(f"ip addr del {test_ip} dev {dummy_if}")
            # Wait for event
            assert wait_for_events(events, 1), "Expected 1 event but got none"
            # Verify event was received
            assert len(events) == 1
            event = events[0]
            assert event["event"] == "remove"
            assert event["iface"] == dummy_if
            assert event["ip"] == test_ip
            assert event["family"] == "inet"
            # Only IPv6 link-local should remain
            assert len(event["available_ips"]) == 1
            assert event["available_ips"][0].startswith("fe80::")
    finally:
        # Cleanup
        ssh(f"ip link delete {dummy_if}", check=False)


def test_ipaddress_change_events_add_multiple():
    """Test IP address being added shows in available_ips along with existing IPs"""
    dummy_if = "dummy2"
    first_ip = "192.168.102.1/24"
    second_ip = "192.168.102.2/24"
    try:
        # Create dummy interface and add first IP
        ssh(f"ip link add {dummy_if} type dummy")
        ssh(f"ip link set {dummy_if} up")
        ssh(f"ip addr add {first_ip} dev {dummy_if}")
        events = []

        def callback(event_type, **message):
            nonlocal events
            if message["fields"]["iface"] == dummy_if:
                events.append(message["fields"])

        with client(py_exceptions=False) as c:
            c.subscribe("ipaddress.change", callback, sync=True)
            # Add second IP address
            ssh(f"ip addr add {second_ip} dev {dummy_if}")
            # Wait for event
            assert wait_for_events(events, 1), "Expected 1 event but got none"
            # Verify event was received
            assert len(events) == 1
            event = events[0]
            assert event["event"] == "add"
            assert event["iface"] == dummy_if
            assert event["ip"] == second_ip
            assert event["family"] == "inet"
            # Both IPv4 IPs should be in available_ips, plus IPv6 link-local
            assert "192.168.102.1" in event["available_ips"]
            assert "192.168.102.2" in event["available_ips"]
            # Should have 2 IPv4 + 1 IPv6 link-local
            assert len(event["available_ips"]) == 3
            ipv6_count = sum(1 for ip in event["available_ips"] if ip.startswith("fe80::"))
            assert ipv6_count == 1
    finally:
        # Cleanup
        ssh(f"ip link delete {dummy_if}", check=False)


def test_ipaddress_change_events_remove_one_of_multiple():
    """Test IP address being removed but other IPs remain in available_ips"""
    dummy_if = "dummy3"
    first_ip = "192.168.103.1/24"
    second_ip = "192.168.103.2/24"
    try:
        # Create dummy interface and add both IPs
        ssh(f"ip link add {dummy_if} type dummy")
        ssh(f"ip link set {dummy_if} up")
        ssh(f"ip addr add {first_ip} dev {dummy_if}")
        ssh(f"ip addr add {second_ip} dev {dummy_if}")
        events = []

        def callback(event_type, **message):
            nonlocal events
            if message["fields"]["iface"] == dummy_if and message["fields"]["family"] == "inet":
                events.append(message["fields"])

        with client(py_exceptions=False) as c:
            c.subscribe("ipaddress.change", callback, sync=True)
            # Remove second IP address (to match the expected event)
            ssh(f"ip addr del {second_ip} dev {dummy_if}")
            # Wait for event
            assert wait_for_events(events, 1), "Expected 1 event but got none"
            # Verify event was received
            assert len(events) == 1
            event = events[0]
            assert event["event"] == "remove"
            assert event["iface"] == dummy_if
            assert event["ip"] == second_ip
            assert event["family"] == "inet"
            # First IP should remain, plus IPv6 link-local
            assert "192.168.103.1" in event["available_ips"]
            assert "192.168.103.2" not in event["available_ips"]
            # Should have 1 IPv4 + 1 IPv6 link-local
            assert len(event["available_ips"]) == 2
            ipv6_count = sum(1 for ip in event["available_ips"] if ip.startswith("fe80::"))
            assert ipv6_count == 1
    finally:
        # Cleanup
        ssh(f"ip link delete {dummy_if}", check=False)
