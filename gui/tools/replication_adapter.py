from types import SimpleNamespace

import requests

from freenasUI.middleware.client import client


def query_model(path, filter_key):
    with client as c:
        token = c.call("auth.generate_token")

    r = requests.get(f"http://localhost/api/v1.0/{path}/", headers={"Authorization": f"Token {token}"})
    r.raise_for_status()

    return [SimpleNamespace(**d) for d in r.json() if d[filter_key]]
