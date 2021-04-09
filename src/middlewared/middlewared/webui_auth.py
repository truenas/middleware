from aiohttp import web


class WebUIAuth(object):

    def __init__(self, middleware):
        self.middleware = middleware

    async def __call__(self, request):
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
