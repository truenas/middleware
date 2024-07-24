import asyncio
import binascii
from collections import defaultdict
import enum
import errno
import pickle
import sys
import traceback
from typing import Any, Callable

from aiohttp.http_websocket import WSCloseCode, WSMessage
from aiohttp.web import WebSocketResponse, WSMsgType
import jsonschema

from truenas_api_client import json
from truenas_api_client.jsonrpc import JSONRPCError

from middlewared.schema import Error
from middlewared.service_exception import (CallException, CallError, ValidationError, ValidationErrors, adapt_exception,
                                           get_errname)
from middlewared.utils.debug import get_frame_details
from middlewared.utils.lock import SoftHardSemaphore, SoftHardSemaphoreLimit
from middlewared.utils.origin import Origin
from .base import BaseWebSocketHandler
from ..app import App
from ..method import Method

REQUEST_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["jsonrpc", "method"],
    "properties": {
        "jsonrpc": {"enum": ["2.0"]},
        "method": {"type": "string"},
        "params": {"type": "array"},
        "id": {"type": ["null", "number", "string"]},
    }
}


class RpcWebSocketAppEvent(enum.Enum):
    MESSAGE = enum.auto()
    CLOSE = enum.auto()


class RpcWebSocketApp(App):
    def __init__(self, middleware: "Middleware", origin: Origin, ws: WebSocketResponse):
        super().__init__(origin)

        self.websocket = True

        self.middleware = middleware
        self.ws = ws
        self.softhardsemaphore = SoftHardSemaphore(10, 20)
        self.callbacks = defaultdict(list)
        self.subscriptions = {}

    def send(self, data):
        fut = asyncio.run_coroutine_threadsafe(self.ws.send_str(json.dumps(data)), self.middleware.loop)

    def send_error(self, id_: Any, code: int, message: str, data: Any = None):
        error = {
            "jsonrpc": "2.0",
            "error": {
                "code": code,
                "message": message,
            },
            "id": id_,
        }
        if data is not None:
            error["error"]["data"] = data

        self.send(error)

    def send_truenas_error(self, id_: Any, code: int, message: str, errno_: int, reason: str,
                           exc_info=None, extra: list | None = None):
        self.send_error(id_, code, message, self.format_truenas_error(errno_, reason, exc_info, extra))

    def format_truenas_error(self, errno_: int, reason: str, exc_info=None, extra: list | None = None):
        return {
            "error": errno_,
            "errname": get_errname(errno_),
            "reason": reason,
            "trace": self.truenas_error_traceback(exc_info) if exc_info else None,
            "extra": extra,
            **({"py_exception": binascii.b2a_base64(pickle.dumps(exc_info[1])).decode()}
               if self.py_exceptions and exc_info else {}),
        }

    def truenas_error_traceback(self, exc_info):
        etype, value, tb = exc_info

        frames = []
        cur_tb = tb
        while cur_tb:
            tb_frame = cur_tb.tb_frame
            cur_tb = cur_tb.tb_next

            cur_frame = get_frame_details(tb_frame, self.middleware.logger)
            if cur_frame:
                frames.append(cur_frame)

        return {
            "class": etype.__name__,
            "frames": frames,
            "formatted": "".join(traceback.format_exception(*exc_info)),
            "repr": repr(value),
        }

    def send_truenas_validation_error(self, id_: Any, exc_info, errors: list):
        self.send_error(id_, JSONRPCError.INVALID_PARAMS.value, "Invalid params",
                        self.format_truenas_validation_error(exc_info[1], exc_info, errors))

    def format_truenas_validation_error(self, exception, exc_info=None, errors: list | None = None):
        return self.format_truenas_error(errno.EINVAL, str(exception), exc_info, errors)

    def register_callback(self, event: RpcWebSocketAppEvent, callback: Callable):
        self.callbacks[event.value].append(callback)

    def run_callback(self, event, *args, **kwargs):
        for callback in self.callbacks[event.value]:
            try:
                callback(self, *args, **kwargs)
            except Exception:
                logger.error(f"Failed to run {event} callback", exc_info=True)

    async def subscribe(self, ident: str, name: str):
        shortname, arg = self.middleware.event_source_manager.short_name_arg(name)
        if shortname in self.middleware.event_source_manager.event_sources:
            await self.middleware.event_source_manager.subscribe_app(self, self.__esm_ident(ident), shortname, arg)
        else:
            self.subscriptions[ident] = name

    async def unsubscribe(self, ident: str):
        if ident in self.subscriptions:
            self.subscriptions.pop(ident)
        elif self.__esm_ident(ident) in self.middleware.event_source_manager.idents:
            await self.middleware.event_source_manager.unsubscribe(self.__esm_ident(ident))

    def __esm_ident(self, ident):
        return self.session_id + ident

    def send_event(self, name: str, event_type: str, **kwargs):
        if (
            not any(i in [name, "*"] for i in self.subscriptions.values()) and
            (
                self.middleware.event_source_manager.short_name_arg(name)[0] not in
                self.middleware.event_source_manager.event_sources
            )
        ):
            return

        event = {
            "msg": event_type.lower(),
            "collection": name,
        }
        kwargs = kwargs.copy()
        if "id" in kwargs:
            event["id"] = kwargs.pop("id")
        if event_type in ("ADDED", "CHANGED"):
            if "fields" in kwargs:
                event["fields"] = kwargs.pop("fields")
        if kwargs:
            event["extra"] = kwargs

        self.send_notification("collection_update", event)

    def notify_unsubscribed(self, collection: str, error: Exception | None):
        params = {"collection": collection, "error": None}
        if error:
            if isinstance(error, ValidationErrors):
                params["error"] = self.format_truenas_validation_error(error, extra=list(error))
            elif isinstance(error, CallError):
                params["error"] = self.format_truenas_error(error.errno, str(error), extra=error.extra)
            else:
                params["error"] = self.format_truenas_error(errno.EINVAL, str(error))

        self.send_notification("notify_unsubscribed", params)

    def send_notification(self, method, params):
        self.send({
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        })


class RpcWebSocketHandler(BaseWebSocketHandler):
    def __init__(self, middleware: "Middleware", methods: {str: Method}):
        super().__init__(middleware)
        self.methods = methods

    async def process(self, origin: Origin, ws: WebSocketResponse):
        app = RpcWebSocketApp(self.middleware, origin, ws)

        self.middleware.register_wsclient(app)
        try:
            # aiohttp can cancel tasks if a request take too long to finish.
            # It is desired to prevent that in this stage in case we are debugging middlewared via gdb (which makes the
            # program execution a lot slower)
            await asyncio.shield(self.middleware.call_hook("core.on_connect", app))

            msg: WSMessage
            async for msg in ws:
                if msg.type == WSMsgType.ERROR:
                    self.middleware.logger.error("Websocket error: %r", msg.data)
                    break

                if msg.type != WSMsgType.TEXT:
                    await ws.close(
                        code=WSCloseCode.UNSUPPORTED_DATA,
                        message=f"Invalid websocket message type: {msg.type!r}".encode("utf-8"),
                    )
                    break

                if not app.authenticated and len(msg.data) > 8192:
                    await ws.close(
                        code=WSCloseCode.INVALID_TEXT,
                        message=b"Anonymous connection max message length is 8 kB",
                    )
                    break

                try:
                    message = json.loads(msg.data)
                except ValueError as e:
                    app.send_error(None, JSONRPCError.INVALID_JSON.value, str(e))
                    continue

                app.run_callback(RpcWebSocketAppEvent.MESSAGE, message)

                try:
                    await self.process_message(app, message)
                except Exception as e:
                    self.middleware.logger.error("Unhandled exception in JSON-RPC message handler", exc_info=True)
                    await ws.close(
                        code=WSCloseCode.INTERNAL_ERROR,
                        message=str(e).encode("utf-8"),
                    )
                    break
        finally:
            app.run_callback(RpcWebSocketAppEvent.CLOSE)

            await self.middleware.event_source_manager.unsubscribe_app(app)

            self.middleware.unregister_wsclient(app)

    async def process_message(self, app: RpcWebSocketApp, message: Any):
        try:
            jsonschema.validate(message, REQUEST_SCHEMA)
        except jsonschema.ValidationError as e:
            app.send_error(app, None, JSONRPCError.INVALID_REQUEST.value, str(e))
            return

        id_ = message.get("id")
        method = self.methods.get(message["method"])
        if method is None:
            app.send_error(id_, JSONRPCError.METHOD_NOT_FOUND.value, "Method does not exist")
            return

        asyncio.ensure_future(self.process_method_call(app, id_, method, message["params"]))

    async def process_method_call(self, app: RpcWebSocketApp, id_: Any, method: Method, params: {str: Any}):
        try:
            async with app.softhardsemaphore:
                result = await method.call(app, params)
        except SoftHardSemaphoreLimit as e:
            app.send_error(id_, JSONRPCError.TRUENAS_TOO_MANY_CONCURRENT_CALLS.value,
                           f"Maximum number of concurrent calls ({e.args[0]}) has exceeded")
        except ValidationError as e:
            app.send_truenas_validation_error(id_, sys.exc_info(), [
                (e.attribute, e.errmsg, e.errno),
            ])
        except ValidationErrors as e:
            app.send_truenas_validation_error(id_, sys.exc_info(), list(e))
        except (CallException, Error) as e:
            # CallException and subclasses are the way to gracefully send errors to the client
            app.send_truenas_error(id_, JSONRPCError.TRUENAS_CALL_ERROR.value, "Method call error", e.errno, str(e),
                                    sys.exc_info(), e.extra)
        except Exception as e:
            adapted = adapt_exception(e)
            if adapted:
                errno_ = adapted.errno
                error = adapted
                extra = adapted.extra
            else:
                errno_ = errno.EINVAL
                error = e
                extra = None

            app.send_truenas_error(id_, JSONRPCError.TRUENAS_CALL_ERROR.value, "Method call error", errno_,
                                    str(error) or repr(error), sys.exc_info(), extra)

            if not adapted and not app.py_exceptions:
                self.middleware.logger.warning(f"Exception while calling {method.name}(*{method.dump_args(params)!r})",
                                               exc_info=True)
        else:
            app.send({
                "jsonrpc": "2.0",
                "result": result,
                "id": id_,
            })
