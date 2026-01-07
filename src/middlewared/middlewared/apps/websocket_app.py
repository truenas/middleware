from asyncio import AbstractEventLoop, shield
from binascii import b2a_base64
from errno import EACCES, EAGAIN, EINVAL, ETOOMANYREFS
from pickle import dumps as pdumps
from sys import exc_info
from traceback import format_exception
from typing import Any, Callable, TYPE_CHECKING
from types import AsyncGeneratorType, GeneratorType

from middlewared.api.base.server.legacy_api_method import LegacyAPIMethod
from middlewared.api.base.server.ws_handler.rpc import (
    RpcWebSocketApp,
    RpcWebSocketAppEvent,
)
from middlewared.job import Job
from middlewared.logger import Logger
from middlewared.service_exception import (
    adapt_exception,
    CallError,
    CallException,
    ValidationError,
    ValidationErrors,
    get_errname,
)
from middlewared.utils.debug import get_frame_details
from middlewared.utils.lock import SoftHardSemaphore, SoftHardSemaphoreLimit
from middlewared.utils.origin import ConnectionOrigin
from middlewared.utils.threading import run_coro_threadsafe
from middlewared.utils.types import OptExcInfo
from truenas_api_client import json
if TYPE_CHECKING:
    from aiohttp.web import WebSocketResponse, Request
    from middlewared.main import Middleware
    from middlewared.service import Service


__all__ = ("WebSocketApplication",)


class WebSocketApplication(RpcWebSocketApp):
    def __init__(
        self,
        middleware: "Middleware",
        origin: ConnectionOrigin,
        loop: AbstractEventLoop,
        request: "Request",
        response: "WebSocketResponse",
    ):
        super().__init__(middleware, origin, response)
        self.websocket = True
        self.loop = loop
        self.request = request
        self.response = response
        self.handshake = False
        self.logger = Logger("websock_app").getLogger()
        # Allow atmost 10 concurrent calls and only queue up until 20
        self._softhardsemaphore = SoftHardSemaphore(10, 20)
        self._py_exceptions = False
        self.__subscribed: dict[str, str] = {}

    def _send(self, data: dict[str, Any]):
        run_coro_threadsafe(self.response.send_str(json.dumps(data)), loop=self.loop)

    def _tb_error(self, exc_info: OptExcInfo) -> dict:
        klass, exc, trace = exc_info
        frames = []
        cur_tb = trace
        while cur_tb:
            tb_frame = cur_tb.tb_frame
            cur_tb = cur_tb.tb_next
            cur_frame = get_frame_details(tb_frame, self.logger)
            if cur_frame:
                frames.append(cur_frame)

        return {
            "class": klass.__name__,
            "frames": frames,
            "formatted": "".join(format_exception(*exc_info)),
            "repr": repr(exc_info[1]),
        }

    def get_error_dict(
        self,
        errno: int,
        reason: str | None = None,
        exc_info: OptExcInfo | None = None,
        etype: str | None = None,
        extra: list | None = None,
    ) -> dict[str, Any]:
        error_extra = {}
        if self._py_exceptions and exc_info:
            error_extra["py_exception"] = b2a_base64(pdumps(exc_info[1])).decode()
        return dict(
            {
                "error": errno,
                "errname": get_errname(errno),
                "type": etype,
                "reason": reason,
                "trace": self._tb_error(exc_info) if exc_info else None,
                "extra": extra,
            },
            **error_extra,
        )

    def send_error(
        self,
        message: dict[str, Any],
        errno: int,
        reason: str | None = None,
        exc_info: OptExcInfo | None = None,
        etype: str | None = None,
        extra: list | None = None,
    ):
        self._send(
            {
                "msg": "result",
                "id": message["id"],
                "error": self.get_error_dict(errno, reason, exc_info, etype, extra),
            }
        )

    async def call_method(self, message: dict, serviceobj: "Service", methodobj: Callable):
        params = message.get("params") or []
        if not isinstance(params, list):
            self.send_error(message, EINVAL, "`params` must be a list.")
            return

        if mock := self.middleware._mock_method(message["method"], params):
            methodobj = mock

        try:
            # For any legacy websocket API method call not defined in 24.10 models we assume its made using the most
            # recent API.
            # If the method is defined there, we perform conversion to the recent API.
            lam = LegacyAPIMethod(
                self.middleware,
                message["method"],
                "v24.10",
                self.middleware.api_versions_adapter,
                passthrough_nonexistent_methods=True,
            )
            if lam.current_accepts_model:
                params = await lam._adapt_params(params)

            async with self._softhardsemaphore:
                result = await self.middleware.call_with_audit(
                    message["method"], serviceobj, methodobj, params, self
                )

            if isinstance(result, Job):
                result = result.id
            elif isinstance(result, GeneratorType):
                result = list(result)
            elif isinstance(result, AsyncGeneratorType):
                result = [i async for i in result]
            else:
                if await lam.returns_model():
                    result = await lam._dump_result(self, methodobj, result)
                else:
                    result = self.middleware.dump_result(
                        serviceobj, methodobj, self, result
                    )

            self._send(
                {
                    "id": message["id"],
                    "msg": "result",
                    "result": result,
                }
            )
        except SoftHardSemaphoreLimit as e:
            self.send_error(
                message,
                ETOOMANYREFS,
                f"Maximum number of concurrent calls ({e.args[0]}) has exceeded.",
            )
        except ValidationError as e:
            self.send_error(
                message,
                e.errno,
                str(e),
                exc_info(),
                etype="VALIDATION",
                extra=[
                    (e.attribute, e.errmsg, e.errno),
                ],
            )
        except ValidationErrors as e:
            self.send_error(
                message, EAGAIN, str(e), exc_info(), etype="VALIDATION", extra=list(e)
            )
        except CallException as e:
            # CallException and subclasses are the way to gracefully
            # send errors to the client
            self.send_error(message, e.errno, str(e), exc_info(), extra=e.extra)
        except Exception as e:
            adapted = adapt_exception(e)
            if adapted:
                self.send_error(
                    message,
                    adapted.errno,
                    str(adapted) or repr(adapted),
                    exc_info(),
                    extra=adapted.extra,
                )
            else:
                self.send_error(message, EINVAL, str(e) or repr(e), exc_info())
                if not self._py_exceptions:
                    self.logger.warning(
                        "Exception while calling {}(*{})".format(
                            message["method"],
                            self.middleware.dump_args(
                                message.get("params", []), method_name=message["method"]
                            ),
                        ),
                        exc_info=True,
                    )

    async def subscribe(self, ident, name):
        shortname, arg = self.middleware.event_source_manager.short_name_arg(name)
        if shortname in self.middleware.event_source_manager.event_sources:
            await self.middleware.event_source_manager.subscribe_app(
                self, self.__esm_ident(ident), shortname, arg
            )
        else:
            self.__subscribed[ident] = name

        self._send(
            {
                "msg": "ready",
                "subs": [ident],
            }
        )

    async def unsubscribe(self, ident):
        if ident in self.__subscribed:
            self.__subscribed.pop(ident)
        elif self.__esm_ident(ident) in self.middleware.event_source_manager.idents:
            await self.middleware.event_source_manager.unsubscribe(
                self.__esm_ident(ident)
            )

    def __esm_ident(self, ident):
        return self.session_id + ident

    def send_event(self, name, event_type, **kwargs):
        if (
            not any(i == name or i == "*" for i in self.__subscribed.values())
            and self.middleware.event_source_manager.short_name_arg(name)[0]
            not in self.middleware.event_source_manager.event_sources
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
        self._send(event)

    def notify_unsubscribed(self, collection, error):
        error_dict = {}
        if error:
            if isinstance(error, ValidationErrors):
                error_dict["error"] = self.get_error_dict(
                    EAGAIN, str(error), etype="VALIDATION", extra=list(error)
                )
            elif isinstance(error, CallError):
                error_dict["error"] = self.get_error_dict(
                    error.errno, str(error), extra=error.extra
                )
            else:
                error_dict["error"] = self.get_error_dict(EINVAL, str(error))

        self._send({"msg": "nosub", "collection": collection, **error_dict})

    async def __log_audit_message_for_method(
        self, message, methodobj, authenticated, authorized, success
    ):
        return await self.middleware.log_audit_message_for_method(
            message["method"],
            methodobj,
            message.get("params") or [],
            self,
            authenticated,
            authorized,
            success,
        )

    def on_open(self):
        self.middleware.register_wsclient(self)

    async def on_close(self):
        await self.run_callback(RpcWebSocketAppEvent.CLOSE)

        await self.middleware.event_source_manager.unsubscribe_app(self)

        self.middleware.unregister_wsclient(self)

    async def on_message(self, message: dict[str, Any]):
        await self.run_callback(RpcWebSocketAppEvent.MESSAGE, message)

        if message["msg"] == "connect":
            if message.get("version") != "1":
                self._send({"msg": "failed", "version": "1"})
            else:
                features = message.get("features") or []
                if "PY_EXCEPTIONS" in features:
                    self._py_exceptions = True
                # aiohttp can cancel tasks if a request take too long to finish
                # It is desired to prevent that in this stage in case we are debugging
                # middlewared via gdb (which makes the program execution a lot slower)
                await shield(self.middleware.call_hook("core.on_connect", app=self))
                self._send({"msg": "connected", "session": self.session_id})
                self.handshake = True
        elif not self.handshake:
            self._send({"msg": "failed", "version": "1"})
        elif message["msg"] == "method":
            if "method" not in message:
                self.send_error(
                    message, EINVAL, "Message is malformed: 'method' is absent."
                )
            else:
                try:
                    serviceobj, methodobj = self.middleware.get_method(
                        message["method"]
                    )

                    await self.middleware.authorize_method_call(
                        self,
                        message["method"],
                        methodobj,
                        message.get("params") or [],
                    )
                except CallError as e:
                    self.send_error(message, e.errno, str(e), exc_info(), extra=e.extra)
                else:
                    self.middleware.create_task(
                        self.call_method(message, serviceobj, methodobj)
                    )
        elif message["msg"] == "sub":
            if not self.middleware.can_subscribe(
                self, message["name"].split(":", 1)[0]
            ):
                self.send_error(message, EACCES, "Not authorized")
            else:
                await self.subscribe(message["id"], message["name"])
        elif message["msg"] == "unsub":
            await self.unsubscribe(message["id"])

    def __getstate__(self):
        return {}

    def __setstate__(self, newstate):
        pass
