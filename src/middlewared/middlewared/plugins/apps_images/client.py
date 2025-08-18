import asyncio
import urllib.parse

import aiohttp

from middlewared.service import CallError

from .utils import (
    DEFAULT_DOCKER_REGISTRY, DOCKER_AUTH_SERVICE, DOCKER_AUTH_HEADER, DOCKER_AUTH_URL, DOCKER_CONTENT_DIGEST_HEADER,
    DOCKER_MANIFEST_LIST_SCHEMA_V2, DOCKER_MANIFEST_SCHEMA_V1, DOCKER_MANIFEST_SCHEMA_V2, DOCKER_RATELIMIT_URL,
    DOCKER_MANIFEST_OCI_V1, parse_auth_header, parse_digest_from_schema,
)


class ContainerRegistryClientMixin:

    @staticmethod
    async def _api_call(url, options=None, headers=None, mode='get', auth=None):
        options = options or {}
        timeout = options.get('timeout', 15)
        assert mode in ('get', 'head')
        response = {'error': None, 'response': {}, 'response_obj': None}
        try:
            async with asyncio.timeout(timeout):
                async with aiohttp.ClientSession(
                    raise_for_status=True, trust_env=True,
                ) as session:
                    req = await getattr(session, mode)(
                        url, headers=headers, auth=aiohttp.BasicAuth(**auth) if auth else None
                    )
        except asyncio.TimeoutError:
            response['error'] = f'Unable to connect with {url} in {timeout} seconds.'
        except aiohttp.ClientResponseError as e:
            response.update({
                'error': str(e),
                'error_obj': e,
            })
        else:
            response['response_obj'] = req
            if req.status != 200:
                response['error'] = f'Received response code {req.status}' + (
                    f' ({req.content})' if req.content else ''
                )
            else:
                try:
                    response['response'] = await req.json()
                except aiohttp.ContentTypeError as e:
                    # quay.io registry returns malformed content type header which aiohttp fails to parse
                    # even though the content returned by registry is valid json
                    response['error'] = f'Unable to parse response: {e}'
                except asyncio.TimeoutError:
                    response['error'] = 'Timed out waiting for a response'
                except RuntimeError as e:
                    response['error'] = f'Connection closed before the response could be fully read ({e})'
        return response

    async def _get_token(self, scope, auth_url=DOCKER_AUTH_URL, service=DOCKER_AUTH_SERVICE, auth=None):
        query_params = urllib.parse.urlencode({
            'service': service,
            'scope': scope,
        })
        response = await self._api_call(f'{auth_url}?{query_params}', auth=auth)
        if response['error']:
            raise CallError(f'Unable to retrieve token for {scope!r}: {response["error"]}')

        return response['response']['token']

    async def _get_manifest_response(self, registry, image, tag, headers, mode, raise_error):
        manifest_url = f'https://{registry}/v2/{image}/manifests/{tag}'
        # 1) try getting manifest
        response = await self._api_call(manifest_url, headers=headers, mode=mode)
        if (error := response.get('error_obj')) and isinstance(error, aiohttp.ClientResponseError):
            if error.status == 401:
                # 2) try to get token from manifest api call's response headers
                auth_data = parse_auth_header(error.headers[DOCKER_AUTH_HEADER])
                headers['Authorization'] = f'Bearer {await self._get_token(**auth_data)}'
                # 3) Redo the manifest call with updated token
                response = await self._api_call(manifest_url, headers=headers, mode=mode)

        if raise_error and response['error']:
            raise CallError(
                f'Unable to retrieve latest image digest for registry={registry} '
                f'image={image} tag={tag}: {response["error"]}'
            )

        return response

    async def get_manifest_call_headers(self, registry, image, headers):
        if registry == DEFAULT_DOCKER_REGISTRY:
            headers['Authorization'] = f'Bearer {await self._get_token(scope=f"repository:{image}:pull")}'
        return headers

    async def _get_repo_digest(self, registry, image, tag):
        response = await self._get_manifest_response(
            registry, image, tag, await self.get_manifest_call_headers(registry, image, {
                'Accept': (f'{DOCKER_MANIFEST_SCHEMA_V2}, '
                           f'{DOCKER_MANIFEST_LIST_SCHEMA_V2}, '
                           f'{DOCKER_MANIFEST_SCHEMA_V1}, '
                           f'{DOCKER_MANIFEST_OCI_V1}')
            }), 'get', True
        )
        digests = parse_digest_from_schema(response)
        digests.append(response['response_obj'].headers.get(DOCKER_CONTENT_DIGEST_HEADER))
        return digests

    async def get_docker_hub_rate_limit_preview(self, auth=None):
        token = (await self._get_token(scope="repository:ratelimitpreview/test:pull", auth=auth))
        return await self._api_call(
            url=DOCKER_RATELIMIT_URL,
            headers={'Authorization': f'Bearer {token}'},
            mode='head'
        )
