#+
# Copyright 2014 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################


import json
import inspect
from flask import Flask, render_template, redirect, url_for
from flask_bootstrap import Bootstrap
from fnutils import materialized_paths_to_tree


app = Flask(__name__)
dispatcher = None
Bootstrap(app)


@app.route('/')
def index():
    return redirect(url_for('rpc'))


@app.route('/events')
def events():
    return render_template('events.html')


@app.route('/rpc')
def rpc():
    return render_template('rpc.html')


@app.route('/tasks')
def tasks():
    return render_template('tasks.html')


@app.route('/term')
def term():
    return render_template('term.html')


@app.route('/stats')
def stats():
    return render_template('stats.html')


@app.route('/apidoc')
def apidoc():
    return render_template('apidoc/index.html')


@app.route('/apidoc/rpc')
def apidoc_rpc():
    services = dispatcher.rpc.instances
    return render_template('apidoc/rpc.html', services=services)


@app.route('/apidoc/tasks')
def apidoc_tasks():
    tasks = dispatcher.tasks
    return render_template('apidoc/tasks.html', tasks=tasks)


@app.route('/apidoc/events')
def apidoc_events():
    events = dispatcher.event_types
    tree = materialized_paths_to_tree(events.keys())
    return render_template('apidoc/events.html', events=events, tree=tree)


@app.route('/apidoc/schemas')
def apidoc_schemas():
    schemas = dispatcher.rpc.schema_definitions
    return render_template('apidoc/schemas.html', schemas=schemas)


@app.template_filter('json')
def json_filter(obj):
    return json.dumps(obj, indent=4)


@app.template_filter('selector')
def jquery_selector_escape(s):
    return s.replace('.', r'\.')


@app.context_processor
def utils():
    def call_args(obj, method_name):
        method = getattr(obj, method_name)
        return inspect.getargspec(method)

    def prepare_args(args, schema):
        idx = 0
        for i in args:
            if i == 'self':
                continue

            if not schema or len(schema) <= idx:
                yield {
                    'name': i,
                    'type': None
                }

                idx += 1
                continue

            fragment = schema[idx]
            typ = None
            reference = False

            if '$ref' in fragment:
                typ = fragment['$ref']
                reference = True

            if 'type' in fragment:
                typ = fragment['type']

            yield {
                'name': i,
                'type': typ,
                'reference': reference
            }

            idx += 1

    return {
        'call_args': call_args,
        'prepare_args': prepare_args,
        'hasattr': hasattr,
        'getattr': getattr
    }