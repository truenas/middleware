import json
import markdown
from markdown.extensions.codehilite import CodeHiliteExtension

from .proxy import ReverseProxied
from flask import Flask, render_template
from middlewared.client import Client

app = Flask(__name__)
app.wsgi_app = ReverseProxied(app.wsgi_app)


@app.template_filter()
def json_filter(value):
    if isinstance(value, dict):
        value.pop('_required_', None)
    return json.dumps(value, indent=True)


@app.template_filter()
def markdown_filter(value):
    if not value:
        return value
    return markdown.markdown(value, extensions=[CodeHiliteExtension(noclasses=True)])


app.jinja_env.filters['json'] = json_filter
app.jinja_env.filters['markdown'] = markdown_filter


@app.route('/')
def main():
    return render_template('index.html')


@app.route('/restful/')
def restful():
    return render_template('restful.html')


@app.route('/websocket/')
def websocket():
    services = []
    # FIXME: better way to call middleware using asyncio insteaad of using client
    with Client() as c:
        for name in sorted(c.call('core.get_services')):
            services.append({
                'name': name,
                'methods': c.call('core.get_methods', name)
            })
        events = render_template('websocket/events.md', **{'events': c.call('core.get_events')})

    query_filters = render_template('websocket/query.md')
    protocol = render_template('websocket/protocol.md')
    jobs = render_template('websocket/jobs.md')
    return render_template('websocket.html', **{
        'events': events,
        'services': services,
        'protocol': protocol,
        'jobs': jobs,
        'query_filters': query_filters,
    })
