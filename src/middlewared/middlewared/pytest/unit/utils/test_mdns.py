import pytest

from middlewared.utils import mdns


def test__dev_info():
    data = mdns.generate_avahi_srv_record(
        'DEV_INFO', txt_records=[f'model={mdns.DevType.MACPRORACK}']
    )
    parsed = mdns.parse_srv_record_data(data)[0]

    assert parsed.get('srv') == mdns.ServiceType.DEV_INFO.value[0]
    assert parsed.get('port') == mdns.ServiceType.DEV_INFO.value[1]
    assert parsed.get('txt_records') == [f'model={mdns.DevType.MACPRORACK}']


def test__smb():
    data = mdns.generate_avahi_srv_record('SMB')
    parsed = mdns.parse_srv_record_data(data)[0]

    assert parsed.get('srv') == mdns.ServiceType.SMB.value[0]
    assert parsed.get('port') == mdns.ServiceType.SMB.value[1]


def test__http():
    data = mdns.generate_avahi_srv_record('HTTP', custom_port='8080')
    parsed = mdns.parse_srv_record_data(data)[0]

    assert parsed.get('srv') == mdns.ServiceType.HTTP.value[0]
    assert parsed.get('port') == 8080


@pytest.mark.parametrize("srv,port,ifindex,txtrecord", [
    ('_ftp._tcp.', 21, None, None),
    ('_afpovertcp._tcp.', 548, None, None),
    ('_nfs._tcp.', 2048, [2, 3], ['path=/mnt/tank', 'path=/mnt/dozer']),
])
def test__custom(srv, port, ifindex, txtrecord):
    data = mdns.generate_avahi_srv_record(
        'CUSTOM',
        interface_indexes=ifindex,
        custom_service_type=srv,
        custom_port=port,
        txt_records=txtrecord
    )
    parsed = mdns.parse_srv_record_data(data)

    expected_txt = txtrecord or []
    ifindexes = ifindex or []

    for idx, ifidx in enumerate(ifindexes):
        assert parsed[idx].get('srv') == srv
        assert parsed[idx].get('port') == port
        assert parsed[idx].get('interface') == ifidx
        assert parsed[idx].get('txt_records') == expected_txt, str(parsed)
