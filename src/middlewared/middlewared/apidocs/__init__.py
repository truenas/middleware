import json

from .proxy import ReverseProxied
from flask import Flask, render_template

app = Flask(__name__)
app.wsgi_app = ReverseProxied(app.wsgi_app)


@app.template_filter()
def json_filter(value):
    return json.dumps(value, indent=True)

app.jinja_env.filters['json'] = json_filter


@app.route('/')
def main():
    services = []
    for name in app.middleware.call('core.get_services'):
        services.append({
           'name': name,
           'methods': app.middleware.call('core.get_methods', name)
        })
    return render_template('websocket.html', **{
        'services': services,
    })
