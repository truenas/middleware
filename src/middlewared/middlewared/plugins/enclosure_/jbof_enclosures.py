from logging import getLogger

from middlewared.plugins.enclosure_.enums import JbofModels
from middlewared.plugins.enclosure_.slot_mappings import get_jbof_slot_info
from middlewared.plugins.jbof.functions import get_sys_class_nvme
from middlewared.plugins.jbof.redfish import RedfishClient, InvalidCredentialsError

LOGGER = getLogger(__name__)


def fake_jbof_enclosure(model, uuid, num_of_slots, mapped, ui_info):
    """This function takes the nvme devices that been mapped
    to their respective slots and then creates a "fake" enclosure
    device that matches (similarly) to what our real enclosure
    mapping code does (get_ses_enclosures()). It's _VERY_ important
    that the keys in the `fake_enclosure` dictionary exist because
    our generic enclosure mapping logic expects certain top-level
    keys.

    Furthermore, we generate DMI (SMBIOS) information for this
    "fake" enclosure because our enclosure mapping logic has to have
    a guaranteed unique key for each enclosure so it can properly
    map the disks accordingly
    """
    # TODO: The `fake_enclosure` object should be removed from this
    # function and should be generated by the
    # `plugins.enclosure_/enclosure_class.py:Enclosure` class so we
    # can get rid of duplicate logic in this module and in that class
    fake_enclosure = {
        'id': uuid,
        'dmi': uuid,
        'model': model,
        'should_ignore': False,
        'sg': None,
        'bsg': None,
        'name': f'{model} JBoF Enclosure',
        'controller': False,
        'status': ['OK'],
        'elements': {'Array Device Slot': {}}
    }
    disks_map = get_jbof_slot_info(model)
    if not disks_map:
        fake_enclosure['should_ignore'] = True
        return [fake_enclosure]

    fake_enclosure.update(ui_info)

    for slot in range(1, num_of_slots + 1):
        device = mapped.get(slot, None)
        # the `value_raw` variables represent the
        # value they would have if a device was
        # inserted into a proper SES device (or not).
        # Since this is NVMe (which deals with PCIe)
        # that paradigm doesn't exist per se but we're
        # "faking" a SES device, hence the hex values.
        # The `status` variables use same logic.
        if device is not None:
            status = 'OK'
            value_raw = 0x1000000
        else:
            status = 'Not installed'
            value_raw = 0x5000000

        mapped_slot = disks_map['versions']['DEFAULT']['model'][model][slot]['mapped_slot']
        fake_enclosure['elements']['Array Device Slot'][mapped_slot] = {
            'descriptor': f'Disk #{slot}',
            'status': status,
            'value': None,
            'value_raw': value_raw,
            'dev': device,
            'original': {
                'enclosure_id': uuid,
                'enclosure_sg': None,
                'enclosure_bsg': None,
                'descriptor': f'slot{slot}',
                'slot': slot,
            }
        }

    return [fake_enclosure]


def map_es24n(model, rclient, uri):
    try:
        all_disks = rclient.get(f'{uri}/Drives?$expand=*').json()
    except Exception:
        LOGGER.error('Unexpected failure enumerating all disk info', exc_info=True)
        return

    num_of_slots = all_disks['Members@odata.count']
    ui_info = {
        'rackmount': True,
        'top_loaded': False,
        'front_slots': num_of_slots,
        'rear_slots': 0,
        'internal_slots': 0
    }
    mounted_disks = {
        v['serial']: (k, v) for k, v in get_sys_class_nvme().items()
        if v['serial'] and v['transport_protocol'] == 'rdma'
    }
    mapped = dict()
    for disk in all_disks['Members']:
        slot = disk.get('Id', '')
        if not slot or not slot.isdigit():
            # shouldn't happen but need to catch edge-case
            continue
        else:
            slot = int(slot)

        state = disk.get('Status', {}).get('State')
        if not state or state == 'Absent':
            mapped[slot] = None
            continue

        sn = disk.get('SerialNumber')
        if not sn:
            mapped[slot] = None
            continue

        if found := mounted_disks.get(sn):
            try:
                # we expect namespace 1 for the device (i.e. nvme1n1)
                idx = found[1]['namespaces'].index(f'{found[0]}n1')
                mapped[slot] = found[1]['namespaces'][idx]
            except ValueError:
                mapped[slot] = None
        else:
            mapped[slot] = None

    return fake_jbof_enclosure(model, rclient.uuid, num_of_slots, mapped, ui_info)


def get_redfish_clients(jbofs):
    clients = dict()
    for jbof in jbofs:
        try:
            rclient = RedfishClient(
                f'https://{jbof["mgmt_ip1"]}', jbof['mgmt_username'], jbof['mgmt_password']
            )
            clients[jbof['mgmt_ip1']] = rclient
        except InvalidCredentialsError:
            LOGGER.error('Failed to login to redfish ip %r', jbof['mgmt_ip1'])
        except Exception:
            LOGGER.error('Unexpected failure creating redfish client object', exc_info=True)

    return clients


def is_this_an_es24n(rclient):
    """At time of writing, we've discovered that OEM of the ES24N
    does not give us predictable model names. Seems to be random
    which is unfortunate but there isn't much we can do about it
    at the moment. We know what the URI _should_ be for this
    platform and we _thought_ we knew what the model should be so
    we'll hard-code these values and check for the specific URI
    and then check if the model at the URI at least has some
    semblance of an ES24N"""
    # FIXME: This function shouldn't exist and the OEM should fix
    # this at some point. When they do (hopefully) fix the model,
    # remove this function
    expected_uri = '/redfish/v1/Chassis/2U24'
    expected_model = JbofModels.ES24N.value
    try:
        info = rclient.get(expected_uri)
        if info.ok:
            found_model = info.json().get('Model', '').lower()
            eml = expected_model.lower()
            if any((
                eml in found_model,
                found_model.startswith(eml),
                found_model.startswith(eml[:-1])
            )):
                # 1. the model string is inside the found model
                # 2. or the model string startswith what we expect
                # 3. or the model string startswith what we expect
                #   with the exception of the last character
                #   (The reason why we chop off last character is
                #   because internal conversation concluded that the
                #   last digit coorrelates to "generation" so we're
                #   going to be extra lenient and ignore it)
                return JbofModels.ES24N.name, expected_uri
    except Exception:
        LOGGER.error('Unexpected failure determining if this is an ES24N', exc_info=True)

    return None, None


def get_enclosure_model(rclient):
    model = uri = None
    try:
        chassis = rclient.chassis()
    except Exception:
        LOGGER.error('Unexpected failure enumerating chassis info', exc_info=True)
        return model, uri

    model, uri = is_this_an_es24n(rclient)
    if all((model, uri)):
        return model, uri

    try:
        for _, uri in chassis.items():
            info = rclient.get(uri)
            if info.ok:
                try:
                    model = JbofModels(info.json().get('Model', '')).name
                    return model, uri
                except ValueError:
                    # Using parenthesis on the enum checks the string BY VALUE
                    # and NOT BY NAME. If you were to use square brackets [],
                    # then a KeyError will be raised.
                    continue
    except Exception:
        LOGGER.error('Unexpected failure determing enclosure model', exc_info=True)

    return model, uri


def map_jbof(jbof_query):
    result = list()
    for mgmt_ip, rclient in filter(lambda x: x[1] is not None, get_redfish_clients(jbof_query).items()):
        model, uri = get_enclosure_model(rclient)
        if model == JbofModels.ES24N.name and (mapped := map_es24n(model, rclient, uri)):
            result.extend(mapped)

    return result
