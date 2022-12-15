import aiohttp
import aiohttp.client_exceptions
import async_timeout
import asyncio
import urllib

from middlewared.service import CallError, private

from .utils import DEFAULT_DOCKER_REGISTRY, DOCKER_CONTENT_DIGEST_HEADER


DOCKER_AUTH_HEADER = 'WWW-Authenticate'
DOCKER_AUTH_URL = 'https://auth.docker.io/token'
DOCKER_AUTH_SERVICE = 'registry.docker.io'
DOCKER_MANIFEST_SCHEMA_V1 = 'application/vnd.docker.distribution.manifest.v1+json'
DOCKER_MANIFEST_SCHEMA_V2 = 'application/vnd.docker.distribution.manifest.v2+json'
DOCKER_MANIFEST_LIST_SCHEMA_V2 = 'application/vnd.docker.distribution.manifest.list.v2+json'


def parse_digest_from_schema(response):
    """
    Parses out the digest according to schemas specs:
    https://docs.docker.com/registry/spec/manifest-v2-1/
    """
    media_type = response['response']['mediaType']
    if media_type == DOCKER_MANIFEST_SCHEMA_V2:
        digest_value = response['response']['config']['digest']
        return [digest_value] if isinstance(digest_value, str) else digest_value
    elif media_type == DOCKER_MANIFEST_LIST_SCHEMA_V2:
        if manifests := response['response']['manifests']:
            return [digest['digest'] for digest in manifests]
    return []


def parse_auth_header(header: str):
    """
    Parses header in format below:
    'Bearer realm="https://ghcr.io/token",service="ghcr.io",scope="redis:pull"'

    Returns:
        {
            'auth_url': 'https://ghcr.io/token',
            'service': 'ghcr.io',
            'scope': 'redis:pull'
        }
    """
    adapter = {
        'realm': 'auth_url',
        'service': 'service',
        'scope': 'scope',
    }
    results = {}
    parts = header.split()
    if len(parts) > 1:
        for part in parts[1].split(','):
            key, value = part.split('=')
            if key in adapter:
                results[adapter[key]] = value.strip('"')
    return results


class DockerClientMixin:

    async def _api_call(self, url, options=None, headers=None, mode='get'):
        options = options or {}
        timeout = options.get('timeout', 15)
        assert mode in ('get', 'head')
        response = {'error': None, 'response': {}, 'response_obj': None}
        try:
            async with async_timeout.timeout(timeout):
                async with aiohttp.ClientSession(
                    raise_for_status=True, trust_env=True,
                ) as session:
                    req = await getattr(session, mode)(url, headers=headers)
        except asyncio.TimeoutError:
            response['error'] = f'Unable to connect with {url} in {timeout} seconds.'
        except aiohttp.ClientResponseError as e:
            response['error'] = e
        else:
            response['response_obj'] = req
            if req.status != 200:
                response['error'] = f'Received response code {req.status}' + (
                    f' ({req.content})' if req.content else ''
                )
            else:
                try:
                    response['response'] = await req.json()
                except aiohttp.client_exceptions.ContentTypeError as e:
                    # quay.io registry returns malformed content type header which aiohttp fails to parse
                    # even though the content returned by registry is valid json
                    response['error'] = f'Unable to parse response: {e}'
                except asyncio.TimeoutError:
                    response['error'] = 'Timed out waiting for a response'
        return response

    async def _get_token(self, scope, auth_url=DOCKER_AUTH_URL, service=DOCKER_AUTH_SERVICE):
        query_params = urllib.parse.urlencode({
            'service': service,
            'scope': scope,
        })
        response = await self._api_call(f'{auth_url}?{query_params}')
        if response['error']:
            raise CallError(f'Unable to retrieve token for {scope!r}: {response["error"]}')

        return response['response']['token']

    async def _get_manifest_response(self, registry, image, tag, headers, mode, raise_error):
        manifest_url = f'https://{registry}/v2/{image}/manifests/{tag}'
        # 1) try getting manifest
        response = await self._api_call(manifest_url, headers=headers, mode=mode)
        if (error := response['error']) and isinstance(error, aiohttp.ClientResponseError):
            if error.status == 401:
                # 2) try to get token from manifest api call's response headers
                auth_data = parse_auth_header(error.headers[DOCKER_AUTH_HEADER])
                headers['Authorization'] = f'Bearer {await self._get_token(**auth_data)}'
                # 3) Redo the manifest call with updated token
                response = await self._api_call(manifest_url, headers=headers, mode=mode)

        if raise_error and response['error']:
            raise CallError(f"Unable to retrieve latest image digest for registry={registry} "
                            f"image={image} tag={tag}: {response['error']}")

        return response

    @private
    async def get_manifest_call_headers(self, registry, image, headers):
        if registry == DEFAULT_DOCKER_REGISTRY:
            headers['Authorization'] = f'Bearer {await self._get_token(scope=f"repository:{image}:pull")}'
        return headers

    async def _get_repo_digest(self, registry, image, tag):
        response = await self._get_manifest_response(
            registry, image, tag, await self.get_manifest_call_headers(registry, image, {
                'Accept': (f'{DOCKER_MANIFEST_SCHEMA_V2}, '
                           f'{DOCKER_MANIFEST_LIST_SCHEMA_V2}, '
                           f'{DOCKER_MANIFEST_SCHEMA_V1}')
            }), 'get', True
        )
        digests = parse_digest_from_schema(response)
        digests.append(response['response_obj'].headers.get(DOCKER_CONTENT_DIGEST_HEADER))
        return digests
