from typing import Any, Literal

from middlewared.alert.base import  AlertCategory, AlertClass, AlertLevel, SimpleOneShotAlertClass
from middlewared.role import Role
from middlewared.service import CallError, Service


class SystemTestingAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.CRITICAL
    title = "System mocking endpoints used"
    text = "System mocking endpoints used on server."

    deleted_automatically = False


class TestService(Service):
    class Config:
        private = True

    async def set_mock(
        self,
        name: str,
        args: list,
        description: str | dict[Literal["exception", "return_value"], Any]
    ) -> None:
        if isinstance(description, str):
            scope: dict[str, Any] = {"__name__": "__main__"}
            exec(description, scope)
            try:
                method = scope["mock"]
            except KeyError:
                raise CallError("Your mock declaration must include `def mock` or `async def mock`")
        elif isinstance(description, dict):
            keys = set(description.keys())
            if keys == {"exception"}:
                def method(*args, **kwargs):
                    raise Exception()
            elif keys == {"return_value"}:
                def method(*args, **kwargs):
                    return description["return_value"]
            else:
                raise CallError("Invalid mock declaration")
        else:
            raise CallError("Invalid mock declaration")

        self.middleware.set_mock(name, args, method)

        await self.middleware.call("alert.oneshot_create", "SystemTesting", None)

    async def remove_mock(self, name, args):
        self.middleware.remove_mock(name, args)

    async def add_mock_role(self):
        """
        Adds a MOCK role to role_manager and grants access to test.test1 and test.test2

        This allows testing RBAC against mocked endpoint
        """
        if 'MOCK' in self.middleware.role_manager.roles:
            return

        # There are no STIG requirements specified for MOCK role here because
        # we need to be able to mock methods in CI testing while under STIG restrictions
        self.middleware.role_manager.roles['MOCK'] = Role()
        self.middleware.role_manager.register_method(method_name='test.test1', roles=['MOCK'])
        self.middleware.role_manager.register_method(method_name='test.test2', roles=['MOCK'])

        await self.middleware.call('alert.oneshot_create', 'SystemTesting', None)

    # Dummy methods to mock for internal infrastructure testing (i.e. jobs manager)
    # When these are mocked over they will be available to users with the "MOCK" role.

    async def test1(self):
        pass

    async def test2(self):
        pass
