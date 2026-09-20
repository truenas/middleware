from middlewared.plugins.zfs.property_choices import recordsize_choices


def test_recordsize_choices():
    assert recordsize_choices(32768, draid=False) == ["512", "512B", "1K", "2K", "4K", "8K", "16K", "32K"]


def test_recordsize_choices_draid_starts_at_128k():
    assert recordsize_choices(1 << 20, draid=True) == ["128K", "256K", "512K", "1M"]
