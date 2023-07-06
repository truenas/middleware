import aiohttp.web

from middlewared.utils.mako import get_template


async def render_template(request, name, **kwargs):
    return await request.app['middleware'].run_in_thread(
        lambda: get_template(f'apidocs/templates/{name}').render(**kwargs)
    )


async def render_to_response(request, name, **kwargs):
    return aiohttp.web.Response(text=await render_template(request, name, **kwargs), content_type='text/html')


routes = aiohttp.web.RouteTableDef()


@routes.get('/api/docs/')
async def index(request):
    return await render_to_response(request, 'index.html')


@routes.get('/api/docs/restful/')
async def restful(request):
    return await render_to_response(request, 'restful.html')


@routes.get('/api/docs/websocket/')
async def websocket(request):
    middleware = request.app['middleware']
    services = []
    for name in sorted(await middleware.call('core.get_services')):
        services.append({
            'name': name,
            'methods': await middleware.call('core.get_methods', name),
        })
    events = await render_template(request, 'websocket/events.md', **{
        'events': await middleware.call('core.get_events')
    })

    query_filters = await render_template(request, 'websocket/query.md')
    protocol = await render_template(request, 'websocket/protocol.md')
    jobs = await render_template(request, 'websocket/jobs.md')
    return await render_to_response(request, 'websocket.html', **{
        'events': events,
        'services': services,
        'protocol': protocol,
        'jobs': jobs,
        'query_filters': query_filters,
    })
