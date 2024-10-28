import contextlib
from time import sleep

from middlewared.test.integration.utils import call


@contextlib.contextmanager
def initiator(comment='Default initiator', initiators=[]):
    payload = {
        'comment': comment,
        'initiators': initiators,
    }
    initiator_config = call('iscsi.initiator.create', payload)

    try:
        yield initiator_config
    finally:
        call('iscsi.initiator.delete', initiator_config['id'])


@contextlib.contextmanager
def portal(listen=[{'ip': '0.0.0.0'}], comment='Default portal', discovery_authmethod='NONE'):
    payload = {
        'listen': listen,
        'comment': comment,
        'discovery_authmethod': discovery_authmethod
    }
    portal_config = call('iscsi.portal.create', payload)

    try:
        yield portal_config
    finally:
        call('iscsi.portal.delete', portal_config['id'])


@contextlib.contextmanager
def initiator_portal():
    with initiator() as initiator_config:
        with portal() as portal_config:
            yield {
                'initiator': initiator_config,
                'portal': portal_config,
            }


@contextlib.contextmanager
def alua_enabled(delay=10):
    payload = {'alua': True}
    call('iscsi.global.update', payload)
    if delay:
        sleep(delay)
        call('iscsi.alua.wait_for_alua_settled', 5, 8)
    try:
        yield
    finally:
        payload = {'alua': False}
        call('iscsi.global.update', payload)
        if delay:
            sleep(delay)


@contextlib.contextmanager
def target(target_name, groups, alias=None):
    payload = {
        'name': target_name,
        'groups': groups,
    }
    if alias:
        payload.update({'alias': alias})
    target_config = call('iscsi.target.create', payload)

    try:
        yield target_config
    finally:
        call('iscsi.target.delete', target_config['id'], True)


@contextlib.contextmanager
def zvol_extent(zvol, extent_name):
    payload = {
        'type': 'DISK',
        'disk': f'zvol/{zvol}',
        'name': extent_name,
    }
    config = call('iscsi.extent.create', payload)
    try:
        yield config
    finally:
        call('iscsi.extent.delete', config['id'], True, True)


@contextlib.contextmanager
def target_extent_associate(target_id, extent_id, lun_id=0):
    alua_enabled = call('iscsi.global.alua_enabled')
    payload = {
        'target': target_id,
        'lunid': lun_id,
        'extent': extent_id
    }
    associate_config = call('iscsi.targetextent.create', payload)
    if alua_enabled:
        # Give a little time for the STANDBY target to surface
        sleep(2)

    try:
        yield associate_config
    finally:
        call('iscsi.targetextent.delete', associate_config['id'], True)
    if alua_enabled:
        sleep(2)


def _extract_luns(rl):
    """
    Return a list of LUNs.

    :param rl: a ReportLuns instance (response)
    :return result a list of int LUNIDs

    Currently the results from pyscsi.ReportLuns.unmarshall_datain are (a) subject
    to change & (b) somewhat lacking for our purposes.  Therefore we will parse
    the datain here in a manner more useful for us.
    """
    result = []
    # First 4 bytes are LUN LIST LENGTH
    lun_list_length = int.from_bytes(rl.datain[:4], "big")
    # Next 4 Bytes are RESERVED
    # Remaining bytes are LUNS (8 bytes each)
    luns = rl.datain[8:]
    assert len(luns) >= lun_list_length
    for i in range(0, lun_list_length, 8):
        lun = luns[i: i + 8]
        addr_method = (lun[0] >> 6) & 0x3
        assert addr_method == 0, f"Unsupported Address Method: {addr_method}"
        if addr_method == 0:
            # peripheral device addressing method, don't care about bus.
            result.append(lun[1])
    return result


def verify_luns(s, expected_luns):
    """
    Verify that the supplied SCSI has the expected LUNs.

    :param s: a pyscsi.SCSI instance
    :param expected_luns: a list of int LUNIDs
    """
    s.testunitready()
    # REPORT LUNS
    rl = s.reportluns()
    data = rl.result
    assert isinstance(data, dict), data
    assert 'luns' in data, data
    # Check that we only have LUN 0
    luns = _extract_luns(rl)
    assert len(luns) == len(expected_luns), luns
    assert set(luns) == set(expected_luns), luns


def read_capacity16(s):
    # READ CAPACITY (16)
    data = s.readcapacity16().result
    return (data['returned_lba'] + 1 - data['lowest_aligned_lba']) * data['block_length']


def verify_capacity(s, expected_capacity):
    """
    Verify that the supplied SCSI has the expected capacity.

    :param s: a pyscsi.SCSI instance
    :param expected_capacity: an int
    """
    s.testunitready()
    returned_size = read_capacity16(s)
    assert returned_size == expected_capacity


def TUR(s):
    """
    Perform a TEST UNIT READY.

    :param s: a pyscsi.SCSI instance
    """
    s.testunitready()


def _serial_number(s):
    x = s.inquiry(evpd=1, page_code=0x80)
    return x.result['unit_serial_number'].decode('utf-8')


def _device_identification(s):
    result = {}
    x = s.inquiry(evpd=1, page_code=0x83)
    for desc in x.result['designator_descriptors']:
        if desc['designator_type'] == 4:
            result['relative_target_port_identifier'] = desc['designator']['relative_port']
        if desc['designator_type'] == 5:
            result['target_port_group'] = desc['designator']['target_portal_group']
        if desc['designator_type'] == 3 and desc['designator']['naa'] == 6:
            items = (desc['designator']['naa'],
                     desc['designator']['ieee_company_id'],
                     desc['designator']['vendor_specific_identifier'],
                     desc['designator']['vendor_specific_identifier_extension']
                     )
            result['naa'] = "0x{:01x}{:06x}{:09x}{:016x}".format(*items)
    return result


def verify_ha_device_identification(s, naa, relative_target_port_identifier, target_port_group):
    x = _device_identification(s)
    assert x['naa'] == naa, x
    assert x['relative_target_port_identifier'] == relative_target_port_identifier, x
    assert x['target_port_group'] == target_port_group, x


def verify_ha_inquiry(s, serial_number, naa, tpgs=0,
                      vendor='TrueNAS', product_id='iSCSI Disk'):
    """
    Verify that the supplied SCSI has the expected INQUIRY response.

    :param s: a pyscsi.SCSI instance
    """
    TUR(s)
    inq = s.inquiry().result
    assert inq['t10_vendor_identification'].decode('utf-8').startswith(vendor)
    assert inq['product_identification'].decode('utf-8').startswith(product_id)
    if tpgs is not None:
        assert inq['tpgs'] == tpgs
    assert serial_number == _serial_number(s)
    assert naa == _device_identification(s)['naa']
