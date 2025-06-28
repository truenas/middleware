from typing import Any, TYPE_CHECKING

from middlewared.api.base.handler.accept import model_dict_from_list
from middlewared.api.base.handler.dump_params import dump_params
from middlewared.api.base.handler.version import APIVersionsAdapter, APIVersionDoesNotContainModelException
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

    def __init__(self, middleware: "Middleware", name: str, api_version: str, adapter: APIVersionsAdapter, *,
                 passthrough_nonexistent_methods=False):
        """
        :param middleware: `Middleware` instance
        :param name: method name
        :param api_version: API version name used to convert parameters and return value
        :param adapter: `APIVersionsAdapter` instance
        """
        super().__init__(middleware, name)
        self.api_version = api_version
        self.adapter = adapter
        # FIXME: Remove this when legacy WS API is removed
        self.passthrough_nonexistent_methods = passthrough_nonexistent_methods

        methodobj = self.methodobj
        if crud_methodobj := real_crud_method(methodobj):
            methodobj = crud_methodobj

        if hasattr(methodobj, "new_style_accepts"):
            self.current_accepts_model = methodobj.new_style_accepts
            self.current_returns_model = methodobj.new_style_returns
        else:
            self.current_accepts_model = None
            self.current_returns_model = None

    async def accepts_model(self):
        try:
            return await self.adapter.versions[self.api_version].get_model(self.current_accepts_model.__name__)
        except APIVersionDoesNotContainModelException:
            return None

    async def returns_model(self):
        try:
            return await self.adapter.versions[self.api_version].get_model(self.current_returns_model.__name__)
        except (KeyError, APIVersionDoesNotContainModelException):
            return None

    async def call(self, app: "RpcWebSocketApp", id_: Any, params):
        if self.current_accepts_model:
            params = await self._adapt_params(params)

        return await super().call(app, id_, params)

    async def _adapt_params(self, params):
        try:
            legacy_accepts_model = await self.adapter.versions[self.api_version].get_model(
                self.current_accepts_model.__name__
            )
        except APIVersionDoesNotContainModelException:
            if self.passthrough_nonexistent_methods:
                return params

            # The legacy API does not contain signature definition for this method, which means it didn't exist
            # when that API was released.
            raise MethodNotFoundError(*reversed(self.name.rsplit(".", 1)))

        params_dict = model_dict_from_list(legacy_accepts_model, params)

        adapted_params_dict = await self.adapter.adapt(
            params_dict,
            legacy_accepts_model.__name__,
            self.api_version,
            self.adapter.current_version,
        )

        return [adapted_params_dict[field] for field in self.current_accepts_model.model_fields]

    async def _dump_result(self, app: "RpcWebSocketApp", methodobj, result):
        if self.current_accepts_model:  # FIXME: Remove this check when all models become new style
            try:
                model, result = await self.adapter.adapt_model(
                    {"result": result},
                    self.current_returns_model.__name__,
                    self.adapter.current_version,
                    self.api_version,
                )
            except APIVersionDoesNotContainModelException:
                if self.passthrough_nonexistent_methods:
                    return await super()._dump_result(app, methodobj, result)

                raise

            return self.middleware.dump_result(self.serviceobj, methodobj, app, result["result"],
                                               new_style_returns_model=model)

        return await super()._dump_result(app, methodobj, result)

    def dump_args(self, params):
        if self.current_accepts_model:  # FIXME: Remove this check when all models become new style
            return dump_params(self.current_accepts_model, params, False)

        return super().dump_args(params)
