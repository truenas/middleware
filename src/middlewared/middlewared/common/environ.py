import os
import time

import urllib.request


def environ_update(update):
    for k, v in update.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

    if 'http_proxy' in update or 'https_proxy' in update:
        # Reset global opener so ProxyHandler can be recalculated
        urllib.request.install_opener(None)

    if 'TZ' in update:
        time.tzset()
