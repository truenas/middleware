import io
from unittest.mock import patch

from middlewared.plugins.pool_.dataset_recordsize import PoolDatasetService


def test_recordsize_choices():
    with patch("middlewared.plugins.pool_.dataset_recordsize.open") as mock:
        mock.return_value = io.StringIO("32768\n")
        assert PoolDatasetService(None).recordsize_choices() == ["512B", "1K", "2K", "4K", "8K", "16K", "32K"]