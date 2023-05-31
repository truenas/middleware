from pathlib import Path

from middlewared.service import Service
from middlewared.schema import accepts, returns, Dict


class HardwareMemoryService(Service):

    class Config:
        namespace = 'hardware.memory'
        cli_namespace = 'system.hardware.memory'

    @accepts()
    @returns(Dict('mem_ctrl', additional_attrs=True))
    def error_info(self):
        results = {}
        mc_path = Path('/sys/devices/system/edac/mc')
        if not mc_path.exists():
            return results

        dimm_or_rank = 'dimm'
        mc_idx = 0
        for mc in filter(lambda x: x.is_dir() and x.name.startswith('mc'), mc_path.iterdir()):
            mc_info = {mc.name: {}}
            if mc_idx == 0 and not (mc / f'{dimm_or_rank}{mc_idx}').exists():
                # AMD systems use "rank" as top-level dir while Intel uses dimm
                dimm_or_rank = 'rank'

            # top-level memory controller information
            for key, _file in (
                ('corrected_errors', 'ce_count'),
                ('uncorrected_errors', 'ue_count'),
                ('corrected_errors_with_no_dimm_info', 'ce_noinfo_count'),
                ('uncorrected_errors_with_no_dimm_info', 'ue_noinfo_count'),
            ):
                try:
                    value = int((mc / _file).read_text().strip())
                except (FileNotFoundError, ValueError):
                    value = None

                mc_info[mc.name].update({key: value})

            # specific dimm module memory information
            for dimm in filter(lambda x: x.is_dir() and x.name.startswith(dimm_or_rank), mc.iterdir()):
                # looks like /sys/devices/edac/mc0/dimm(or rank){0/1/2}
                mc_info[mc.name][dimm.name] = {}
                for key, _file in (
                    ('corrected_errors', 'dimm_ce_count'),
                    ('uncorrected_errors', 'dimm_ue_count'),
                ):
                    try:
                        value = int((dimm / _file).read_text().strip())
                    except (FileNotFoundError, ValueError):
                        value = None

                    mc_info[mc.name][dimm.name].update({key: value})

            mc_idx += 1
            results.update(mc_info)

        return results
