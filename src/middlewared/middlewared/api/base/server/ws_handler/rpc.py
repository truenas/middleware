from __future__ import annotations
import asyncio
import binascii
from collections import defaultdict
import enum
import errno
import pickle
import sys
import traceback
from typing import Any, Callable, TYPE_CHECKING

from aiohttp.http_websocket import WSCloseCode, WSMessage
from aiohttp.web import WebSocketResponse, WSMsgType

from truenas_api_client import json
from truenas_api_client.jsonrpc import JSONRPCError

from middlewared.service_exception import (
    CallException, CallError, ValidationError, ValidationErrors, adapt_exception, get_errname
)
from middlewared.utils.auth import AUID_UNSET, AUID_FAULTED
from middlewared.utils.debug import get_frame_details
from middlewared.utils.lang import undefined
from middlewared.utils.limits import MsgSizeError, MsgSizeLimit, parse_message
from middlewared.utils.lock import SoftHardSemaphore, SoftHardSemaphoreLimit
from middlewared.utils.origin import ConnectionOrigin, is_external_call
from .base import BaseWebSocketHandler
from ..app import App
from ..method import Method

if TYPE_CHECKING:
    from middlewared.main import Middleware
    from middlewared.utils.types import ExcInfo


class RpcWebSocketAppEvent(enum.Enum):
    MESSAGE = enum.auto()
    CLOSE = enum.auto()


class RpcWebSocketApp(App):
    def __init__(self, middleware: Middleware, origin: ConnectionOrigin, ws: WebSocketResponse):
        super().__init__(origin)

        self.websocket = True

        self.middleware = middleware
        self.ws = ws
        self.softhardsemaphore = SoftHardSemaphore(10, 20)
        self.callbacks: defaultdict[int, list[Callable]] = defaultdict(list)
        self.subscriptions: dict[str, str] = {}

    def send(self, data):
        try:
            data_ = json.dumps(data)
        except Exception as e:
            self.middleware.logger.error(f"{data}: Failed to JSON serialize server message: {e}", exc_info=True)
            self.send_truenas_error(
                data.get("id"),
                JSONRPCError.INTERNAL_ERROR.value,
                "Failed to JSON serialize server message",
                errno.EFAULT,
                str(e),
                sys.exc_info()
            )
        else:
            asyncio.run_coroutine_threadsafe(self.ws.send_str(data_), self.middleware.loop)

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

    def send_truenas_error(
        self,
        id_: Any,
        code: int,
        message: str,
        errno_: int,
        reason: str,
        exc_info: ExcInfo | None = None,
        extra: list | None = None,
    ):
        self.send_error(id_, code, message, self.format_truenas_error(errno_, reason, exc_info, extra))

    def format_truenas_error(
        self, errno_: int, reason: str, exc_info: ExcInfo | None = None, extra: list | None = None
    ) -> dict:
        result = {
            "error": errno_,
            "errname": get_errname(errno_),
            "reason": reason,
            "trace": self.truenas_error_traceback(exc_info) if exc_info else None,
            "extra": extra,
        }

        if self.py_exceptions and exc_info:
            try:
                result["py_exception"] = binascii.b2a_base64(pickle.dumps(exc_info[1])).decode()
            except Exception:
                self.middleware.logger.debug("Error pickling py_exception", exc_info=True)

        return result

    def truenas_error_traceback(self, exc_info: ExcInfo) -> dict:
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

    def send_truenas_validation_error(self, id_: Any, exc_info: ExcInfo, errors: list):
        self.send_error(
            id_,
            JSONRPCError.INVALID_PARAMS.value,
            "Invalid params",
            self.format_truenas_validation_error(exc_info[1], exc_info, errors),
        )

    def format_truenas_validation_error(
        self, exception: BaseException, exc_info: ExcInfo | None = None, errors: list | None = None
    ) -> dict:
        return self.format_truenas_error(errno.EINVAL, str(exception), exc_info, errors)

    def register_callback(self, event: RpcWebSocketAppEvent, callback: Callable):
        self.callbacks[event.value].append(callback)

    async def run_callback(self, event: RpcWebSocketAppEvent, *args, **kwargs):
        for callback in self.callbacks[event.value]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(self, *args, **kwargs)
                else:
                    await self.middleware.run_in_thread(callback, self, *args, **kwargs)
            except Exception:
                self.middleware.logger.error(f"Failed to run {event} callback", exc_info=True)

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

    def __esm_ident(self, ident: str):
        return self.session_id + ident

    def send_event(self, name: str, event_type: str, **kwargs):
        esm_ = self.middleware.event_source_manager
        if (
            not any(i in [name, "*"] for i in self.subscriptions.values())
            and esm_.short_name_arg(name)[0] not in esm_.event_sources
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
                params["error"] = self.format_truenas_validation_error(error, errors=list(error))
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
    def __init__(self, middleware: Middleware, methods: list[Method]):
        super().__init__(middleware)
        self.methods = {method.name: method for method in methods}

    async def process(self, origin: ConnectionOrigin, ws: WebSocketResponse):
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

                try:
                    message = parse_message(app.authenticated, msg.data)
                except MsgSizeError as err:
                    if err.limit is not MsgSizeLimit.UNAUTHENTICATED:
                        creds = app.authenticated_credentials.dump() if app.authenticated_credentials else None
                        origin = app.origin.repr if app.origin else None

                        self.middleware.logger.error(
                            'Client using credentials [%s] at [%s] sent message with payload size [%d bytes] '
                            'exceeding limit of %d for method %s',
                            creds, origin, err.datalen, err.limit, err.method_name
                        )

                    await ws.close(
                        code=err.ws_close_code,
                        message=err.ws_errmsg.encode('utf-8'),
                    )
                    break
                except ValueError as e:
                    app.send_error(None, JSONRPCError.INVALID_JSON.value, str(e))
                    continue

                await app.run_callback(RpcWebSocketAppEvent.MESSAGE, message)

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
            await app.run_callback(RpcWebSocketAppEvent.CLOSE)

            await self.middleware.event_source_manager.unsubscribe_app(app)

            self.middleware.unregister_wsclient(app)

    @staticmethod
    async def validate_message(message: Any) -> None:
        """
        Validate the message adheres to the JSON-RPC 2.0
        specification as described in the request_object section.
        Cf. https://www.jsonrpc.org/specification#request_object

        NOTE: This is a 'hot-path' so care should be taken to be
        as efficient as possible."""
        try:
            if message["jsonrpc"] != "2.0":
                raise ValueError(
                    "'jsonrpc' member must be of type string and must be exactly '2.0'"
                )
        except KeyError:
            raise ValueError("Missing 'jsonrpc' member")

        try:
            if not isinstance(message["id"], None | int | str):
                raise ValueError("'id' member must be of type null, string or number")
        except KeyError:
            pass

        try:
            if not isinstance(message["method"], str) or not message["method"]:
                raise ValueError("'method' member must be of type string")
        except KeyError:
            raise ValueError("Missing 'method' member")

        try:
            if not isinstance(message["params"], list):
                raise ValueError("'params' member must be of type array")
        except KeyError:
            message["params"] = []

    async def process_message(self, app: RpcWebSocketApp, message: dict):
        try:
            await self.validate_message(message)
        except ValueError as e:
            if (id_ := message.get("id", undefined)) != undefined:
                app.send_error(id_, JSONRPCError.INVALID_REQUEST.value, str(e))
            return

        id_ = message.get("id", undefined)

        try:
            method = self.methods[message["method"]]
        except KeyError:
            if id_ != undefined:
                app.send_error(id_, JSONRPCError.METHOD_NOT_FOUND.value, "Method does not exist")
            return
        if not app.private_methods and method.private and not self._can_call_private_methods(app):
            # FIXME: Eventually, prohibit this
            self.middleware.logger.warning(
                "Private method %r called on a connection without private_methods enabled",
                method.name
            )

        asyncio.ensure_future(
            self.process_method_call(app, id_, method, message["params"])
        )

    def _can_call_private_methods(self, app: RpcWebSocketApp) -> bool:
        if app.origin.uid == 33:
            # Calls made via WebSocket API
            return False

        if app.origin.loginuid in (AUID_UNSET, AUID_FAULTED):
            # System-initiated calls to `midclt`
            return True

        if ppids := app.origin.ppids():
            try:
                with open("/run/crond.pid") as f:
                    cron_pid = int(f.read())
            except (FileNotFoundError, ValueError):
                return False

            return cron_pid in ppids

        return False

    async def process_method_call(self, app: RpcWebSocketApp, id_: Any, method: Method, params: list):
        # Track external method calls
        if is_external_call(app):
            self.middleware.external_method_calls[method.name] += 1

        try:
            async with app.softhardsemaphore:
                result = await method.call(app, id_, params)
        except SoftHardSemaphoreLimit as e:
            if id_ != undefined:
                app.send_error(id_, JSONRPCError.TRUENAS_TOO_MANY_CONCURRENT_CALLS.value,
                               f"Maximum number of concurrent calls ({e.args[0]}) has exceeded")
        except ValidationError as e:
            if id_ != undefined:
                app.send_truenas_validation_error(id_, sys.exc_info(), [
                    (e.attribute, e.errmsg, e.errno),
                ])
        except ValidationErrors as e:
            if id_ != undefined:
                app.send_truenas_validation_error(id_, sys.exc_info(), list(e))
        except CallException as e:
            # CallException and subclasses are the way to gracefully send errors to the client
            if id_ != undefined:
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

            if id_ != undefined:
                app.send_truenas_error(id_, JSONRPCError.TRUENAS_CALL_ERROR.value, "Method call error", errno_,
                                       str(error) or repr(error), sys.exc_info(), extra)

            if not adapted and not app.py_exceptions:
                self.middleware.logger.warning(f"Exception while calling {method.name}(*{method.dump_args(params)!r})",
                                               exc_info=True)
        else:
            if isinstance(result, ValidationErrors):
                self.logger.debug("XXX: method: %s params: %s returned ValidationErrors", method, params)
                app.send_truenas_validation_error(id_, sys.exc_info(), list(result))
                return

            if id_ != undefined:
                app.send({
                    "jsonrpc": "2.0",
                    "result": result,
                    "id": id_,
                })
