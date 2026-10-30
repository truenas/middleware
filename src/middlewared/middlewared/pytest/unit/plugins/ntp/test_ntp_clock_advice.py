from middlewared.plugins.ntp.advice import domain_clock_advice


def test_nothing_to_add_without_nts():
    """Taking time from the domain controller works, so the usual advice about NTP stands."""
    assert domain_clock_advice([], False) == ""


def test_nts_servers_are_named_and_the_way_back_offered():
    advice = domain_clock_advice(["time.cloudflare.com", "ntppool1.time.nl"], False)

    assert "only from its NTS servers (time.cloudflare.com, ntppool1.time.nl)" in advice
    assert "Correct the domain controller's clock, or remove the NTS servers" in advice


def test_required_nts_leaves_only_the_domain_controllers_clock():
    advice = domain_clock_advice(["time.cloudflare.com"], True)

    assert advice.startswith("NTS is required by the system security configuration")
    assert advice.endswith("Correct the domain controller's clock.")
