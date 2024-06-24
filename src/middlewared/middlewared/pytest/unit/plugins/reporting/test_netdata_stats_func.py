from unittest.mock import patch, mock_open

from middlewared.plugins.reporting.netdata.utils import NETDATA_UPDATE_EVERY
from middlewared.plugins.reporting.realtime_reporting import (
    get_arc_stats, get_cpu_stats, get_disk_stats, get_interface_stats, get_memory_info,
)
from middlewared.plugins.reporting.realtime_reporting.utils import normalize_value, safely_retrieve_dimension


NETDATA_ALL_METRICS = {
    'system.cpu': {
        'name': 'system.cpu',
        'family': 'cpu',
        'context': 'system.cpu',
        'units': 'percentage',
        'last_updated': 1691150349,
        'dimensions': {
            'guest_nice': {
                'name': 'guest_nice',
                'value': 0.5375124
            },
            'guest': {
                'name': 'guest',
                'value': 0.5375124
            },
            'steal': {
                'name': 'steal',
                'value': 0.5275124
            },
            'softirq': {
                'name': 'softirq',
                'value': 0.5175124
            },
            'irq': {
                'name': 'irq',
                'value': 0.4975124
            },
            'user': {
                'name': 'user',
                'value': 0.4975124
            },
            'system': {
                'name': 'system',
                'value': 0.4975124
            },
            'nice': {
                'name': 'nice',
                'value': 49.75124
            },
            'iowait': {
                'name': 'iowait',
                'value': 4.75124
            },
            'idle': {
                'name': 'idle',
                'value': 99.0049751
            }
        }
    },
    'cpu.cpu0': {
        'name': 'cpu.cpu0',
        'family': 'utilization',
        'context': 'cpu.cpu',
        'units': 'percentage',
        'last_updated': 1691150349,
        'dimensions': {
            'guest_nice': {
                'name': 'guest_nice',
                'value': 0.2575124
            },
            'guest': {
                'name': 'guest',
                'value': 0.2575124
            },
            'steal': {
                'name': 'steal',
                'value': 0.2575124
            },
            'softirq': {
                'name': 'softirq',
                'value': 0.2375124
            },
            'irq': {
                'name': 'irq',
                'value': 0.2075124
            },
            'user': {
                'name': 'user',
                'value': 0.3275124
            },
            'system': {
                'name': 'system',
                'value': 0.3275124
            },
            'nice': {
                'name': 'nice',
                'value': 26.75124
            },
            'iowait': {
                'name': 'iowait',
                'value': 2.75124
            },
            'idle': {
                'name': 'idle',
                'value': 49.0049751
            }
        }
    },
    'cpu.cpu1': {
        'name': 'cpu.cpu1',
        'family': 'utilization',
        'context': 'cpu.cpu',
        'units': 'percentage',
        'last_updated': 1691150349,
        'dimensions': {
            'guest_nice': {
                'name': 'guest_nice',
                'value': 0.2575124
            },
            'guest': {
                'name': 'guest',
                'value': 0.2575124
            },
            'steal': {
                'name': 'steal',
                'value': 0.2575124
            },
            'softirq': {
                'name': 'softirq',
                'value': 0.2375124
            },
            'irq': {
                'name': 'irq',
                'value': 0.2075124
            },
            'user': {
                'name': 'user',
                'value': 0.3275124
            },
            'system': {
                'name': 'system',
                'value': 0.3275124
            },
            'nice': {
                'name': 'nice',
                'value': 26.75124
            },
            'iowait': {
                'name': 'iowait',
                'value': 2.75124
            },
            'idle': {
                'name': 'idle',
                'value': 49.0049751
            }
        }
    },
    'system.ram': {
        'name': 'system.ram',
        'family': 'ram',
        'context': 'system.ram',
        'units': 'MiB',
        'last_updated': 1691150349,
        'dimensions': {
            'free': {
                'name': 'free',
                'value': 301.0585938
            },
            'used': {
                'name': 'used',
                'value': 1414.1318359
            },
            'cached': {
                'name': 'cached',
                'value': 250.1103516
            },
            'buffers': {
                'name': 'buffers',
                'value': 2.0820312
            }
        }
    },
    'mem.available': {
        'name': 'mem.available',
        'family': 'system',
        'context': 'mem.available',
        'units': 'MiB',
        'last_updated': 1691150349,
        'dimensions': {
            'MemAvailable': {
                'name': 'avail',
                'value': 428.5869141
            }
        }
    },
    'mem.committed': {
        'name': 'mem.committed',
        'family': 'system',
        'context': 'mem.committed',
        'units': 'MiB',
        'last_updated': 1691150349,
        'dimensions': {
            'Committed_AS': {
                'name': 'Committed_AS',
                'value': 1887.0546875
            }
        }
    },
    'mem.kernel': {
        'name': 'mem.kernel',
        'family': 'kernel',
        'context': 'mem.kernel',
        'units': 'MiB',
        'last_updated': 1691150349,
        'dimensions': {
            'Slab': {
                'name': 'Slab',
                'value': 150.78125
            },
            'KernelStack': {
                'name': 'KernelStack',
                'value': 5.25
            },
            'PageTables': {
                'name': 'PageTables',
                'value': 6.53125
            },
            'VmallocUsed': {
                'name': 'VmallocUsed',
                'value': 99.6875
            },
            'Percpu': {
                'name': 'Percpu',
                'value': 0.8984375
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
    'disk.sda': {
        'name': 'disk.sda',
        'family': 'vda',
        'context': 'disk.io',
        'units': 'KiB/s',
        'last_updated': 1691150349,
        'dimensions': {
            'reads': {
                'name': 'reads',
                'value': 0
            },
            'writes': {
                'name': 'writes',
                'value': 0
            }
        }
    },
    'disk_ops.sda': {
        'name': 'disk_ops.sda',
        'family': 'vda',
        'context': 'disk.ops',
        'units': 'operations/s',
        'last_updated': 1691150349,
        'dimensions': {
            'reads': {
                'name': 'reads',
                'value': 0
            },
            'writes': {
                'name': 'writes',
                'value': 0
            }
        }
    },
    'disk_busy.sda': {
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
    'disk.sdb': {
        'name': 'disk.sdb',
        'family': 'vdb',
        'context': 'disk.io',
        'units': 'KiB/s',
        'last_updated': 1691150349,
        'dimensions': {
            'reads': {
                'name': 'reads',
                'value': 0
            },
            'writes': {
                'name': 'writes',
                'value': 0
            }
        }
    },
    'disk_ops.sdb': {
        'name': 'disk_ops.sdb',
        'family': 'vdb',
        'context': 'disk.ops',
        'units': 'operations/s',
        'last_updated': 1691150349,
        'dimensions': {
            'reads': {
                'name': 'reads',
                'value': 0
            },
            'writes': {
                'name': 'writes',
                'value': 0
            }
        }
    },
    'disk_busy.sdb': {
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
    'disk.sdc': {
        'name': 'disk.sdc',
        'family': 'vdc',
        'context': 'disk.io',
        'units': 'KiB/s',
        'last_updated': 1691150349,
        'dimensions': {
            'reads': {
                'name': 'reads',
                'value': 0
            },
            'writes': {
                'name': 'writes',
                'value': 0
            }
        }
    },

    'disk_ops.sdc': {
        'name': 'disk_ops.sdc',
        'family': 'vdc',
        'context': 'disk.ops',
        'units': 'operations/s',
        'last_updated': 1691150349,
        'dimensions': {
            'reads': {
                'name': 'reads',
                'value': 0
            },
            'writes': {
                'name': 'writes',
                'value': 0
            }
        }
    },
    'disk_busy.sdc': {
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
    'disk.sdd': {
        'name': 'disk.sdd',
        'family': 'vdd',
        'context': 'disk.io',
        'units': 'KiB/s',
        'last_updated': 1691150349,
        'dimensions': {
            'reads': {
                'name': 'reads',
                'value': 0
            },
            'writes': {
                'name': 'writes',
                'value': 0
            }
        }
    },
    'disk_ops.sdd': {
        'name': 'disk_ops.sdd',
        'family': 'vdd',
        'context': 'disk.ops',
        'units': 'operations/s',
        'last_updated': 1691150349,
        'dimensions': {
            'reads': {
                'name': 'reads',
                'value': 0
            },
            'writes': {
                'name': 'writes',
                'value': 0
            }
        }
    },
    'disk_busy.sdd': {
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
    'zfs.arc_size': {
        'name': 'zfs.arc_size',
        'family': 'size',
        'context': 'zfs.arc_size',
        'units': 'MiB',
        'last_updated': 1691150349,
        'dimensions': {
            'size': {
                'name': 'arcsz',
                'value': 210.9588394
            },
            'target': {
                'name': 'target',
                'value': 256.2307129
            },
            'min': {
                'name': 'min (hard limit)',
                'value': 61.4807129
            },
            'max': {
                'name': 'max (high water)',
                'value': 983.6914062
            }
        }
    },
    'zfs.hits': {
        'name': 'zfs.hits',
        'family': 'efficiency',
        'context': 'zfs.hits',
        'units': 'percentage',
        'last_updated': 1691150349,
        'dimensions': {
            'hits': {
                'name': 'hits',
                'value': 3
            },
            'misses': {
                'name': 'misses',
                'value': 4
            }
        }
    }
}
MEM_INFO = '''Active:            67772 kB
Inactive:        1379892 kB
Mapped:            54768 kB
'''


def test_arc_stats():
    arc_stats = get_arc_stats(NETDATA_ALL_METRICS)
    assert arc_stats['arc_max_size'] == normalize_value(
        safely_retrieve_dimension(NETDATA_ALL_METRICS, 'zfs.arc_size', 'max', 0), multiplier=1024 * 1024,
    )
    assert arc_stats['arc_size'] == normalize_value(
        safely_retrieve_dimension(NETDATA_ALL_METRICS, 'zfs.arc_size', 'size', 0), multiplier=1024 * 1024,
    )
    total = safely_retrieve_dimension(NETDATA_ALL_METRICS, 'zfs.hits', 'hits', 0) + safely_retrieve_dimension(
        NETDATA_ALL_METRICS, 'zfs.hits', 'misses', 0)
    assert arc_stats['cache_hit_ratio'] == safely_retrieve_dimension(
        NETDATA_ALL_METRICS, 'zfs.hits', 'hits', 0
    ) / total


def test_cpu_stats():
    cpu_stats = get_cpu_stats(NETDATA_ALL_METRICS, 2)
    cpu_stat = {'system.cpu': cpu_stats['average'], 'cpu.cpu0': cpu_stats['0'], 'cpu.cpu1': cpu_stats['1']}
    for chart_name, metrics in cpu_stat.items():
        total_sum = sum(metrics.values()) - metrics['usage']
        assert metrics['user'] == safely_retrieve_dimension(NETDATA_ALL_METRICS, chart_name, 'user', 0)
        assert metrics['nice'] == safely_retrieve_dimension(NETDATA_ALL_METRICS, chart_name, 'nice', 0)
        assert metrics['system'] == safely_retrieve_dimension(NETDATA_ALL_METRICS, chart_name, 'system', 0)
        assert metrics['idle'] == safely_retrieve_dimension(NETDATA_ALL_METRICS, chart_name, 'idle', 0)
        assert metrics['iowait'] == safely_retrieve_dimension(NETDATA_ALL_METRICS, chart_name, 'iowait', 0)
        assert metrics['irq'] == safely_retrieve_dimension(NETDATA_ALL_METRICS, chart_name, 'irq', 0)
        assert metrics['softirq'] == safely_retrieve_dimension(NETDATA_ALL_METRICS, chart_name, 'softirq', 0)
        assert metrics['steal'] == safely_retrieve_dimension(NETDATA_ALL_METRICS, chart_name, 'steal', 0)
        assert metrics['guest'] == safely_retrieve_dimension(NETDATA_ALL_METRICS, chart_name, 'guest', 0)
        assert metrics['guest_nice'] == safely_retrieve_dimension(NETDATA_ALL_METRICS, chart_name, 'guest_nice', 0)
        assert metrics['usage'] == ((total_sum - metrics['idle'] - metrics['iowait']) / total_sum) * 100


def test_disk_stats():
    disks = ['sda', 'sdb', 'sdc', 'sdd']
    disk_stats = get_disk_stats(NETDATA_ALL_METRICS, disks)
    read_ops = read_bytes = write_ops = write_bytes = busy = 0
    for disk in disks:
        read_ops += safely_retrieve_dimension(NETDATA_ALL_METRICS, f'disk_ops.{disk}', 'reads', 0)
        read_bytes += normalize_value(
            safely_retrieve_dimension(NETDATA_ALL_METRICS, f'disk.{disk}', 'reads', 0), multiplier=1024,
        )
        write_ops += normalize_value(safely_retrieve_dimension(NETDATA_ALL_METRICS, f'disk_ops.{disk}', 'writes', 0))
        write_bytes += normalize_value(safely_retrieve_dimension(NETDATA_ALL_METRICS, f'disk.{disk}', 'writes', 0))
        busy += safely_retrieve_dimension(NETDATA_ALL_METRICS, f'disk_busy.{disk}', 'busy', 0)

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
    with patch('builtins.open', mock_open(read_data=MEM_INFO)):
        memory_stats = get_memory_info(NETDATA_ALL_METRICS)
        assert memory_stats['classes']['page_tables'] == normalize_value(
            safely_retrieve_dimension(NETDATA_ALL_METRICS, 'mem.kernel', 'PageTables', 0), multiplier=1024 * 1024
        )
        assert memory_stats['classes']['slab_cache'] == normalize_value(
            safely_retrieve_dimension(NETDATA_ALL_METRICS, 'mem.kernel', 'Slab', 0), multiplier=1024 * 1024
        )
        assert memory_stats['classes']['cache'] == normalize_value(
            safely_retrieve_dimension(NETDATA_ALL_METRICS, 'system.ram', 'cached', 0), multiplier=1024 * 1024
        )
        assert memory_stats['classes']['buffers'] == normalize_value(
            safely_retrieve_dimension(NETDATA_ALL_METRICS, 'system.ram', 'buffers', 0), multiplier=1024 * 1024
        )
        assert memory_stats['classes']['unused'] == normalize_value(
            safely_retrieve_dimension(NETDATA_ALL_METRICS, 'system.ram', 'free', 0), multiplier=1024 * 1024
        )
        assert memory_stats['classes']['arc'] == normalize_value(
            safely_retrieve_dimension(NETDATA_ALL_METRICS, 'zfs.arc_size', 'size', 0), multiplier=1024 * 1024
        )
        assert memory_stats['classes']['apps'] == normalize_value(
            safely_retrieve_dimension(NETDATA_ALL_METRICS, 'system.ram', 'used', 0), multiplier=1024 * 1024
        )
        assert memory_stats['extra']['inactive'] == 1413009408 * 1024
        assert memory_stats['extra']['committed'] == normalize_value(
            safely_retrieve_dimension(NETDATA_ALL_METRICS, 'mem.committed', 'Committed_AS', 0), multiplier=1024 * 1024,
        )
        assert memory_stats['extra']['active'] == 69398528 * 1024
        assert memory_stats['extra']['vmalloc_used'] == normalize_value(
            safely_retrieve_dimension(NETDATA_ALL_METRICS, 'mem.kernel', 'VmallocUsed', 0), multiplier=1024 * 1024
        )
        assert memory_stats['extra']['mapped'] == 56082432 * 1024
        