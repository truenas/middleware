import os
from .base import SimpleService


class TrueSearchService(SimpleService):
    name = "truesearch"
    reloadable = True

    systemd_unit = "truesearch"

    async def before_start(self):
        """Check that the config file exists before starting."""
        config_file = '/etc/truesearch/config.json'
        if not os.path.exists(config_file):
            raise Exception(
                f'TrueSearch config file {config_file} not found. '
                'Please ensure WebShare is configured first.'
            )
