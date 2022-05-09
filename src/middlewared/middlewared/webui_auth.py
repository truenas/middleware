from ipaddress import ip_address, ip_network

from aiohttp import web


class WebUIAuth(object):

    def __init__(self, middleware):
        self.middleware = middleware

    async def __call__(self, request):
        """
        TrueCommand authenticates client's browser in WebUI by sending POST request with `auth_token`.
        This is more secure than using query string.
        """

        # We are not able to use nginx to allow/deny client for this specific endpoint so we'll have to make that
        # check ourselves.
        config = await self.middleware.call('system.general.config')
        if config['ui_allowlist']:
            remote_addr = ip_address(request.headers['X-Real-Remote-Addr'])
            for allowed in config['ui_allowlist']:
                allowed = ip_network(allowed)
                if remote_addr == allowed or remote_addr in allowed:
                    break
            else:
                return web.Response(status=403)

        post = await request.post()
        if 'auth_token' not in post:
            return web.Response(status=400, text='No token provided.')
        if not await self.middleware.call('auth.get_token', post['auth_token']):
            return web.Response(status=400, text='Invalid token.')
        with open('/usr/share/truenas/webui/index.html', 'r') as f:
            index = f.read()
        index = index.replace(
            '</head>',
            f'<script>var MIDDLEWARE_TOKEN = "{post["auth_token"]}";</script></head>',
        )
        return web.Response(status=200, body=index, content_type='text/html')
