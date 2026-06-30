from __future__ import annotations

import asyncio
from typing import Any
import urllib.parse

import aiohttp

from middlewared.service import CallError
from middlewared.utils.docker_registry import DEFAULT_DOCKER_REGISTRY

from .utils import (
    DOCKER_AUTH_HEADER,
    DOCKER_AUTH_SERVICE,
    DOCKER_AUTH_URL,
    DOCKER_CONTENT_DIGEST_HEADER,
    DOCKER_MANIFEST_LIST_SCHEMA_V2,
    DOCKER_MANIFEST_OCI_V1,
    DOCKER_MANIFEST_SCHEMA_V1,
    DOCKER_MANIFEST_SCHEMA_V2,
    DOCKER_RATELIMIT_URL,
    parse_auth_header,
    parse_digest_from_schema,
)


class ContainerRegistryClientMixin:
    @staticmethod
    async def _api_call(
        url: str,
        options: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        mode: str = "get",
        auth: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        options = options or {}
        timeout = options.get("timeout", 15)
        assert mode in ("get", "head")
        response: dict[str, Any] = {"error": None, "response": {}, "response_obj": None}
        try:
            async with asyncio.timeout(timeout):
                async with aiohttp.ClientSession(raise_for_status=True, trust_env=True) as ss:
                    coro = getattr(ss, mode)
                    req = await coro(url, headers=headers, auth=aiohttp.BasicAuth(**auth) if auth else None)
                    response["response_obj"] = req
                    if req.status != 200:
                        cnt = ""
                        if req.content:
                            cnt = f" ({req.content})"
                        response["error"] = f"Received response code {req.status}{cnt}"
                    else:
                        try:
                            response["response"] = await req.json()
                        except aiohttp.ContentTypeError as e:
                            # quay.io registry returns malformed content type header
                            # which aiohttp fails to parse even though the content
                            # returned by registry is valid json
                            response["error"] = f"Unable to parse response: {e}"
                        except RuntimeError as e:
                            response["error"] = f"Connection closed before the response could be fully read ({e})"
        except asyncio.TimeoutError:
            response["error"] = f"Unable to connect with {url} in {timeout} seconds."
        except aiohttp.ClientResponseError as e:
            response.update({"error": str(e), "error_obj": e})
        return response

    async def _get_token(
        self,
        scope: str,
        auth_url: str = DOCKER_AUTH_URL,
        service: str = DOCKER_AUTH_SERVICE,
        auth: dict[str, str] | None = None,
    ) -> str:
        query_params = urllib.parse.urlencode(
            {
                "service": service,
                "scope": scope,
            }
        )
        response = await self._api_call(f"{auth_url}?{query_params}", auth=auth)
        if response["error"]:
            raise CallError(f"Unable to retrieve token for {scope!r}: {response['error']}")

        return str(response["response"]["token"])

    async def _get_manifest_response(
        self,
        registry: str,
        image: str,
        tag: str,
        headers: dict[str, str],
        mode: str,
        raise_error: bool,
        auth: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        manifest_url = f"https://{registry}/v2/{image}/manifests/{tag}"
        # 1) try getting manifest
        response = await self._api_call(manifest_url, headers=headers, mode=mode)
        if (error := response.get("error_obj")) and isinstance(error, aiohttp.ClientResponseError):
            if error.status == 401:
                # 2) Authenticate according to the scheme advertised in the challenge. An
                # empty/unrecognized challenge - or a Bearer challenge that omits the scope
                # needed to request a token - is left to surface as a CallError below rather
                # than crashing.
                auth_data = parse_auth_header((error.headers or {}).get(DOCKER_AUTH_HEADER) or '')
                scheme = auth_data.pop('scheme', None)
                if scheme == 'basic' and auth is not None:
                    # Private registries using htpasswd/HTTP Basic auth answer with a
                    # `Basic` challenge that has no token endpoint or scope - there is no
                    # token to fetch. Replay the manifest request with the stored
                    # credentials. With no credentials the replay would just repeat the
                    # anonymous request that already 401'd, so it is skipped.
                    response = await self._api_call(manifest_url, headers=headers, mode=mode, auth=auth)
                elif scheme == 'bearer' and 'scope' in auth_data:
                    # Bearer/token auth: fetch a scoped token from the registry's auth
                    # endpoint and retry with it. The token request is sent with Basic auth
                    # when registry creds are configured so the returned token has read
                    # scope on private repos.
                    token = await self._get_token(
                        scope=auth_data["scope"],
                        auth_url=auth_data.get("auth_url", DOCKER_AUTH_URL),
                        service=auth_data.get("service", DOCKER_AUTH_SERVICE),
                        auth=auth,
                    )
                    headers['Authorization'] = f'Bearer {token}'
                    # 3) Redo the manifest call with updated token
                    response = await self._api_call(manifest_url, headers=headers, mode=mode)

        if raise_error and response["error"]:
            raise CallError(
                f"Unable to retrieve latest image digest for registry={registry} "
                f"image={image} tag={tag}: {response['error']}"
            )

        return response

    async def get_manifest_call_headers(
        self,
        registry: str,
        image: str,
        headers: dict[str, str],
        auth: dict[str, str] | None = None,
    ) -> dict[str, str]:
        # Docker Hub always 401s the first manifest hit, so preemptively fetch a
        # bearer token here. For non-Hub registries we let `_get_manifest_response`
        # discover the challenge from the 401 response itself.
        if registry == DEFAULT_DOCKER_REGISTRY:
            headers["Authorization"] = (
                f"Bearer {await self._get_token(scope=f'repository:{image}:pull', auth=auth)}"
            )
        return headers

    async def _get_repo_digest(
        self,
        registry: str,
        image: str,
        tag: str,
        auth: dict[str, str] | None = None,
    ) -> list[str]:
        # `auth` is the aiohttp BasicAuth kwargs dict ({"login", "password"}) for
        # the registry hosting this image, or None for anonymous access. It is
        # threaded down to `_get_token` so that the bearer token returned by the
        # registry's auth endpoint carries the user's read scope on private repos.
        response = await self._get_manifest_response(
            registry,
            image,
            tag,
            await self.get_manifest_call_headers(
                registry,
                image,
                {
                    "Accept": (
                        f"{DOCKER_MANIFEST_SCHEMA_V2}, "
                        f"{DOCKER_MANIFEST_LIST_SCHEMA_V2}, "
                        f"{DOCKER_MANIFEST_SCHEMA_V1}, "
                        f"{DOCKER_MANIFEST_OCI_V1}"
                    )
                },
                auth=auth,
            ),
            "get",
            True,
            auth=auth,
        )
        digests = parse_digest_from_schema(response)
        digests.append(response["response_obj"].headers.get(DOCKER_CONTENT_DIGEST_HEADER))
        return digests

    async def get_docker_hub_rate_limit_preview(
        self,
        auth: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        token = await self._get_token(scope="repository:ratelimitpreview/test:pull", auth=auth)
        return await self._api_call(url=DOCKER_RATELIMIT_URL, headers={"Authorization": f"Bearer {token}"}, mode="head")
