from middlewared.utils import filter_list


DATA = [
    {
        'foo': 'foo1',
        'number': 1,
        'list': [1],
    },
    {
        'foo': 'foo2',
        'number': 2,
        'list': [2],
    },
    {
        'foo': '_foo_',
        'number': 3,
        'list': [3],
    },
]

COMPLEX_DATA = [
    {
        "timestamp": "2022-11-10T07:40:17.397502-0800",
        "type": "Authentication",
        "Authentication": {
            "version": {
                "major": 1,
                "minor": 2
            },
            "eventId": 4625,
            "logonId": "0",
            "logonType": 3,
            "status": "NT_STATUS_NO_SUCH_USER",
            "localAddress": "ipv4:192.168.0.200:445",
            "remoteAddress": "ipv4:192.168.0.151:50559",
            "serviceDescription": "SMB2",
            "authDescription": None,
            "clientDomain": "MicrosoftAccount",
            "clientAccount": "awalker325@outlook.com",
            "workstation": "WALKSURF",
            "becameAccount": None,
            "becameDomain": None,
            "becameSid": None,
            "mappedAccount": "awalker325@outlook.com",
            "mappedDomain": "MicrosoftAccount",
            "netlogonComputer": None,
            "netlogonTrustAccount": None,
            "netlogonNegotiateFlags": "0x00000000",
            "netlogonSecureChannelType": 0,
            "netlogonTrustAccountSid": None,
            "passwordType": "NTLMv2",
            "duration": 6298
        },
        "timestamp_tval": {
            "tv_sec": 1668094817,
            "tv_usec": 397502
        }
    },
    {
        "timestamp": "2023-01-24T12:37:39.522594-0800",
        "type": "Authentication",
        "Authentication": {
            "version": {
                "major": 1,
                "minor": 2
            },
            "eventId": 4624,
            "logonId": "c1b1a262c42babb6",
            "logonType": 8,
            "status": "NT_STATUS_OK",
            "localAddress": "unix:",
            "remoteAddress": "unix:",
            "serviceDescription": "winbind",
            "authDescription": "PAM_AUTH, PAM_WINBIND[sshd], 133191",
            "clientDomain": "BILLY",
            "clientAccount": "joiner",
            "workstation": None,
            "becameAccount": "joiner",
            "becameDomain": "BILLY",
            "becameSid": "S-1-5-21-1002530428-2020721000-3540273080-1103",
            "mappedAccount": None,
            "mappedDomain": None,
            "netlogonComputer": None,
            "netlogonTrustAccount": None,
            "netlogonNegotiateFlags": "0x00000000",
            "netlogonSecureChannelType": 0,
            "netlogonTrustAccountSid": None,
            "passwordType": "Plaintext",
            "duration": 23554
        },
        "timestamp_tval": {
            "tv_sec": 1674592659,
            "tv_usec": 522594
        }
    }
]


def test__filter_list_equal():
    assert len(filter_list(DATA, [['foo', '=', 'foo1']])) == 1


def test__filter_list_starts():
    assert len(filter_list(DATA, [['foo', '^', 'foo']])) == 2


def test__filter_list_ends():
    assert len(filter_list(DATA, [['foo', '$', '_']])) == 1


def test__filter_list_regex_begins():
    assert len(filter_list(DATA, [['foo', '~', '^foo']])) == 2


def test__filter_list_regex_contains():
    assert len(filter_list(DATA, [['foo', '~', '.*foo.*']])) == 3


def test__filter_list_gt():
    assert len(filter_list(DATA, [['number', '>', 1]])) == 2


def test__filter_list_gte():
    assert len(filter_list(DATA, [['number', '>=', 1]])) == 3


def test__filter_list_lt():
    assert len(filter_list(DATA, [['number', '<', 3]])) == 2


def test__filter_list_lte():
    assert len(filter_list(DATA, [['number', '<=', 3]])) == 3


def test__filter_list_in():
    assert len(filter_list(DATA, [['number', 'in', [1, 3]]])) == 2


def test__filter_list_nin():
    assert len(filter_list(DATA, [['number', 'nin', [1, 3]]])) == 1


def test__filter_list_rin():
    assert len(filter_list(DATA, [['list', 'rin', 1]])) == 1


def test__filter_list_rnin():
    assert len(filter_list(DATA, [['list', 'rnin', 1]])) == 2


def test__filter_list_OR_eq1():
    assert len(filter_list(DATA, [['OR', [
        ['number', '=', 1],
        ['number', '=', 200],
    ]]])) == 1


def test__filter_list_OR_eq2():
    assert len(filter_list(DATA, [['OR', [
        ['number', '=', 1],
        ['number', '=', 2],
    ]]])) == 2


def test__filter_list_nested_dict():
    assert len(filter_list(COMPLEX_DATA, [['Authentication.status', '=', 'NT_STATUS_OK']])) == 1


def test__filter_list_option_get():
    assert isinstance(filter_list(DATA, [], {'get': True}), dict)


def test__filter_list_option_get_and_order_by():
    assert filter_list(DATA, [], {'get': True, 'order_by': ['-number']})['foo'] == '_foo_'


def test__filter_list_option_order_by():
    for idx, entry in enumerate(filter_list(DATA, [], {'order_by': ['number']})):
        assert entry['number'] == idx + 1


def test__filter_list_option_order_by_reverse():
    for idx, entry in enumerate(filter_list(DATA, [], {'order_by': ['-number']})):
        assert entry['number'] == 3 - idx


def test__filter_list_option_select():
    for entry in filter_list(DATA, [], {'select': ['foo']}):
        assert list(entry.keys()) == ['foo']
