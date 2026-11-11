import os

from truesearch_client.config import TARGETS_DIR, render_config

from middlewared.plugins.etc import FileShouldNotExist


def render(service, middleware):
    # The units need the encrypted index dataset to be mounted. A plain directory is not enough, because the indexes
    # would then go to the unencrypted system dataset.
    if not os.path.ismount(TARGETS_DIR):
        raise FileShouldNotExist()

    rows = middleware.call_sync2(middleware.services.truesearch.targets)
    if not rows:
        raise FileShouldNotExist()

    return render_config(rows)
