from unittest.mock import patch, mock_open

from middlewared.plugins.reporting.netdata.utils import NETDATA_UPDATE_EVERY
from middlewared.plugins.reporting.realtime_reporting import (
    get_arc_stats, get_cpu_stats, get_disk_stats, get_interface_stats, get_memory_info, get_pool_stats
)
from middlewared.plugins.reporting.realtime_reporting.utils import normalize_value, safely_retrieve_dimension


NETDATA_ALL_METRICS = {
    'cputemp.temperatures': {
        'name': 'cputemp.temperatures',
        'family': 'temperature',
        'context': 'sensors.temperature',
        'units': 'Celsius',
        'last_updated': 1737452189,
        'dimensions': {
            'cpu0': {
                'name': 'cpu0',
                'value': 22
            },
            'cpu1': {
                'name': 'cpu1',
                'value': 21
            },
            'cpu2': {
                'name': 'cpu2',
                'value': 10
            },
            'cpu': {
                'name': 'cpu',
                'value': 40
            }
        }
    },
    'truenas_cpu_usage.cpu': {
        'name': 'truenas_cpu_usage.cpu',
        'family': 'cpu.usage',
        'context': 'Cpu usage',
        'units': 'CPU USAGE%',
        'last_updated': 1737452189,
        'dimensions': {
            'cpu': {
                'name': 'cpu',
                'value': 4
            },
            'cpu0': {
                'name': 'cpu0',
                'value': 2
            },
            'cpu1': {
                'name': 'cpu1',
                'value': 3
            },
            'cpu2': {
                'name': 'cpu2',
                'value': 4
            }
        }
    },
    'truenas_meminfo.total': {
        'name': 'truenas_meminfo.total',
        'family': 'total',
        'context': 'Total memory',
        'units': 'Bytes',
        'last_updated': 1732714553,
        'dimensions': {
            'total': {
                'name': 'total',
                'value': 6119460864
            }
        }
    },

    'net.enp1s0': {
        'name': 'net.enp1s0',
        'family': 'enp1s0',
        'context': 'net.net',
        'units': 'kilobits/s',
        'last_updated': 1691150349,
        'dimensions': {
            'received': {
                'name': 'received',
                'value': 4.0394645
            },
            'sent': {
                'name': 'sent',
                'value': -5.8688266
            }
        }
    },
    'net_speed.enp1s0': {
        'name': 'net_speed.enp1s0',
        'family': 'enp1s0',
        'context': 'net.speed',
        'units': 'kilobits/s',
        'last_updated': 1691150349,
        'dimensions': {
            'speed': {
                'name': 'speed',
                'value': 0
            }
        }
    },
    'net_operstate.enp1s0': {
        'name': 'net_operstate.enp1s0',
        'family': 'enp1s0',
        'context': 'net.operstate',
        'units': 'state',
        'last_updated': 1691150349,
        'dimensions': {
            'up': {
                'name': 'up',
                'value': 1
            },
            'down': {
                'name': 'down',
                'value': 0
            },
            'notpresent': {
                'name': 'notpresent',
                'value': 0
            },
            'lowerlayerdown': {
                'name': 'lowerlayerdown',
                'value': 0
            },
            'testing': {
                'name': 'testing',
                'value': 0
            },
            'dormant': {
                'name': 'dormant',
                'value': 0
            },
            'unknown': {
                'name': 'unknown',
                'value': 0
            }
        }
    },
    'truenas_disk_stats.io.{devicename}sda': {
        'name': 'disk.sda',
        'family': 'vda',
        'context': 'disk.io',
        'units': 'KiB/s',
        'last_updated': 1691150349,
        'dimensions': {
            'reads': {
                'name': 'reads',
                'value': 10
            },
            'writes': {
                'name': 'writes',
                'value': 20
            }
        }
    },
    'truenas_disk_stats.ops.{devicename}sda': {
        'name': 'disk_ops.sda',
        'family': 'vda',
        'context': 'disk.ops',
        'units': 'operations/s',
        'last_updated': 1691150349,
        'dimensions': {
            'reads': {
                'name': 'reads',
                'value': 2
            },
            'writes': {
                'name': 'writes',
                'value': 3
            }
        }
    },
    'truenas_disk_stats.busy.{devicename}sda': {
        'name': 'disk_busy.sda',
        'family': 'vda',
        'context': 'disk.busy',
        'units': 'milliseconds',
        'last_updated': 1691150349,
        'dimensions': {
            'busy': {
                'name': 'busy',
                'value': 0
            }
        }
    },
    'truenas_disk_stats.io.{devicename}sdb': {
        'name': 'disk.sdb',
        'family': 'vdb',
        'context': 'disk.io',
        'units': 'KiB/s',
        'last_updated': 1691150349,
        'dimensions': {
            'reads': {
                'name': 'reads',
                'value': 3
            },
            'writes': {
                'name': 'writes',
                'value': 3
            }
        }
    },
    'truenas_disk_stats.ops.{devicename}sdb': {
        'name': 'disk_ops.sdb',
        'family': 'vdb',
        'context': 'disk.ops',
        'units': 'operations/s',
        'last_updated': 1691150349,
        'dimensions': {
            'reads': {
                'name': 'reads',
                'value': 1
            },
            'writes': {
                'name': 'writes',
                'value': 1
            }
        }
    },
    'truenas_disk_stats.busy.{devicename}sdb': {
        'name': 'disk_busy.sdb',
        'family': 'vdb',
        'context': 'disk.busy',
        'units': 'milliseconds',
        'last_updated': 1691150349,
        'dimensions': {
            'busy': {
                'name': 'busy',
                'value': 0
            }
        }
    },
    'truenas_disk_stats.io.{devicename}sdc': {
        'name': 'disk.sdc',
        'family': 'vdc',
        'context': 'disk.io',
        'units': 'KiB/s',
        'last_updated': 1691150349,
        'dimensions': {
            'reads': {
                'name': 'reads',
                'value': 3
            },
            'writes': {
                'name': 'writes',
                'value': 4
            }
        }
    },

    'truenas_disk_stats.ops.{devicename}sdc': {
        'name': 'disk_ops.sdc',
        'family': 'vdc',
        'context': 'disk.ops',
        'units': 'operations/s',
        'last_updated': 1691150349,
        'dimensions': {
            'reads': {
                'name': 'reads',
                'value': 6
            },
            'writes': {
                'name': 'writes',
                'value': 6
            }
        }
    },
    'truenas_disk_stats.busy.{devicename}sdc': {
        'name': 'disk_busy.sdc',
        'family': 'vdc',
        'context': 'disk.busy',
        'units': 'milliseconds',
        'last_updated': 1691150349,
        'dimensions': {
            'busy': {
                'name': 'busy',
                'value': 0
            }
        }
    },
    'truenas_disk_stats.io.{devicename}sdd': {
        'name': 'disk.sdd',
        'family': 'vdd',
        'context': 'disk.io',
        'units': 'KiB/s',
        'last_updated': 1691150349,
        'dimensions': {
            'reads': {
                'name': 'reads',
                'value': 2
            },
            'writes': {
                'name': 'writes',
                'value': 3
            }
        }
    },
    'truenas_disk_stats.ops.{devicename}sdd': {
        'name': 'disk_ops.sdd',
        'family': 'vdd',
        'context': 'disk.ops',
        'units': 'operations/s',
        'last_updated': 1691150349,
        'dimensions': {
            'reads': {
                'name': 'reads',
                'value': 1
            },
            'writes': {
                'name': 'writes',
                'value': 1
            }
        }
    },
    'truenas_disk_stats.busy.{devicename}sdd': {
        'name': 'disk_busy.sdd',
        'family': 'vdd',
        'context': 'disk.busy',
        'units': 'milliseconds',
        'last_updated': 1691150349,
        'dimensions': {
            'busy': {
                'name': 'busy',
                'value': 0
            }
        }
    },
    'truenas_arcstats.free': {
        'name': 'truenas_arcstats.free',
        'family': 'free',
        'context': 'ARC free memory',
        'units': 'Bytes',
        'last_updated': 1730482785,
        'dimensions': {
            'free': {
                'name': 'free',
                'value': 2432081920
            }
        }
    },
    'truenas_arcstats.avail': {
        'name': 'truenas_arcstats.avail',
        'family': 'avail',
        'context': 'ARC available memory',
        'units': 'Bytes',
        'last_updated': 1730482785,
        'dimensions': {
            'avail': {
                'name': 'avail',
                'value': 2165650048
            }
        }
    },
    'truenas_arcstats.size': {
        'name': 'truenas_arcstats.size',
        'family': 'size',
        'context': 'ARC size',
        'units': 'Bytes',
        'last_updated': 1730482785,
        'dimensions': {
            'size': {
                'name': 'size',
                'value': 1371942144
            }
        }
    },
    'truenas_arcstats.dread': {
        'name': 'truenas_arcstats.dread',
        'family': 'dread',
        'context': 'Demand accesses per second',
        'units': 'dread/s',
        'last_updated': 1730482785,
        'dimensions': {
            'dread': {
                'name': 'dread',
                'value': 93.6866928
            }
        }
    },
    'truenas_arcstats.ddread': {
        'name': 'truenas_arcstats.ddread',
        'family': 'ddread',
        'context': 'Demand data accesses per second',
        'units': 'ddread/s',
        'last_updated': 1730482785,
        'dimensions': {
            'ddread': {
                'name': 'ddread',
                'value': 48.2190993
            }
        }
    },
    'truenas_arcstats.dmread': {
        'name': 'truenas_arcstats.dmread',
        'family': 'dmread',
        'context': 'Demand metadata accesses per second',
        'units': 'dmread/s',
        'last_updated': 1730482785,
        'dimensions': {
            'dmread': {
                'name': 'dmread',
                'value': 45.4620412
            }
        }
    },
    'truenas_arcstats.ddhit': {
        'name': 'truenas_arcstats.ddhit',
        'family': 'ddhit',
        'context': 'Demand data hits per second',
        'units': 'ddhit/s',
        'last_updated': 1730482785,
        'dimensions': {
            'ddhit': {
                'name': 'ddhit',
                'value': 48.2155335
            }
        }
    },
    'truenas_arcstats.ddioh': {
        'name': 'truenas_arcstats.ddioh',
        'family': 'ddioh',
        'context': 'Demand data I/O hits per second',
        'units': 'ddioh/s',
        'last_updated': 1730482785,
        'dimensions': {
            'ddioh': {
                'name': 'ddioh',
                'value': 0
            }
        }
    },
    'truenas_arcstats.ddmis': {
        'name': 'truenas_arcstats.ddmis',
        'family': 'ddmis',
        'context': 'Demand data misses per second',
        'units': 'ddmis/s',
        'last_updated': 1730482785,
        'dimensions': {
            'ddmis': {
                'name': 'ddmis',
                'value': 0
            }
        }
    },
    'truenas_arcstats.ddh_p': {
        'name': 'truenas_arcstats.ddh_p',
        'family': 'ddh',
        'context': 'Demand data hit percentage',
        'units': 'ddh%',
        'last_updated': 1730482785,
        'dimensions': {
            'ddh_p': {
                'name': 'ddh',
                'value': 0
            }
        }
    },
    'truenas_arcstats.ddi_p': {
        'name': 'truenas_arcstats.ddi_p',
        'family': 'ddi',
        'context': 'Demand data I/O hit percentage',
        'units': 'ddi%',
        'last_updated': 1730482785,
        'dimensions': {
            'ddi_p': {
                'name': 'ddi',
                'value': 0
            }
        }
    },
    'truenas_arcstats.ddm_p': {
        'name': 'truenas_arcstats.ddm_p',
        'family': 'ddm',
        'context': 'Demand data miss percentage',
        'units': 'ddm%',
        'last_updated': 1730482785,
        'dimensions': {
            'ddm_p': {
                'name': 'ddm',
                'value': 0
            }
        }
    },
    'truenas_arcstats.dmhit': {
        'name': 'truenas_arcstats.dmhit',
        'family': 'dmhit',
        'context': 'Demand metadata hits per second',
        'units': 'dmhit',
        'last_updated': 1730482785,
        'dimensions': {
            'dmhit': {
                'name': 'dmhit',
                'value': 45.4499775
            }
        }
    },
    'truenas_arcstats.dmioh': {
        'name': 'truenas_arcstats.dmioh',
        'family': 'dmioh',
        'context': 'Demand metadata I/O hits per second',
        'units': 'dmioh',
        'last_updated': 1730482785,
        'dimensions': {
            'dmioh': {
                'name': 'dmioh',
                'value': 0
            }
        }
    },
    'truenas_arcstats.dmmis': {
        'name': 'truenas_arcstats.dmmis',
        'family': 'dmmis',
        'context': 'Demand metadata misses per second',
        'units': 'dmmis',
        'last_updated': 1730482785,
        'dimensions': {
            'dmmis': {
                'name': 'dmmis',
                'value': 0
            }
        }
    },
    'truenas_arcstats.dmh_p': {
        'name': 'truenas_arcstats.dmh_p',
        'family': 'dmh',
        'context': 'Demand metadata hit percentage',
        'units': 'dmh%',
        'last_updated': 1730482785,
        'dimensions': {
            'dmh_p': {
                'name': 'dmh',
                'value': 0
            }
        }
    },
    'truenas_arcstats.dmi_p': {
        'name': 'truenas_arcstats.dmi_p',
        'family': 'dmi',
        'context': 'Demand metadata I/O hit percentage',
        'units': 'dmi%',
        'last_updated': 1730482785,
        'dimensions': {
            'dmi_p': {
                'name': 'dmi',
                'value': 0
            }
        }
    },
    'truenas_arcstats.dmm_p': {
        'name': 'truenas_arcstats.dmm_p',
        'family': 'dmm',
        'context': 'Demand metadata miss percentage',
        'units': 'dmm%',
        'last_updated': 1730482785,
        'dimensions': {
            'dmm_p': {
                'name': 'dmm',
                'value': 0
            }
        }
    },
    'truenas_arcstats.l2hits': {
        'name': 'truenas_arcstats.l2hits',
        'family': 'l2hits',
        'context': 'L2ARC hits per second',
        'units': 'l2hits',
        'last_updated': 1730482785,
        'dimensions': {
            'l2hits': {
                'name': 'l2hits',
                'value': 0
            }
        }
    },
    'truenas_arcstats.l2miss': {
        'name': 'truenas_arcstats.l2miss',
        'family': 'l2miss',
        'context': 'L2ARC misses per second',
        'units': 'l2miss',
        'last_updated': 1730482785,
        'dimensions': {
            'l2miss': {
                'name': 'l2miss',
                'value': 0
            }
        }
    },
    'truenas_arcstats.l2read': {
        'name': 'truenas_arcstats.l2read',
        'family': 'l2read',
        'context': 'Total L2ARC accesses per second',
        'units': 'l2read',
        'last_updated': 1730482785,
        'dimensions': {
            'l2read': {
                'name': 'l2read',
                'value': 0
            }
        }
    },
    'truenas_arcstats.l2hit_p': {
        'name': 'truenas_arcstats.l2hit_p',
        'family': 'l2hit',
        'context': 'L2ARC access hit percentage',
        'units': 'l2hit%',
        'last_updated': 1730482785,
        'dimensions': {
            'l2hit_p': {
                'name': 'l2hit',
                'value': 0
            }
        }
    },
    'truenas_arcstats.l2miss_p': {
        'name': 'truenas_arcstats.l2miss_p',
        'family': 'l2miss',
        'context': 'L2ARC access miss percentage',
        'units': 'l2miss%',
        'last_updated': 1730482785,
        'dimensions': {
            'l2miss_p': {
                'name': 'l2miss',
                'value': 0
            }
        }
    },
    'truenas_arcstats.l2bytes': {
        'name': 'truenas_arcstats.l2bytes',
        'family': 'l2bytes',
        'context': 'Bytes read per second from the L2ARC',
        'units': 'l2bytes',
        'last_updated': 1730482785,
        'dimensions': {
            'l2bytes': {
                'name': 'l2bytes',
                'value': 0
            }
        }
    },
    'truenas_arcstats.l2wbytes': {
        'name': 'truenas_arcstats.l2wbytes',
        'family': 'l2wbytes',
        'context': 'Bytes written per second to the L2ARC',
        'units': 'l2wbytes',
        'last_updated': 1730482785,
        'dimensions': {
            'l2wbytes': {
                'name': 'l2wbytes',
                'value': 0
            }
        }
    },
    'truenas_pool.usage': {
        'name': 'truenas_pool.usage',
        'family': 'pool.usage',
        'context': 'pool.usage',
        'units': 'bytes',
        'last_updated': 1741816789,
        'dimensions': {
            '11653691484309152344.available': {
                'name': 'available',
                'value': 15574065152
            },
            '11653691484309152344.used': {
                'name': 'used',
                'value': 4210708480
            },
            '11653691484309152344.total': {
                'name': 'total',
                'value': 19784773632
            },
            '14935745712721614601.available': {
                'name': 'available',
                'value': 6004465664
            },
            '14935745712721614601.used': {
                'name': 'used',
                'value': 14279315456
            },
            '14935745712721614601.total': {
                'name': 'total',
                'value': 20283781120
            }
        }
    },
}


def test_get_pool_stats():
    with patch('middlewared.plugins.reporting.realtime_reporting.pool.query_imported_fast_impl') as pool_imp:
        pool_imp.return_value = {
            '14935745712721614601': {
                'name': 'tank', 'state': 'ONLINE'
            },
            '11653691484309152344': {
                'name': 'boot-pool', 'state': 'ONLINE'
            }
        }

        pool_stats = get_pool_stats(NETDATA_ALL_METRICS)
        assert pool_stats['tank']['available'] == safely_retrieve_dimension(
            NETDATA_ALL_METRICS, 'truenas_pool.usage', '14935745712721614601.available'
        )
        assert pool_stats['tank']['used'] == safely_retrieve_dimension(
            NETDATA_ALL_METRICS, 'truenas_pool.usage', '14935745712721614601.used'
        )
        assert pool_stats['tank']['total'] == safely_retrieve_dimension(
            NETDATA_ALL_METRICS, 'truenas_pool.usage', '14935745712721614601.total'
        )
        assert pool_stats['boot-pool']['available'] == safely_retrieve_dimension(
            NETDATA_ALL_METRICS, 'truenas_pool.usage', '11653691484309152344.available'
        )
        assert pool_stats['boot-pool']['used'] == safely_retrieve_dimension(
            NETDATA_ALL_METRICS, 'truenas_pool.usage', '11653691484309152344.used'
        )
        assert pool_stats['boot-pool']['total'] == safely_retrieve_dimension(
            NETDATA_ALL_METRICS, 'truenas_pool.usage', '11653691484309152344.total'
        )



def test_arc_stats():
    arc_stats = get_arc_stats(NETDATA_ALL_METRICS)

    assert arc_stats['demand_accesses_per_second'] == normalize_value(
        safely_retrieve_dimension(NETDATA_ALL_METRICS, 'truenas_arcstats.dread', 'dread', 0)
    )
    assert arc_stats['demand_data_accesses_per_second'] == normalize_value(
        safely_retrieve_dimension(NETDATA_ALL_METRICS, 'truenas_arcstats.ddread', 'ddread', 0)
    )
    assert arc_stats['demand_metadata_accesses_per_second'] == normalize_value(
        safely_retrieve_dimension(NETDATA_ALL_METRICS, 'truenas_arcstats.dmread', 'dmread', 0)
    )
    assert arc_stats['demand_data_hits_per_second'] == normalize_value(
        safely_retrieve_dimension(NETDATA_ALL_METRICS, 'truenas_arcstats.ddhit', 'ddhit', 0)
    )
    assert arc_stats['demand_data_io_hits_per_second'] == normalize_value(
        safely_retrieve_dimension(NETDATA_ALL_METRICS, 'truenas_arcstats.ddioh', 'ddioh', 0)
    )
    assert arc_stats['demand_data_misses_per_second'] == normalize_value(
        safely_retrieve_dimension(NETDATA_ALL_METRICS, 'truenas_arcstats.ddmis', 'ddmis', 0)
    )
    assert arc_stats['demand_data_hit_percentage'] == normalize_value(
        safely_retrieve_dimension(NETDATA_ALL_METRICS, 'truenas_arcstats.ddh_p', 'ddh_p', 0)
    )
    assert arc_stats['demand_data_io_hit_percentage'] == normalize_value(
        safely_retrieve_dimension(NETDATA_ALL_METRICS, 'truenas_arcstats.ddi_p', 'ddi_p', 0)
    )
    assert arc_stats['demand_data_miss_percentage'] == normalize_value(
        safely_retrieve_dimension(NETDATA_ALL_METRICS, 'truenas_arcstats.ddm_p', 'ddm_p', 0)
    )
    assert arc_stats['demand_metadata_hits_per_second'] == normalize_value(
        safely_retrieve_dimension(NETDATA_ALL_METRICS, 'truenas_arcstats.dmhit', 'dmhit', 0)
    )
    assert arc_stats['demand_metadata_io_hits_per_second'] == normalize_value(
        safely_retrieve_dimension(NETDATA_ALL_METRICS, 'truenas_arcstats.dmioh', 'dmioh', 0)
    )
    assert arc_stats['demand_metadata_misses_per_second'] == normalize_value(
        safely_retrieve_dimension(NETDATA_ALL_METRICS, 'truenas_arcstats.dmmis', 'dmmis', 0)
    )
    assert arc_stats['demand_metadata_hit_percentage'] == normalize_value(
        safely_retrieve_dimension(NETDATA_ALL_METRICS, 'truenas_arcstats.dmh_p', 'dmh_p', 0)
    )
    assert arc_stats['demand_metadata_io_hit_percentage'] == normalize_value(
        safely_retrieve_dimension(NETDATA_ALL_METRICS, 'truenas_arcstats.dmi_p', 'dmi_p', 0)
    )
    assert arc_stats['demand_metadata_miss_percentage'] == normalize_value(
        safely_retrieve_dimension(NETDATA_ALL_METRICS, 'truenas_arcstats.dmm_p', 'dmm_p', 0)
    )
    assert arc_stats['l2arc_hits_per_second'] == normalize_value(
        safely_retrieve_dimension(NETDATA_ALL_METRICS, 'truenas_arcstats.l2hits', 'l2hits', 0)
    )
    assert arc_stats['l2arc_misses_per_second'] == normalize_value(
        safely_retrieve_dimension(NETDATA_ALL_METRICS, 'truenas_arcstats.l2miss', 'l2miss', 0)
    )
    assert arc_stats['total_l2arc_accesses_per_second'] == normalize_value(
        safely_retrieve_dimension(NETDATA_ALL_METRICS, 'truenas_arcstats.l2read', 'l2read', 0)
    )
    assert arc_stats['l2arc_access_hit_percentage'] == normalize_value(
        safely_retrieve_dimension(NETDATA_ALL_METRICS, 'truenas_arcstats.l2hit_p', 'l2hit_p', 0)
    )
    assert arc_stats['l2arc_miss_percentage'] == normalize_value(
        safely_retrieve_dimension(NETDATA_ALL_METRICS, 'truenas_arcstats.l2miss_p', 'l2miss_p', 0)
    )
    assert arc_stats['bytes_read_per_second_from_the_l2arc'] == normalize_value(
        safely_retrieve_dimension(NETDATA_ALL_METRICS, 'truenas_arcstats.l2bytes', 'l2bytes', 0)
    )
    assert arc_stats['bytes_written_per_second_to_the_l2arc'] == normalize_value(
        safely_retrieve_dimension(NETDATA_ALL_METRICS, 'truenas_arcstats.l2wbytes', 'l2wbytes', 0)
    )


def test_cpu_stats():
    cpu_stat = get_cpu_stats(NETDATA_ALL_METRICS)
    for metric, value in cpu_stat.items():
        assert value == {
            'usage': safely_retrieve_dimension(
                NETDATA_ALL_METRICS,
                f'truenas_cpu_usage.cpu',
                f'{metric}', 0
            ),
            'temp': safely_retrieve_dimension(
                NETDATA_ALL_METRICS, 'cputemp.temperatures', metric,
            ) or None
        }


def test_disk_stats():
    disks = ['sda', 'sdb', 'sdc', 'sdd']
    disk_mapping = {
        'sda': '{devicename}sda', 'sdb': '{devicename}sdb', 'sdc': '{devicename}sdc', 'sdd': '{devicename}sdd'
    }
    disk_stats = get_disk_stats(NETDATA_ALL_METRICS, disks, disk_mapping)
    read_ops = read_bytes = write_ops = write_bytes = busy = 0
    for disk in disks:
        mapped_key = disk_mapping.get(disk)
        read_ops += safely_retrieve_dimension(
            NETDATA_ALL_METRICS, f'truenas_disk_stats.ops.{mapped_key}', f'{mapped_key}.read_ops', 0
        )
        read_bytes += normalize_value(
            safely_retrieve_dimension(
                NETDATA_ALL_METRICS, f'truenas_disk_stats.io.{mapped_key}', f'{mapped_key}.reads', 0
            ), multiplier=1024,
        )
        write_ops += normalize_value(safely_retrieve_dimension(
            NETDATA_ALL_METRICS, f'truenas_disk_stats.ops.{mapped_key}', f'{mapped_key}.write_ops', 0
        ))
        write_bytes += normalize_value(
            safely_retrieve_dimension(
                NETDATA_ALL_METRICS, f'truenas_disk_stats.io.{mapped_key}', f'{mapped_key}.writes', 0
            ), multiplier=1024,
        )
        busy += safely_retrieve_dimension(
            NETDATA_ALL_METRICS, f'truenas_disk_stats.busy.{mapped_key}', f'{mapped_key}.busy', 0
        )

    assert disk_stats['read_ops'] == read_ops
    assert disk_stats['read_bytes'] == read_bytes
    assert disk_stats['write_ops'] == write_ops
    assert disk_stats['write_bytes'] == write_bytes
    assert disk_stats['busy'] == busy


def test_network_stats():
    interfaces = ['enp1s0']
    for interface_name, metrics in get_interface_stats(NETDATA_ALL_METRICS, interfaces).items():
        send_bytes_rate = normalize_value(
            safely_retrieve_dimension(NETDATA_ALL_METRICS, f'net.{interface_name}', 'sent', 0),
            multiplier=1000, divisor=8
        )
        received_bytes_rate = normalize_value(
            safely_retrieve_dimension(NETDATA_ALL_METRICS, f'net.{interface_name}', 'received', 0),
            multiplier=1000, divisor=8
        )
        assert metrics['received_bytes_rate'] == received_bytes_rate
        assert metrics['sent_bytes_rate'] == send_bytes_rate
        assert metrics['speed'] == normalize_value(safely_retrieve_dimension(
            NETDATA_ALL_METRICS, f'net_speed.{interface_name}', 'speed', 0), divisor=1000
        )
        assert metrics['link_state'] == 'LINK_STATE_UP'


def test_memory_stats():
    memory_stats = get_memory_info(NETDATA_ALL_METRICS)
    assert memory_stats['arc_size'] == normalize_value(
        safely_retrieve_dimension(NETDATA_ALL_METRICS, 'truenas_arcstats.size', 'size', 0)
    )
    assert memory_stats['arc_free_memory'] == normalize_value(
        safely_retrieve_dimension(NETDATA_ALL_METRICS, 'truenas_arcstats.free', 'free', 0)
    )
    assert memory_stats['arc_available_memory'] == normalize_value(
        safely_retrieve_dimension(NETDATA_ALL_METRICS, 'truenas_arcstats.avail', 'avail', 0)
    )
    assert memory_stats['physical_memory_total'] == normalize_value(
        safely_retrieve_dimension(NETDATA_ALL_METRICS, 'truenas_meminfo.total', 'total', 0),
    )
