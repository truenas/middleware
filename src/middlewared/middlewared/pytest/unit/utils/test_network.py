import ipaddress

from middlewared.service_exception import ValidationErrors
from middlewared.utils.network import system_ips_to_cidrs, validate_network_overlaps


class TestSystemIpsToCidrs:
    def test_empty_list(self):
        assert system_ips_to_cidrs([]) == set()

    def test_single_ipv4(self):
        ips = [{"type": "INET", "address": "192.168.1.100", "netmask": 24, "broadcast": "192.168.1.255"}]
        result = system_ips_to_cidrs(ips)
        assert result == {ipaddress.ip_network("192.168.1.0/24")}

    def test_single_ipv6(self):
        ips = [{"type": "INET6", "address": "fe80::1", "netmask": 64, "broadcast": "fe80::ffff:ffff:ffff:ffff"}]
        result = system_ips_to_cidrs(ips)
        assert result == {ipaddress.ip_network("fe80::/64")}

    def test_mixed_v4_and_v6(self):
        ips = [
            {"type": "INET", "address": "10.0.0.5", "netmask": 8, "broadcast": "10.255.255.255"},
            {"type": "INET6", "address": "fd00::1", "netmask": 48, "broadcast": "fd00::ffff:ffff:ffff:ffff"},
        ]
        result = system_ips_to_cidrs(ips)
        assert result == {
            ipaddress.ip_network("10.0.0.0/8"),
            ipaddress.ip_network("fd00::/48"),
        }

    def test_host_bits_are_masked(self):
        """Verify strict=False behavior: host bits in address get masked off."""
        ips = [{"type": "INET", "address": "172.20.0.33", "netmask": 16, "broadcast": "172.20.255.255"}]
        result = system_ips_to_cidrs(ips)
        assert result == {ipaddress.ip_network("172.20.0.0/16")}

    def test_duplicate_ips_deduplicated(self):
        ips = [
            {"type": "INET", "address": "10.0.0.1", "netmask": 24, "broadcast": "10.0.0.255"},
            {"type": "INET", "address": "10.0.0.2", "netmask": 24, "broadcast": "10.0.0.255"},
        ]
        result = system_ips_to_cidrs(ips)
        # Both map to the same /24 network, so deduplicated to one entry
        assert result == {ipaddress.ip_network("10.0.0.0/24")}


class TestValidateNetworkOverlaps:
    def test_no_overlap_v4(self):
        verrors = ValidationErrors()
        network = ipaddress.ip_network("10.0.0.0/8")
        system_cidrs = {ipaddress.ip_network("192.168.1.0/24")}
        validate_network_overlaps("test.field", network, system_cidrs, verrors)
        assert len(verrors.errors) == 0

    def test_overlap_v4(self):
        verrors = ValidationErrors()
        network = ipaddress.ip_network("192.168.1.0/24")
        system_cidrs = {ipaddress.ip_network("192.168.0.0/16")}
        validate_network_overlaps("test.field", network, system_cidrs, verrors)
        assert len(verrors.errors) == 1
        assert "overlaps" in verrors.errors[0].errmsg

    def test_no_overlap_v6(self):
        verrors = ValidationErrors()
        network = ipaddress.ip_network("fd00::/48")
        system_cidrs = {ipaddress.ip_network("fe80::/64")}
        validate_network_overlaps("test.field", network, system_cidrs, verrors)
        assert len(verrors.errors) == 0

    def test_overlap_v6(self):
        verrors = ValidationErrors()
        network = ipaddress.ip_network("fe80::/56")
        system_cidrs = {ipaddress.ip_network("fe80::/64")}
        validate_network_overlaps("test.field", network, system_cidrs, verrors)
        assert len(verrors.errors) == 1
        assert "overlaps" in verrors.errors[0].errmsg

    def test_v4_does_not_compare_against_v6(self):
        """IPv4 network should not be compared against IPv6 CIDRs."""
        verrors = ValidationErrors()
        network = ipaddress.ip_network("10.0.0.0/8")
        system_cidrs = {ipaddress.ip_network("fe80::/64")}
        validate_network_overlaps("test.field", network, system_cidrs, verrors)
        assert len(verrors.errors) == 0

    def test_v6_does_not_compare_against_v4(self):
        """IPv6 network should not be compared against IPv4 CIDRs."""
        verrors = ValidationErrors()
        network = ipaddress.ip_network("fe80::/64")
        system_cidrs = {ipaddress.ip_network("192.168.0.0/16")}
        validate_network_overlaps("test.field", network, system_cidrs, verrors)
        assert len(verrors.errors) == 0

    def test_mixed_cidrs_only_same_family_checked(self):
        """With mixed v4/v6 system CIDRs, only same-family overlap triggers error."""
        verrors = ValidationErrors()
        network = ipaddress.ip_network("192.168.1.0/24")
        system_cidrs = {
            ipaddress.ip_network("192.168.0.0/16"),  # overlaps
            ipaddress.ip_network("fe80::/64"),          # different family, ignored
        }
        validate_network_overlaps("test.field", network, system_cidrs, verrors)
        assert len(verrors.errors) == 1

    def test_empty_system_cidrs(self):
        verrors = ValidationErrors()
        network = ipaddress.ip_network("10.0.0.0/8")
        validate_network_overlaps("test.field", network, set(), verrors)
        assert len(verrors.errors) == 0

    def test_error_message_contains_network(self):
        verrors = ValidationErrors()
        network = ipaddress.ip_network("172.20.2.0/24")
        system_cidrs = {ipaddress.ip_network("172.20.0.0/16")}
        validate_network_overlaps("test.field", network, system_cidrs, verrors)
        assert verrors.errors[0].errmsg == "Network 172.20.2.0/24 overlaps with an existing system network"

    def test_schema_propagated(self):
        verrors = ValidationErrors()
        network = ipaddress.ip_network("10.0.0.0/8")
        system_cidrs = {ipaddress.ip_network("10.0.0.0/8")}
        validate_network_overlaps("my_custom.schema", network, system_cidrs, verrors)
        assert verrors.errors[0].attribute == "my_custom.schema"
