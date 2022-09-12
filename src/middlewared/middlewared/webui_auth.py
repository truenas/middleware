from ipaddress import ip_address, ip_network

from aiohttp import web


def addr_in_allowlist(remote_addr, allowlist):
    valid = False
    try:
        remote_addr = ip_address(remote_addr)
    except Exception:
        # invalid/malformed IP so play it safe and
        # return False
        valid = False
    else:
        for allowed in allowlist:
            try:
                allowed = ip_network(allowed)
            except Exception:
                # invalid/malformed network so play it safe
                valid = False
                break
            else:
                if remote_addr == allowed or remote_addr in allowed:
                    valid = True
                    break

    return valid


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
        if allowlist := await self.middleware.call('system.general.get_ui_allowlist'):
            if not addr_in_allowlist(request.headers['X-Real-Remote-Addr'], allowlist):
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
