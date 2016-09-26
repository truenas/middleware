from . import ejson as json


class DDPProtocol(object):

    PROTOCOL_NAME = 'ddp'

    def __init__(self, app):
        self._app = app

    def on_open(self):
        self.app.on_open()

    def on_message(self, message):
        if message is None:
            return

        try:
            message = json.loads(message)
        except ValueError:
            raise Exception("Invalid JSON message")

        if 'msg' not in message:
            raise Exception("msg property not found")

        self.app.on_message(message)

    def on_close(self, code=0, reason=None):
        self.app.on_close(code, reason)

    @property
    def app(self):
        if self._app:
            return self._app
        else:
            raise Exception("No application coupled")
