from logging import getLogger

from middlewared.plugins.enclosure_.enums import ElementType, JbofModels
from middlewared.plugins.enclosure_.jbof.utils import (fake_jbof_enclosure,
                                                       map_cooling,
                                                       map_power_supplies,
                                                       map_temperature_sensors,
                                                       map_voltage_sensors)
from middlewared.plugins.jbof.functions import get_sys_class_nvme

ES24N_EXPECTED_URI = '/redfish/v1/Chassis/2U24'
LOGGER = getLogger(__name__)


async def map_es24n(model, rclient, uri):
    data = {}
    urls = {'Drives': f'{uri}/Drives?$expand=*',
            'PowerSubsystem': f'{uri}/PowerSubsystem?$expand=*($levels=2)',
            'Sensors': f'{uri}/Sensors?$expand=*',
            'ThermalSubsystem': f'{uri}/ThermalSubsystem?$expand=*($levels=2)'
            }
    try:
        # Unfortunately the ES24n response doesn't lend itself it issuing a single query.
        #
        # Furthermore, experiments have shown that executing the queries in series
        # is just as fast as executing in parallel, so we'll do the former here for
        # simplicity.
        for key, uri2 in urls.items():
            info = await rclient.get(uri2)
            if not info:
                LOGGER.error('Unexpected failure fetching %r info', key)
                return
            data[key] = info
    except Exception:
        LOGGER.error('Unexpected failure enumerating all enclosure info', exc_info=True)
        return
    return do_map_es24n(model, rclient.uuid, data)


def do_map_es24n(model, uuid, data):
    #
    # Drives
    #
    try:
        all_disks = data['Drives']
    except KeyError:
        LOGGER.error('Unexpected failure extracting all disk info', exc_info=True)
        return

    num_of_slots = len(all_disks['Members'])
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

    elements = {}
    if psus := map_power_supplies(data):
        elements[ElementType.POWER_SUPPLY.value] = psus
    if cooling := map_cooling(data):
        elements[ElementType.COOLING.value] = cooling
    if temperature := map_temperature_sensors(data):
        elements[ElementType.TEMPERATURE_SENSORS.value] = temperature
    if voltage := map_voltage_sensors(data):
        elements[ElementType.VOLTAGE_SENSOR.value] = voltage
    # No Current Sensors reported

    return fake_jbof_enclosure(model, uuid, num_of_slots, mapped, ui_info, elements)


async def is_this_an_es24n(rclient):
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
    expected_uri = ES24N_EXPECTED_URI
    expected_model = JbofModels.ES24N.value
    try:
        info = await rclient.get(expected_uri)
        if info:
            found_model = info.get('Model', '').lower()
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
