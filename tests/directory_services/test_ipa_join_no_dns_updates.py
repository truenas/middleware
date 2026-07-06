import pytest

from middlewared.test.integration.assets.directory_service import directoryservice


def test_ipa_join_requires_dns_updates():
    """ Joining an IPA domain requires the TrueNAS host to register its DNS record so
    that the SMB and NFS Kerberos service principals can be created (FreeIPA refuses to
    add a service to a host that has no A/AAAA record). Attempting to join with DNS
    updates disabled must be rejected with a validation error rather than completing a
    join that leaves kerberized services non-functional. """
    with pytest.raises(Exception, match='DNS updates are currently required'):
        with directoryservice('IPA', dns_updates=False):
            pass
