from middlewared.utils.metrics.gpu_usage import get_gpu_usage

from .utils import safely_retrieve_dimension

def get_gpu_stats(netdata_metrics: dict | None = None) -> dict:
    data = {}
    for name, info in get_gpu_usage().items():
        if netdata_metrics is None:
            data[name] = {
                'usage': info['gpu_utilization'],
                'temp': info['temperature']
            }
        else:
            data[name] = {
                'usage': safely_retrieve_dimension(
                    netdata_metrics, 'truenas_gpu_usage.gpu', name, 0
                ),
                'temp': safely_retrieve_dimension(
                    netdata_metrics, 'gputemp.temperatures', name,
                ) or None
            }

    return data
