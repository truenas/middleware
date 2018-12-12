from types import SimpleNamespace

import requests

from freenasUI.middleware.client import client


def query_model(path, filter_key):
    with client as c:
        url = c.call("system.general.local_url")
        token = c.call("auth.generate_token")

    r = requests.get(f"{url}/api/v1.0/{path}/", headers={"Authorization": f"Token {token}"}, verify=False)
    r.raise_for_status()

    return [SimpleNamespace(**d) for d in r.json() if d[filter_key]]
