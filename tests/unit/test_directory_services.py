import pytest

from datetime import datetime, timedelta
from dataclasses import asdict
from middlewared.utils.directoryservices.ipa import ldap_dn_to_realm
from middlewared.utils.directoryservices import dns
from middlewared.utils.time_utils import utc_now
from truenas_api_client import ejson as json


@pytest.mark.parametrize('ldap_dn,realm', [
    ('dc=company,dc=com', 'company.com'),
    ('dc=tn,dc=ixsystems,dc=net', 'tn.ixsystems.net'),
])
def test_dn_to_realm(ldap_dn, realm):
    assert ldap_dn_to_realm(ldap_dn) == realm


def get_nsupdate_object(fqdn: str, age_days: int) -> dns.NSUpdateState:
    now = utc_now(False)
    record_age = now - timedelta(days=age_days)
    return dns.NSUpdateState(
        fqdn=fqdn,
        expiry=record_age + dns.DEFAULT_RECORD_EXPIRY,
        version=dns.NSUPDATE_STATE_VERSION
    )


def write_nsupdate_object(data: dns.NSUpdateState) -> None:
    with open(dns.DS_DNS_STATE_FILE, 'w') as f:
        f.write(json.dumps(asdict(data)))
        f.flush()


@pytest.mark.parametrize('fqdn,fqdn_to_check,age,expired', [
    ('bobnas.billy.goat', 'bobnas.billy.goat', 0, False),
    ('bobnas.billy.goat', 'bobnas.billy.goat', dns.DEFAULT_RECORD_EXPIRY.days - 1, False),
    ('bobnas.billy.goat', 'bobnas.BILLY.GOAT', dns.DEFAULT_RECORD_EXPIRY.days - 1, False),
    ('bobnas.billy.goat', 'bobnas.billy.goat', dns.DEFAULT_RECORD_EXPIRY.days + 1, True),
    ('bobnas.billy.goat', 'canary.billy.goat', 0, True),  # wrong name
])
def test_dns_check_expired(fqdn, fqdn_to_check, age, expired):
    nsupdate_obj = get_nsupdate_object(fqdn, age)
    write_nsupdate_object(nsupdate_obj)

    assert dns.dns_record_is_expired(fqdn_to_check) is expired


def test_dns_wrong_version():
    fqdn = 'bobnas.billy.goat'
    nsupdate_obj = get_nsupdate_object(fqdn, 0)
    write_nsupdate_object(nsupdate_obj)

    assert dns.dns_record_is_expired(fqdn) is False

    nsupdate_obj.version = dns.NSUPDATE_STATE_VERSION -1
    write_nsupdate_object(nsupdate_obj)

    assert dns.dns_record_is_expired(fqdn) is True


def test_dns_remove_state():
    fqdn = 'bobnas.billy.goat'
    nsupdate_obj = get_nsupdate_object(fqdn, 0)
    write_nsupdate_object(nsupdate_obj)

    assert dns.dns_record_is_expired(fqdn) is False

    dns.remove_dns_record_state()

    assert dns.dns_record_is_expired(fqdn) is True
