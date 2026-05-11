import time

from middlewared.utils.cpu import cpu_info
from middlewared.utils.metrics.cpu_usage import calculate_cpu_usage, get_cpu_usage

# /proc/stat exposes 10 numeric fields per cpu line on modern Linux:
# user, nice, system, idle, iowait, irq, softirq, steal, guest, guest_nice
PROC_STAT_FIELDS = 10


def test_first_call_zero():
    """No prior sample → every value reported as 0 (cpu_usage.py:45-47)."""
    usage, cached = get_cpu_usage(None)
    assert usage and cached
    for core, value in usage.items():
        assert value == 0, f"{core}: expected 0 on first call, got {value!r}"


def test_second_call_in_range():
    _, cached = get_cpu_usage(None)
    # Allow the cpu counters to advance so the second sample produces non-zero
    # deltas — the calculation degrades to 0 if delta_time is 0.
    time.sleep(0.2)
    usage, _ = get_cpu_usage(cached)
    for core, value in usage.items():
        assert isinstance(value, float), f"{core}: expected float, got {type(value)}"
        assert 0.0 <= value <= 100.0, f"{core}: {value!r} outside 0-100"


def test_keys_match_proc_stat():
    usage, cached = get_cpu_usage(None)
    assert usage.keys() == cached.keys()
    assert "cpu" in usage
    expected_cores = frozenset(f"cpu{i}" for i in range(cpu_info()["core_count"]))
    assert expected_cores <= usage.keys()


def test_cached_values_are_lists_of_int():
    _, cached = get_cpu_usage(None)
    for core, values in cached.items():
        assert isinstance(values, list), f"{core}: cached values not a list"
        assert values, f"{core}: cached values list is empty"
        for v in values:
            assert isinstance(v, int)
        assert len(values) == PROC_STAT_FIELDS, f"{core}: {len(values)} fields"


def test_calculate_cpu_usage_zero_delta():
    """Identical sample lists → no time elapsed → 0.0."""
    sample = [100, 0, 50, 1000, 0, 0, 0, 0, 0, 0]
    assert calculate_cpu_usage(sample, sample) == 0.0


def test_calculate_cpu_usage_idle_only():
    """All elapsed time was idle → 0% active."""
    old = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    new = [0, 0, 0, 100, 0, 0, 0, 0, 0, 0]  # only idle advanced
    assert calculate_cpu_usage(new, old) == 0.0


def test_calculate_cpu_usage_fully_active():
    """All elapsed time was non-idle/non-iowait → 100%."""
    old = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    new = [50, 0, 50, 0, 0, 0, 0, 0, 0, 0]
    assert calculate_cpu_usage(new, old) == 100.0
