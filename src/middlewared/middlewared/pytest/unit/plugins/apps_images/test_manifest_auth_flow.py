import asyncio

import aiohttp
import pytest

from middlewared.plugins.apps_images.client import ContainerRegistryClientMixin
from middlewared.plugins.apps_images.utils import DOCKER_AUTH_HEADER
from middlewared.service import CallError


CREDS = {"login": "user", "password": "pass"}
BASIC = 'Basic realm="Registry Realm"'
BEARER = 'Bearer realm="https://auth.docker.io/token",service="registry.docker.io",scope="repository:foo/bar:pull"'


class _Client(ContainerRegistryClientMixin):
    """Stubs the network layer so the 401 auth control flow can be asserted.

    The first ``_api_call`` returns a 401 carrying ``challenge`` in its
    WWW-Authenticate header; any retry returns a valid manifest.
    """

    def __init__(self, challenge):
        self._challenge = challenge
        self.api_call_auth = []  # the `auth` passed to each _api_call
        self.token_calls = []

    async def _api_call(self, url, options=None, headers=None, mode="get", auth=None):
        self.api_call_auth.append(auth)
        if len(self.api_call_auth) == 1:
            err = aiohttp.ClientResponseError(None, (), status=401, headers={DOCKER_AUTH_HEADER: self._challenge})
            return {"error": "401 Unauthorized", "response": {}, "response_obj": None, "error_obj": err}

        class _Resp:
            headers = {}

        return {
            "error": None,
            "response": {
                "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                "config": {"digest": "sha256:cafe"},
            },
            "response_obj": _Resp(),
        }

    async def _get_token(self, scope, auth_url=None, service=None, auth=None):
        self.token_calls.append({"scope": scope, "auth": auth})
        return "FAKE-TOKEN"


async def _run(challenge, auth):
    client = _Client(challenge)
    err = None
    try:
        await client._get_manifest_response(
            "registry.example.com", "foo/bar", "latest", {"Accept": "x"}, "get", True, auth=auth
        )
    except CallError as e:
        err = e
    return client, err


def test__basic_auth_replays_manifest_with_credentials():
    # htpasswd/Basic registry with stored creds: no token fetch, retry carries the creds.
    client, err = asyncio.run(_run(BASIC, CREDS))
    assert err is None
    assert client.token_calls == []
    assert client.api_call_auth == [None, CREDS]


def test__basic_auth_without_credentials_does_not_replay():
    # No creds: replaying would just repeat the same anonymous 401, so it is skipped and
    # the 401 surfaces as a CallError (point 1 - no wasted round-trip, no crash).
    client, err = asyncio.run(_run(BASIC, None))
    assert isinstance(err, CallError)
    assert client.token_calls == []
    assert client.api_call_auth == [None]


def test__bearer_auth_fetches_scoped_token():
    client, err = asyncio.run(_run(BEARER, CREDS))
    assert err is None
    assert len(client.token_calls) == 1
    assert client.token_calls[0]["scope"] == "repository:foo/bar:pull"


@pytest.mark.parametrize(
    "challenge",
    [
        "",  # present-but-empty WWW-Authenticate
        'Bearer realm="x",service="y"',  # Bearer challenge missing scope
    ],
)
def test__insufficient_challenge_raises_callerror_not_typeerror(challenge):
    # An empty/unparseable challenge or a Bearer challenge without `scope` must degrade to
    # a CallError instead of crashing with TypeError: _get_token() missing 'scope' (point 2).
    client, err = asyncio.run(_run(challenge, CREDS))
    assert isinstance(err, CallError)
    assert client.token_calls == []
