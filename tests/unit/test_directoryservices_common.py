"""
Unit tests for the shared directory services FQDN helper.

An IPA host account may live in a DNS zone other than the IPA domain (a subdomain of it
or an unrelated zone entirely), so the IPA hostname may be supplied as a complete FQDN.
When it is, it must be used verbatim; blindly appending the domain produced names such as
"nas.lan.example.net.ipa.example.net" which the IPA server refuses to add.
"""

import pytest

from middlewared.utils.directoryservices.common import ds_config_to_fqdn, ds_hostname_is_fqdn


def _ds_config(service_type, hostname, domain):
    return {
        "service_type": service_type,
        "configuration": {"hostname": hostname, "domain": domain},
    }


@pytest.mark.parametrize(
    "hostname,domain,expected",
    [
        # Bare hostname is still qualified with the IPA domain.
        ("truenasnyc", "ipa.internal", "truenasnyc.ipa.internal"),
        # An FQDN under the IPA domain is used as-is rather than doubled up.
        ("truenasnyc.ipa.internal", "ipa.internal", "truenasnyc.ipa.internal"),
        # A subdomain of the IPA domain.
        ("truenasnyc.nyc.ipa.internal", "ipa.internal", "truenasnyc.nyc.ipa.internal"),
        # A zone entirely outside the IPA domain.
        ("nas-nyc.lan.example.net", "ipa.example.net", "nas-nyc.lan.example.net"),
    ],
)
def test__ipa_fqdn(hostname, domain, expected):
    assert ds_config_to_fqdn(_ds_config("IPA", hostname, domain)) == expected


def test__ad_hostname_is_always_qualified():
    """Active Directory takes a bare hostname; the domain is always appended."""
    assert ds_config_to_fqdn(_ds_config("ACTIVEDIRECTORY", "truenasnyc", "ad.internal")) == "truenasnyc.ad.internal"
    assert not ds_hostname_is_fqdn(_ds_config("ACTIVEDIRECTORY", "truenasnyc", "ad.internal"))


def test__unsupported_service_type():
    with pytest.raises(ValueError):
        ds_config_to_fqdn(_ds_config("LDAP", "truenasnyc", "ldap.internal"))
