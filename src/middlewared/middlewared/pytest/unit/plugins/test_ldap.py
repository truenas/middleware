import pytest
from mock import Mock

from middlewared.schema import (
    accepts, LDAP_DN
)


@pytest.mark.parametrize('value,expected', [
    ('o=5def63d2b12d4332c706a57f,dc=jumpcloud,dc=com', 'o=5def63d2b12d4332c706a57f,dc=jumpcloud,dc=com'),
    ('canary', ValueError),
])
def test__schema_ldapdn(value, expected):
    @accepts(LDAP_DN('data', null=True))
    def ldapdnnotnull(self, data):
        return data

    self = Mock()

    if expected is ValueError:
        with pytest.raises(expected):
            ldapdnnotnull(self, value)
    else:
        assert ldapdnnotnull(self, value) == expected


def test__schema_ldapdn_null():
    @accepts(LDAP_DN('data', null=True))
    def ldapdnnull(self, data):
        return data

    self = Mock()

    assert ldapdnnull(self, None) is None
