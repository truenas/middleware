from middlewared.utils.metrics.gpu_usage import get_gpu_usage


def get_gpu_stats() -> dict:
    """
    Retrieve GPU usage statistics for all detected GPUs.

    Returns a dictionary keyed by GPU identifier (e.g. 'gpu0', 'gpu1')
    with usage metrics for each GPU. Returns an empty dict if no GPUs
    are detected.
    """
    return get_gpu_usage()
