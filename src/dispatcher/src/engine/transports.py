import json
import urlparse
import gevent

from geventwebsocket import WebSocketError
from pyee import EventEmitter

import logging
import re
from .parser import Parser

logger = logging.getLogger(__name__)

class BaseTransport(EventEmitter):
    """
    Base class for all transports. Mostly wraps handler class functions.

    Life cycle for a transport:
    A transport object lives cross the whole socket session.
    One handler lives for one request, so one transport will survive for
    multiple handler objects.

    """
    name = "Base"

    def __init__(self, handler, config, **kwargs):
        """Base transport class.

        :param config: dict Should contain the config keys, like
          ``heartbeat_interval``, ``heartbeat_timeout`` and
          ``close_timeout``.

        """

        super(BaseTransport, self).__init__()

        self.content_type = ("Content-Type", "text/plain; charset=UTF-8")
        self.headers = [
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Credentials", "true"),
            ("Access-Control-Allow-Methods", "POST, GET, OPTIONS"),
            ("Access-Control-Max-Age", 3600),
        ]

        self.supports_binary = config.pop("supports_binary", True)
        self.ready_state = "opening"

        self.handler = handler
        self.config = config

        self.request = None
        self.writable = False
        self.should_close = False

    def write(self, data=""):
        # Gevent v 0.13
        if hasattr(self.handler, 'response_headers_list'):
            if 'Content-Length' not in self.handler.response_headers_list:
                self.handler.response_headers.append(('Content-Length', len(data)))
                self.handler.response_headers_list.append('Content-Length')
        elif not hasattr(self.handler, 'provided_content_length') or self.handler.provided_content_length is None:
            # Gevent 1.0bX
            l = len(data)
            self.handler.provided_content_length = l
            self.handler.response_headers.append(('Content-Length', l))

        self.handler.write_smart(data)

    def do_close(self):
        raise NotImplementedError()

    def close(self):
        self.ready_state = 'closing'
        if not self.request.response.is_set:
            # Close the response when the transport closes
            self.request.response.end(200, 'closed')
        self.do_close()

    def _cleanup(self):
        logger.debug('clean up in transport')
        self.handler.remove_listener('cleanup', self._cleanup)
        self.request = None
        self.handler = None

    def on_request(self, request):
        self.handler = request.handler
        self.request = request

        self.handler.on("cleanup", self._cleanup)

    def on_error(self, message):
        if self.listeners('error'):
            self.emit('error', {
                'type': 'TransportError',
                'description': message
            })
        else:
            logger.debug("Ignored transoport error %s" % message)

    def on_packet(self, packet):
        self.emit('packet', packet)

    def on_data(self, data):
        self.on_packet(Parser.decode_packet(data))

    def on_close(self):
        self.ready_state = 'closed'
        self.emit('close')


class PollingTransport(BaseTransport):
    name = "polling"

    def __init__(self, *args, **kwargs):
        self.data_request = None
        super(PollingTransport, self).__init__(*args, **kwargs)

    def on_request(self, request):
        # We intentionally not call super

        if request.method == 'GET':
            self.on_poll_request(request)
        elif request.method == 'POST':
            self.on_data_request(request)
        else:
            pass

    def _cleanup(self):
        self._cleanup_data()
        self._cleanup_poll()
        super(PollingTransport, self)._cleanup()

    def _cleanup_poll(self):
        self.request.response.remove_listener('post_end', self._cleanup_poll)
        self.request = None

    def _cleanup_data(self):
        self.data_request.response.remove_listener('post_end', self._cleanup_data)
        self.data_request = None

    def on_poll_request(self, request):
        if self.request is not None and self.request is not request:
            logger.debug('request overlap')
            self.on_error('overlap from client')
            self.request.response.end(500)

        logger.debug('setting request')

        self.request = request
        request.response.on('post_end', self._cleanup_poll)

        def pre_end():
            self.writable = False
        request.response.on('pre_end', pre_end)

        self.writable = True

        # Flush the socket in case some buffered message
        self.emit('drain')

        if self.should_close:
            logger.debug('triggering empty send to append close packet')
            self.send([{'type': 'noop'}])

    def on_data_request(self, request):
        """
        The client sends a request with data.
        :param request:
        :return:
        """
        is_binary = 'application/octet-stream' == request.headers.get('content-type', 'None')
        self.data_request = request
        self.data_request.response.on('post_end', self._cleanup_data)

        chunks = bytearray() if is_binary else ''

        chunks += self.data_request.body
        self.on_data(chunks)
        self.data_request.response.headers = self.data_request.headers
        self.data_request.response.headers.update({
            'Content-Length': 2,
            'Content-Type': 'text/html'
        })
        self.data_request.response.end(status_code=200, body='ok')

    def on_data(self, data):
        """
        Processes the incoming data payload
        :param data:
        :return:
        """

        logger.debug('received %s', data)

        for packet, index, total in Parser.decode_payload(data):
            if packet['type'] == 'close':
                logger.debug('got xhr close packet')
                self.on_close()
                break
            self.on_packet(packet)

    def send(self, packets):
        """
        Encode and Send packets
        :param packets: The packets list
        :return: None
        """
        if self.should_close:
            packets.push({type: 'close'})
            self.on('should_close')
            self.should_close = False

        encoded = Parser.encode_payload(packets, self.supports_binary)
        self.write(encoded)

    def write(self, data=""):
        logger.debug('writing %s' % data)

        self.do_write(data)

    def do_write(self, data):
        raise NotImplementedError()

    def do_close(self):
        logger.debug('closing')

        if self.data_request:
            logger.debug('aborting ongoing data request')
            # self.data_request.abort()

        if self.writable:
            self.send([{'type': 'close'}])

        else:
            logger.debug('transport not writable - buffering orderly close')
            self.should_close = True


class XHRPollingTransport(PollingTransport):

    def on_request(self, request):
        super(XHRPollingTransport, self).on_request(request)

        if request.method in ('POST', 'OPTIONS'):
            request.response.headers['Access-Control-Allow-Credentials'] = 'true'
            request.response.headers['Access-Control-Allow-Origin'] = request.headers['origin']
            request.response.headers['Access-Control-Allow-Headers'] = 'Content-Type'

        if request.method == 'OPTIONS':
            request.response.end(status_code=200)

    def do_write(self, data):
        is_string = type(data) == str
        content_type = 'text/plain; charset=UTF-8' if is_string else 'application/octet-stream'
        content_length = str(len(data))

        headers = {
            'Content-Type': content_type,
            'Content-Length': content_length
        }

        ua = self.request.headers['user-agent']
        if ua and (ua.find(';MSIE') == -1 or ua.find('Trident/') == -1):
            headers['X-XSS-Protection'] = '0'

        headers = self.merge_headers(self.request, headers)
        self.request.response.headers = headers
        self.request.response.body += bytes(data)
        self.request.response.end()

    def merge_headers(self, request, headers=None):
        if not headers:
            headers = {}

        if 'origin' in request.headers:
            headers['Access-Control-Allow-Credentials'] = 'true'
            headers['Access-Control-Allow-Origin'] = request.headers['origin']
        else:
            headers['Access-Control-Allow-Origin'] = '*'
        return headers


class JSONPollingTransport(PollingTransport):
    def __init__(self, request, handler, config):
        super(JSONPollingTransport, self).__init__(handler, config)
        cn = re.sub('[^0-9]', '', self.request.query['j'] or '')
        self.head = '___eio[' + cn + ']('
        self.foot = ');'

    def on_data(self, data):
        data = urlparse.parse_qsl(data)['d']

        if type(data) == str:
            # TODO ESCAPE HANDLING
            super(JSONPollingTransport, self).on_data(data)

    def do_write(self, data):
        js = json.dumps(data)

        args = urlparse.parse_qs(self.handler.environ.get("QUERY_STRING"))
        if "i" in args:
            i = args["i"]
        else:
            i = "0"

        super(JSONPollingTransport, self).write("io.j[%s]('%s');" % (i, js))


class WebsocketTransport(BaseTransport):
    name = 'websocket'
    handles_upgrades = True
    supports_framing = True

    def __init__(self, *args, **kwargs):
        self.websocket = None
        self.jobs = []
        super(WebsocketTransport, self).__init__(*args, **kwargs)

    def on_request(self, request):
        self.request = request
        if hasattr(request, 'websocket'):
            self.websocket = request.websocket

            def read_from_ws():
                while True:
                    try:
                        message = self.websocket.receive()
                    except WebSocketError:
                        self.close()

                    if message is None:
                        break

                    self.on_data(message)

            job = gevent.spawn(read_from_ws)
            self.jobs.append(job)

        else:
            request.response.end(500, 'not able to create websocket')

    def send(self, packets):
        for packet in packets:
            encoded = Parser.encode_packet(packet, self.supports_binary)
            logger.debug('writing %s', encoded)
            self.writable = False
            try:
                self.websocket.send(encoded)
            except WebSocketError:
                self.close()

            self.writable = True

    def do_close(self):
        logger.debug('clean all the jobs')
        for job in self.jobs:
            gevent.kill(job)
        self.websocket.close()
