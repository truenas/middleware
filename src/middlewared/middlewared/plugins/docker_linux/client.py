import aiohttp
import aiohttp.client_exceptions
import async_timeout
import asyncio

from middlewared.service import CallError

from .utils import DEFAULT_DOCKER_REGISTRY, DOCKER_CONTENT_DIGEST_HEADER


DOCKER_REGISTRY_AUTH_BASE = 'https://auth.docker.io'
DOCKER_AUTH_SERVICE = 'registry.docker.io'


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
            response['error'] = str(e)
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
        return response

    async def _get_token(self, image):
        response = await self._api_call(
            f'{DOCKER_REGISTRY_AUTH_BASE}/token?service={DOCKER_AUTH_SERVICE}&scope=repository:{image}:pull'
        )
        if response['error']:
            raise CallError(f'Unable to retrieve token for {image!r}: {response["error"]}')

        return response['response']['token']

    async def _get_manifest_response(self, registry, image, tag, headers, mode, raise_error):
        response = await self._api_call(
            f'https://{registry}/v2/{image}/manifests/{tag}', headers=headers, mode=mode
        )
        if raise_error and response['error']:
            raise CallError(f'Unable to retrieve latest image digest for {f"{image}:{tag}"!r}: {response["error"]}')

        return response

    async def get_manifest_call_headers(self, registry, image, headers):
        if registry == DEFAULT_DOCKER_REGISTRY:
            headers['Authorization'] = f'Bearer {await self._get_token(image)}'
        return headers

    async def _get_latest_digest(self, registry, image, tag):
        response = await self._get_manifest_response(
            registry, image, tag, await self.get_manifest_call_headers(registry, image, {
                'Accept': 'application/vnd.docker.distribution.manifest.v2+json',
            }), 'get', True
        )

        return response['response']['config']['digest']

    async def _get_repo_digest(self, registry, image, tag):
        response = await self._get_manifest_response(
            registry, image, tag, await self.get_manifest_call_headers(registry, image, {
                'Accept': 'application/vnd.docker.distribution.manifest.v2+json, '
                          'application/vnd.docker.distribution.manifest.list.v2+json, '
                          'application/vnd.docker.distribution.manifest.v1+json',
            }), 'head', False
        )
        if not response['error']:
            return response['response_obj'].headers.get(DOCKER_CONTENT_DIGEST_HEADER)
