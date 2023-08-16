from bases.FrameworkServices.SimpleService import SimpleService
from collections import defaultdict
from copy import deepcopy
from third_party import lm_sensors as sensors

from middlewared.utils.cpu import amd_cpu_temperatures, generic_cpu_temperatures, cpu_info


CPU_TEMPERATURE_FEAT_TYPE = 2


ORDER = [
    'temperatures',
]

# This is a prototype of chart definition which is used to dynamically create self.definitions
CHARTS = {
    'temperatures': {
        'options': [None, 'Temperature', 'Celsius', 'temperature', 'sensors.temperature', 'line'],
        'lines': []
    }
}


def cpu_temperatures(cpu_metrics):
    if amd_metrics := cpu_metrics.get('k10temp-pci-00c3'):
        return amd_cpu_temperatures(amd_metrics)
    return generic_cpu_temperatures(cpu_metrics)


class Service(SimpleService):
    def __init__(self, configuration=None, name=None):
        SimpleService.__init__(self, configuration=configuration, name=name)
        self.order = deepcopy(ORDER)
        self.definitions = deepcopy(CHARTS)

    def get_data(self):
        seen, data, cpu_data = dict(), dict(), defaultdict(dict)
        try:
            for chip in sensors.ChipIterator():
                chip_name = sensors.chip_snprintf_name(chip)
                seen[chip_name] = defaultdict(list)
                if not any(chip_name.startswith(cpu_chip) for cpu_chip in ('k10temp-pci-00c3', 'coretemp-isa')):
                    continue

                cpu_d = {}
                for feat in sensors.FeatureIterator(chip):
                    if feat.type != CPU_TEMPERATURE_FEAT_TYPE:
                        continue

                    feat_name = str(feat.name.decode())
                    feat_label = sensors.get_label(chip, feat)
                    sub_feat = next(sensors.SubFeatureIterator(chip, feat))  # current value

                    if not sub_feat:
                        continue

                    try:
                        v = sensors.get_value(chip, sub_feat.number)
                    except sensors.SensorsError:
                        continue

                    if v is None:
                        continue

                    cpu_d[f'{chip_name}_{feat_name}'] = {'name': feat_label, 'value': v}

                cpu_data[chip_name] = cpu_d
        except sensors.SensorsError as error:
            self.error(error)
            return None

        data = {}
        for core, temp in cpu_temperatures(cpu_data).items():
            data[str(core)] = temp

        return data or {str(i): 0 for i in range(cpu_info()['core_count'])}

    def check(self):
        try:
            sensors.init()
        except sensors.SensorsError as error:
            self.error(error)
            return False

        data = self.get_data()
        for i in data:
            self.definitions['temperatures']['lines'].append([str(i)])

        return bool(data)
