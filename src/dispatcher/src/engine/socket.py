"""
Engine socket, a abstract layer for all transports internal api. It is created by Engine.handler with proper parameters
and used by socketio.socket.
"""

import random
import logging
import json

import gevent
from gevent.queue import Queue
from gevent.event import Event
from pyee import EventEmitter

from engine import transports

__all__ = ['Socket']

logger = logging.getLogger(__name__)

handler_types = {
    'websocket': transports.WebsocketTransport,
    'polling': transports.XHRPollingTransport,
}


def default_error_handler(socket, error_name, error_message, endpoint,
                          msg_id, quiet):
    """This is the default error handler, you can override this when
    calling :func:`socketio.socketio_manage`.

    It basically sends an event through the socket with the 'error' name.

    See documentation for :meth:`Socket.error`.

    :param quiet: if quiet, this handler will not send a packet to the
                  user, but only log for the server developer.
    """
    pkt = dict(type='event', name='error',
               args=[error_name, error_message],
               endpoint=endpoint)
    if msg_id:
        pkt['id'] = msg_id

    # Send an error event through the Socket
    if not quiet:
        socket.send_packet('event', default_json_dumps(pkt))

    # Log that error somewhere for debugging...
    logger.error(u"default_error_handler: {}, {} (endpoint={}, msg_id={})".format(
        error_name, error_message, endpoint, msg_id
    ))


class Socket(EventEmitter):
    """
    Socket is the abstraction of the underlying transport
    it sends heartbeat packet periodically
    handles upgrade logic

    Internal:
    It creates several eventlet:
        heartbeat
        Server message handling
        Client message handling

    The main thread (gevent thread) should block during the request lifecycle.


    """

    STATE_NEW = "NEW"
    STATE_OPENING = "OPENING"
    STATE_OPEN = "OPEN"
    STATE_CLOSING = "CLOSING"
    STATE_CLOSED = "CLOSED"

    json_loads = json.loads
    json_dumps = json.dumps

    def __init__(self, request, ping_interval=5000, ping_timeout=10000, error_handler=None):
        super(Socket, self).__init__()

        self.request = request

        self.id = str(random.random())[2:]
        self.ready_state = self.STATE_NEW
        self.environ = None
        self.upgraded = False

        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout

        self.write_buffer = Queue()  # queue for messages to client
        self.server_queue = Queue()  # queue for messages to server

        self.timeout = Event()
        self.wsgi_app_greenlet = None
        self.send_packet_callbacks = []
        self.jobs = []
        self.error_handler = default_error_handler
        self.ping_timeout_eventlet = None
        self.check_eventlet = None
        self.upgrade_eventlet = None

        self.context = {} # Holder for framework specific data.

        transport_name = request.GET.get("transport", None)

        if transport_name not in handler_types:
            raise Exception('transport name not in query string')

        transport = handler_types[transport_name](request.handler, {})
        self._set_transport(transport)

        if error_handler is not None:
            self.error_handler = error_handler

    def _set_transport(self, transport):
        self.transport = transport
        self.transport.once('error', self.on_error)
        self.transport.on('packet', self.on_packet)

        # On drain event, we call flush_nowait which sends out buffered messages
        self.transport.on('drain', self.flush_nowait)
        self.transport.once('close', self.on_close)

    def _clear_transport(self):
        self.transport.on('error', lambda: logger.debug('error triggered by discarded transport'))
        if self.ping_timeout_eventlet:
            self.ping_timeout_eventlet.kill()

    def on_open(self):
        logger.debug('in on_open socket')
        self.ready_state = self.STATE_OPEN
        self.send_packet(
            "open",
            json.dumps({
                "sid": self.id,
                "upgrades": ["websocket"],
                # "upgrades": [],
                "pingInterval": 30000,
                "pingTimeout": 60000})
        )
        self.emit("open")
        self._set_ping_timeout_eventlet()

    def on_request(self, request):
        self.transport.on_request(request)

    def on_packet(self, packet):
        if self.STATE_OPEN == self.ready_state:
            logger.debug("packet")

            self.emit("packet", packet)
            self._set_ping_timeout_eventlet()

            packet_type = packet["type"]

            if packet_type == 'ping':
                logger.debug("got ping")
                self.send_packet('pong')

            elif packet_type == 'message':
                self.emit("message", packet['data'])

            elif packet_type == 'error':
                self.on_close("Parse error")

        else:
            logger.debug("Packet received with closed socket")

    def on_error(self, error=None):
        logger.debug("transport error: %s" % error)
        self.on_close('transport error', error)

    def on_close(self, reason, description=None):
        if self.STATE_CLOSED != self.ready_state:
            if self.ping_timeout_eventlet:
                self.ping_timeout_eventlet.kill()
                self.ping_timeout_eventlet = None

            if self.check_eventlet:
                self.check_eventlet.kill()
                self.check_eventlet = None

            if self.upgrade_eventlet:
                self.upgrade_eventlet.kill()
                self.upgrade_eventlet = None

            self._clear_transport()
            self.ready_state = self.STATE_CLOSED
            self.emit("close", reason, description)
            self.write_buffer = Queue()

    def _fail_upgrade(self, transport):
        logger.debug('client did not complete upgrade - closing transport')

        # Cancel jobs
        self.kill(detach=True)

        if self.check_eventlet:
            self.check_eventlet.kill()
            self.check_eventlet = None

        if 'open' == transport.ready_state:
            transport.close()

    def maybe_upgrade(self, transport):
        logger.debug("might upgrade from %s to %s" % (self.transport.name, transport.name))

        # TODO MAKE TIME OUT CONFIGURABLE
        self.upgrade_eventlet = gevent.spawn_later(1, self._fail_upgrade, transport)

        def check():
            if 'polling' == self.transport.name and self.transport.writable:
                logger.debug("writing a noop packet to polling for fast upgrade")
                self.transport.send([{
                                         "type": "noop"
                                     }])

        def on_packet(packet):
            if "ping" == packet["type"] and "probe" == packet["data"]:
                transport.send([{
                                    "type": "pong",
                                    "data": "probe"
                                }])

                if self.check_eventlet is not None:
                    self.check_eventlet.kill()

                def loop():
                    while True:
                        gevent.sleep(0.1)
                        check()

                self.check_eventlet = gevent.Greenlet.spawn(loop)

            elif 'upgrade' == packet["type"] and self.ready_state == self.STATE_OPEN:
                logger.debug("got upgrade packet - upgrading")
                self.upgraded = True
                self._clear_transport()
                self._set_transport(transport)
                self.emit("upgrade", transport)
                self._set_ping_timeout_eventlet()
                self.upgrade_eventlet.kill()
                self.flush_nowait()
                transport.remove_listener('packet', on_packet)
            else:
                transport.close()

        transport.on("packet", on_packet)

    def _set_ping_timeout_eventlet(self):
        if self.ping_timeout_eventlet:
            self.ping_timeout_eventlet.kill()

        def time_out():
            self.on_close('ping timeout')
        self.ping_timeout_eventlet = gevent.spawn_later(self.ping_interval + self.ping_timeout, time_out)

    def _set_environ(self, environ):
        """Save the WSGI environ, for future use.

        This is called by socketio_manage().
        """
        self.environ = environ

    def _set_error_handler(self, error_handler):
        """Changes the default error_handler function to the one specified

        This is called by socketio_manage().
        """
        self.error_handler = error_handler

    def _set_json_loads(self, json_loads):
        """Change the default JSON decoder.

        This should be a callable that accepts a single string, and returns
        a well-formed object.
        """
        self.json_loads = json_loads

    def _set_json_dumps(self, json_dumps):
        """Change the default JSON decoder.

        This should be a callable that accepts a single string, and returns
        a well-formed object.
        """
        self.json_dumps = json_dumps

    def _get_next_msgid(self):
        """This retrieves the next value for the 'id' field when sending
        an 'event' or 'message' or 'json' that asks the remote client
        to 'ack' back, so that we trigger the local callback.
        """
        self.ack_counter += 1
        return self.ack_counter

    def _save_ack_callback(self, msgid, callback):
        """Keep a reference of the callback on this socket."""
        if msgid in self.ack_callbacks:
            return False
        self.ack_callbacks[msgid] = callback

    def _pop_ack_callback(self, msgid):
        """Fetch the callback for a given msgid, if it exists, otherwise,
        return None"""
        if msgid not in self.ack_callbacks:
            return None
        return self.ack_callbacks.pop(msgid)

    def __str__(self):
        result = ['sessid=%r' % self.id]
        if self.ready_state == self.STATE_OPEN:
            result.append('open')
        if self.write_buffer.qsize():
            result.append('client_queue[%s]' % self.write_buffer.qsize())
        if self.server_queue.qsize():
            result.append('server_queue[%s]' % self.server_queue.qsize())

        return ' '.join(result)

    def __getitem__(self, key):
        """This will get the nested Namespace using its '/chat' reference.

        Using this, you can go from one Namespace to the other (to emit, add
        ACLs, etc..) with:

          adminnamespace.socket['/chat'].add_acl_method('kick-ban')

        """
        return self.active_ns[key]

    def __hasitem__(self, key):
        """Verifies if the namespace is active (was initialized)"""
        return key in self.active_ns

    def send(self, data):
        self.send_packet('message', data)
        return self

    def send_json(self, data):
        self.send_packet('message', json.dumps(data))
        return self

    write = send

    def send_packet(self, packet_type, data=None):
        """
        the primary send_packet method
        """
        logger.debug('send_packet in socket data [%s]' % data)
        packet = {
            "type": packet_type
        }

        if data:
            packet["data"] = data

        self.emit("packet_created", packet)

        if self.ready_state != self.STATE_CLOSING:
            self.put_client_msg(packet)
            self.flush()

    def flush_nowait(self):
        logger.debug("entering flushing buffer to transport " + str(self.transport.writable) + " " + str(self.write_buffer.qsize()))
        if self.ready_state != self.STATE_CLOSED and self.transport.writable and self.write_buffer.qsize():
            msg = []
            while self.write_buffer.qsize():
                msg.append(self.write_buffer.get())

            logger.debug("flushing buffer to transport")
            self.transport.send(msg)

    def flush(self):
        logger.debug("entering flushing buffer to transport " + str(self.transport.writable) + " " + str(self.write_buffer.qsize()))
        if self.ready_state != self.STATE_CLOSED and self.transport.writable:
            logger.debug('wait for the queue %s' % self.write_buffer.qsize())
            msg = [self.write_buffer.get()]
            while self.write_buffer.qsize():
                msg.append(self.write_buffer.get())

            logger.debug("flushing buffer to transport")
            self.transport.send(msg)

    def get_available_upgrades(self):
        availabel_upgrades = ["websocket"]
        # TODO FIX THIS, HOOK UP WITH SERVER
        return availabel_upgrades

    def close(self):
        if self.STATE_OPEN == self.ready_state:
            self.ready_state = self.STATE_CLOSING
            self.transport.close()  # TODO transport needs a close method

    def kill(self, detach=False):
        """This function must/will be called when a socket is to be completely
        shut down, closed by connection timeout, connection error or explicit
        disconnection from the client.

        It will call all of the Namespace's
        :meth:`~socketio.namespace.BaseNamespace.disconnect` methods
        so that you can shut-down things properly.

        """
        # Clear out the callbacks
        self.ack_callbacks = {}
        if self.STATE_OPEN == self.ready_state:
            self.ready_state = self.STATE_CLOSING
            self.server_queue.put_nowait(None)

        if detach:
            self.detach()

        gevent.killall(self.jobs)

    def detach(self):
        """Detach this socket from the server. This should be done in
        conjunction with kill(), once all the jobs are dead, detach the
        socket for garbage collection."""

        logger.debug("Removing %s sockets" % self)
        if self.id in self.request.handler.clients:
            self.request.handler.clients.pop(self.id)

    def put_client_msg(self, msg):
        """Writes to the client's pipe, to end up in the browser"""
        self.write_buffer.put(msg)

    def error(self, error_name, error_message, endpoint=None, msg_id=None,
              quiet=False):
        """Send an error to the user, using the custom or default
        ErrorHandler configured on the [TODO: Revise this] Socket/Handler
        object.

        :param error_name: is a simple string, for easy association on
                           the client side

        :param error_message: is a human readable message, the user
                              will eventually see

        :param endpoint: set this if you have a message specific to an
                         end point

        :param msg_id: set this if your error is relative to a
                       specific message

        :param quiet: way to make the error handler quiet. Specific to
                      the handler.  The default handler will only log,
                      with quiet.
        """
        handler = self.error_handler
        return handler(
            self, error_name, error_message, endpoint, msg_id, quiet)

    def spawn(self, fn, *args, **kwargs):
        """Spawn a new Greenlet, attached to this Socket instance.

        It will be monitored by the "watcher" method
        """

        logger.debug("Spawning sub-Socket Greenlet: %s" % fn.__name__)
        job = gevent.spawn(fn, *args, **kwargs)
        self.jobs.append(job)
        return job
