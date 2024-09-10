from typing import TYPE_CHECKING

from middlewared.api.base.handler.accept import model_dict_from_list
from middlewared.api.base.handler.dump_params import dump_params
from middlewared.api.base.handler.version import APIVersionsAdapter
from middlewared.api.base.server.method import Method
from middlewared.utils.service.call import MethodNotFoundError
from middlewared.utils.service.crud import real_crud_method

if TYPE_CHECKING:
    from middlewared.api.base.server.ws_handler.rpc import RpcWebSocketApp
    from middlewared.main import Middleware


class LegacyAPIMethod(Method):
    """
    Represents a middleware legacy API method used in JSON-RPC server. Converts method parameters and return value
    between most recent API version (used in the code) and predetermined legacy API version.
    """

    def __init__(self, middleware: "Middleware", name: str, api_version: str, adapter: APIVersionsAdapter):
        """
        :param middleware: `Middleware` instance
        :param name: method name
        :param api_version: API version name used to convert parameters and return value
        :param adapter: `APIVersionsAdapter` instance
        """
        super().__init__(middleware, name)
        self.api_version = api_version
        self.adapter = adapter

        methodobj = self.methodobj
        if crud_methodobj := real_crud_method(methodobj):
            methodobj = crud_methodobj
        if hasattr(methodobj, "new_style_accepts"):
            self.accepts_model = methodobj.new_style_accepts
            self.returns_model = methodobj.new_style_returns
        else:
            self.accepts_model = None
            self.returns_model = None

    async def call(self, app: "RpcWebSocketApp", params):
        if self.accepts_model:
            return self._adapt_result(await super().call(app, self._adapt_params(params)))

        return await super().call(app, params)

    def _adapt_params(self, params):
        try:
            legacy_accepts_model = self.adapter.versions[self.api_version].models[self.accepts_model.__name__]
        except KeyError:
            # The legacy API does not contain signature definition for this method, which means it didn't exist
            # when that API was released.
            raise MethodNotFoundError(*self.name.rsplit(".", 1))

        params_dict = model_dict_from_list(legacy_accepts_model, params)

        adapted_params_dict = self.adapter.adapt(
            params_dict,
            legacy_accepts_model.__name__,
            self.api_version,
            self.adapter.current_version,
        )

        return [adapted_params_dict[field] for field in self.accepts_model.model_fields]

    def _adapt_result(self, result):
        return self.adapter.adapt(
            {"result": result},
            self.returns_model.__name__,
            self.adapter.current_version,
            self.api_version,
        )["result"]

    def dump_args(self, params):
        if self.accepts_model:
            return dump_params(self.accepts_model, params, False)

        return super().dump_args(params)
