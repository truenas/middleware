import os
import sys
import fnmatch
import glob
import imp
import json
import logging
import logging.config
import logging.handlers
import argparse
import gevent
import daemon
import daemon.pidfile
import signal
from pyee import EventEmitter
from gevent import monkey, Greenlet
from gevent.wsgi import WSGIServer
from engine.server import Server as EngineServer
from datastore import get_datastore, DatastoreException
from rpc.rpc import RpcContext, RpcException
from api.handler import ApiHandler
from balancer import Balancer

DEFAULT_CONFIGFILE = '/conf/middleware.conf'
PLUGIN_DIRS = [
    os.path.join(os.path.dirname(os.path.realpath(__file__)), 'plugins/')
]

class Dispatcher(object):
    def __init__(self):
        self.preserved_files = []
        self.event_types = []
        self.event_sources = {}
        self.event_handlers = {}
        self.plugins = []
        self.threads = []
        self.queues = {}
        self.providers = {}
        self.tasks = {}
        self.logger = logging.getLogger('Main')
        self.balancer = None
        self.datastore = None
        self.ws_server = None
        self.http_server = None
        self.pidfile = None

    def init(self):
        self.datastore = get_datastore(
            self.config['datastore']['driver'],
            self.config['datastore']['dsn']
        )

        self.logger.info('Connected to datastore')

        self.balancer = Balancer(self)
        self.rpc = RpcContext(self)

    def start(self):
        for name, clazz in self.event_sources.items():
            source = clazz(self)
            self.threads.append(gevent.spawn(source.run))

        self.balancer.start()

    def read_config_file(self, file):
        try:
            f = open(file, 'r')
            data = json.load(f)
            f.close()
        except IOError, err:
            self.logger.error('Cannot read config file: %s', err.message)
            sys.exit(1)
        except ValueError, err:
            self.logger.error('Cannot read config file: not valid JSON')
            sys.exit(1)

        if data['dispatcher']['logging'] == 'syslog':
            handler = logging.handlers.SysLogHandler('/dev/log')
            self.preserved_files.append(handler.socket.fileno())
            self.logger.addHandler(handler)
            self.logger.info('Initialized syslog logger')

        self.config = data
        self.pidfile = data['dispatcher']['pidfile']

    def discover_plugins(self):
        for dir in PLUGIN_DIRS:
            self.logger.debug("Searching for plugins in %s", dir)
            self.__discover_plugin_dir(dir)

    def __discover_plugin_dir(self, dir):
        for i in glob.glob1(dir, "*.py"):
            self.__try_load_plugin(os.path.join(dir, i))

    def __try_load_plugin(self, path):
        self.logger.debug("Loading plugin from %s", path)
        plugin = imp.load_source("plugin", path)
        if hasattr(plugin, "_init"):
            plugin._init(self)

        self.dispatch_event("internal.plugin.loaded", {"name": os.path.basename(path)})

    def dispatch_event(self, name, args):
        self.logger.debug("New event of type %s. Params: %s", name, args)
        self.ws_server.broadcast_event("/events", "event", {"name": name, "args": args})

        if name in self.event_handlers:
            for h in self.event_handlers[name]:
                h()

    def register_event_handler(self, name, handler):
        if name not in self.event_handlers:
            self.event_handlers[name] = []

        self.event_handlers[name].append(handler)

    def register_event_source(self, name, clazz):
        self.logger.debug("New event source: %s provided by %s", name, clazz.__module__)
        self.event_sources[name] = clazz

    def register_task_handler(self, name, clazz):
        self.logger.debug("New task handler: %s", name)
        self.tasks[name] = clazz

    def register_provider(self, name, clazz):
        self.logger.debug("New provider: %s", name)
        self.providers[name] = clazz
        self.rpc.register_service(name, clazz)

    def require_collection(self, collection, pkey_type='uuid'):
        if not self.datastore.collection_exists(collection):
            self.datastore.collection_create(collection, pkey_type)

    def die(self):
        self.logger.warning('Exiting from "die" command')
        gevent.killall(self.threads)
        sys.exit(0)

class Server(EngineServer):
    def __init__(self, *args, **kwargs):
        self.dispatcher = kwargs.pop("dispatcher")
        self.connections = []
        super(Server, self).__init__(*args, **kwargs)

    def on_connection(self, engine_socket):
        conn = ServerConnection(engine_socket, self)
        self.connections.append(conn)

    def broadcast_event(self, ns, event, args):
        for i in self.connections:
            i.emit_event(event, args)


class ServerConnection(EventEmitter):
    def __init__(self, socket, server):
        super(ServerConnection, self).__init__()
        self.server = server
        self.socket = socket
        self.dispatcher = server.dispatcher
        self.pending_calls = {}
        self.event_masks = set()
        self.socket.on("message", self.on_message)

    def on_message(self, message):
        if not type(message) is str:
            return

        if not "namespace" in message:
            return

        message = json.loads(message)

        getattr(self, "on_{}_{}".format(message["namespace"], message["name"]))(message["id"], message["args"])

    def on_events_subscribe(self, id, event_masks):
        self.event_masks = set.union(self.event_masks, event_masks)

    def on_events_unsubscribe(self, id, event_masks):
        self.event_masks = set.difference(self.event_masks, event_masks)

    def on_rpc_call(self, id, data):
        def dispatch_call_async(id, method, args):
            try:
                result = self.dispatcher.rpc.dispatch_call(method, args)
            except RpcException as err:
                self.socket.send_json({
                    "namespace": "rpc",
                    "name": "error",
                    "id": id,
                    "args": {
                        "code": err.code,
                        "message": err.message
                    }
                })
            else:
                self.socket.send_json({
                    "namespace": "rpc",
                    "name": "response",
                    "id": id,
                    "args": result
                })

        method = data["method"]
        args = data["args"]
        greenlet = Greenlet(dispatch_call_async, id, method, args)
        self.pending_calls[id] = {
            "method": method,
            "args": args,
            "greenlet": greenlet
        }

        greenlet.start()


    def emit_event(self, event, args):
        for i in self.event_masks:
            if not fnmatch.fnmatch(event, i):
                continue

            self.socket.send_json({
                "namespace": "events",
                "name": "event",
                "id": None,
                "args": args
            })

def run(d, args):
    print "siema"
    sys.stdout.flush()
    monkey.patch_all()

    # Signal handlers
    gevent.signal(signal.SIGQUIT, gevent.kill)
    gevent.signal(signal.SIGINT, gevent.kill)

    # WebSockets server
    app = ApiHandler(d)
    s = Server(('', args.p), app, resource="socket", dispatcher=d)
    d.ws_server = s
    serv_thread = gevent.spawn(s.serve_forever)

    logging.info('Listening on port %d and on port 10843 (flash policy server)', args.p)

    if args.s:
        # Debugging frontend server
        from frontend import frontend
        http_server = WSGIServer(('', args.s), frontend.app)
        gevent.spawn(http_server.serve_forever)
        logging.info('Frontend server listening on port %d', args.s)

    d.init()
    d.discover_plugins()
    d.start()
    gevent.joinall(d.threads + [serv_thread])


def main():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', type=int, metavar='PORT', default=8180, help="Run debug frontend server on port")
    parser.add_argument('-p', type=int, metavar='PORT', default=5000, help="WebSockets server port")
    parser.add_argument('-f', action='store_true', help='Do not daemonize')
    parser.add_argument('-c', type=str, metavar='CONFIG', default=DEFAULT_CONFIGFILE, help='Configuration file path')
    args = parser.parse_args()

    # Initialization and dependency injection
    d = Dispatcher()
    try:
        d.read_config_file(args.c)
    except:
        pass

    if args.f:
        run(d, args)
    else:
        ctx = daemon.DaemonContext(
            stdout=open('out.log', 'w+'),
            stderr=open('err.log', 'w+'),
            pidfile=daemon.pidfile.PIDLockFile(d.pidfile)
        )

        ctx.files_preserve = d.preserved_files
        ctx.open()

        sys.stdout.flush()
        run(d, args)




if __name__ == '__main__':
    main()