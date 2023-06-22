from pathlib import Path

from middlewared.service import Service
from middlewared.service_exception import ValidationError
from middlewared.schema import accepts, returns, Dict, Str
from middlewared.utils.functools import cache


class HardwareCpuService(Service):

    class Config:
        namespace = 'hardware.cpu'
        cli_namespace = 'system.hardware.cpu'

    @accepts()
    @returns(Dict('governor', additional_attrs=True))
    @cache
    def available_governors(self):
        """Return available cpu governors"""
        try:
            with open('/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors') as f:
                return {i: i for i in f.read().split()}
        except FileNotFoundError:
            # doesn't support changing governor
            return dict()

    @accepts()
    @returns(Str('governor'))
    def current_governor(self):
        """Returns currently set cpu governor"""
        try:
            with open('/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor') as f:
                return f.read().strip()
        except FileNotFoundError:
            # doesn't support changing governor
            return

    @accepts(Str('governor', required=True))
    @returns()
    def set_governor(self, governor):
        """Set the cpu governor to `governor` on all cpus"""
        curr_gov = sef.current_governor()
        if curr_gov is None:
            raise ValidationError('hardware.cpu.governor', 'Changing cpu governor is not supported')
        elif curr_gov == governor:
            # current governor is already set to what is being requested
            return
        elif governor not in self.available_governors():
            raise ValidationError('hardware.cpu.governor', f'{governor} is not available')

        for i in Path('/sys/devices/system/cpu').iterdir():
            if i.is_dir() and i.name.startswith('cpu'):
                cpug = (i / 'cpufreq/scaling_governor')
                if cpug.exists():
                    cpug.write_text(governor)
