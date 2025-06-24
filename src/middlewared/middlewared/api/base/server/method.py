import types
from typing import TYPE_CHECKING

from middlewared.job import Job

if TYPE_CHECKING:
    from middlewared.api.base.server.ws_handler.rpc import RpcWebSocketApp
    from middlewared.main import Middleware


class Method:
    """
    Represents a middleware API method used in JSON-RPC server.
    """

    def __init__(self, middleware: "Middleware", name: str):
        """
        :param middleware: `Middleware` instance
        :param name: method name
        """
        self.middleware = middleware
        self.name = name
        self.serviceobj, self.methodobj = self.middleware.get_method(self.name)

    async def accepts_model(self):
        """
        :return: model that validates method input params.
        """
        return self.methodobj.new_style_accepts

    async def returns_model(self):
        """
        :return: model that validates method return value.
        """
        return self.methodobj.new_style_returns

    async def call(self, app: "RpcWebSocketApp", params: list):
        """
        Calls the method in the context of a given `app`.

        :param app: `RpcWebSocketApp` instance.
        :param params: method arguments.
        :return: method return value.
        """
        methodobj = self.methodobj

        await self.middleware.authorize_method_call(app, self.name, methodobj, params)

        if mock := self.middleware._mock_method(self.name, params):
            methodobj = mock

        result = await self.middleware.call_with_audit(self.name, self.serviceobj, methodobj, params, app)
        if isinstance(result, Job):
            return result.id

        if isinstance(result, types.GeneratorType):
            result = list(result)
        elif isinstance(result, types.AsyncGeneratorType):
            result = [i async for i in result]

        return await self._dump_result(app, methodobj, result)

    async def _dump_result(self, app: "RpcWebSocketApp", methodobj, result):
        return self.middleware.dump_result(self.serviceobj, methodobj, app, result)

    def dump_args(self, params: list) -> list:
        """
        Dumps the method call params (i.e., removes secrets).

        :param params: method call arguments.
        :return: dumped method call arguments.
        """
        return self.middleware.dump_args(params, method_name=self.name)
