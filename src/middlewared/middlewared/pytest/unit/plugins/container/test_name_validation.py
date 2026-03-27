import pytest

from middlewared.plugins.container.crud import RE_NAME


@pytest.mark.parametrize('name', [
    # single characters
    'a',
    'Z',
    '1',
    # simple names
    'test',
    'my-container',
    'abc123',
    # all-digit labels (RFC 1123 allows)
    '123',
    '001',
    '42',
    # case variations
    'ALLCAPS',
    'MiXeD',
    # max single-label length (63 chars)
    'a' * 63,
    'a' + 'b' * 61 + 'c',
    # hyphens in middle
    'a-b',
    'a' + '-b' * 31,
    # dotted FQDNs
    'web.prod.local',
    'a.b',
    'a.b.c.d.e',
    '123.abc',
    'my-host.example.com',
    # multi-label with max label length
    'a' * 63 + '.' + 'b' * 63,
    # realistic names
    'test-container-123',
    'ubuntu-24-04',
    'web-server-01',
])
def test__valid_container_names(name):
    assert RE_NAME.match(name), f'{name!r} should be a valid container name'


@pytest.mark.parametrize('name', [
    # empty
    '',
    # leading hyphen
    '-test',
    # trailing hyphen
    'test-',
    # single/all hyphens
    '-',
    '---',
    # leading and trailing
    '-test-',
    # underscore
    'my_container',
    # space
    'my container',
    # special characters
    'my@container',
    'foo/bar',
    'foo:bar',
    # single label over 63 chars
    'a' * 64,
    # leading/trailing dot
    '.test',
    'test.',
    # consecutive dots
    'test..foo',
    # IPv4 addresses (dotted-decimal)
    '10.2.0.52',
    '192.168.1.1',
    '0.0.0.0',
    '255.255.255.255',
    '999.999.999.999',
    # control characters
    'test\nname',
    'test\tname',
    # label in the middle exceeds 63 chars
    'a.' + 'b' * 64 + '.c',
    # leading hyphen in a label after dot
    'foo.-bar',
    # trailing hyphen in a label before dot
    'foo-.bar',
    # total length over 253
    ('a' * 63 + '.') * 3 + 'a' * 63 + '.b',
])
def test__invalid_container_names(name):
    assert not RE_NAME.match(name), f'{name!r} should NOT be a valid container name'
