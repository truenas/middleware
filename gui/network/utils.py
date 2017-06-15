import os
import urllib.request


def configure_http_proxy(http_proxy):
    if http_proxy:
        os.environ['http_proxy'] = http_proxy
        os.environ['https_proxy'] = http_proxy
    elif not http_proxy:
        if 'http_proxy' in os.environ:
            del os.environ['http_proxy']
        if 'https_proxy' in os.environ:
            del os.environ['https_proxy']

    # Reset global opener so ProxyHandler can be recalculated
    urllib.request.install_opener(None)
