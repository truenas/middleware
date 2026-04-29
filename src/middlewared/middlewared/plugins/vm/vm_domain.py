from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generator

from truenas_pylibvirt import VmDomain as BaseVMDomain
from truenas_pylibvirt import VmDomainConfiguration as BaseVmDomainConfiguration

if TYPE_CHECKING:
    from middlewared.main import Middleware


@dataclass(kw_only=True)
class VmDomainConfiguration(BaseVmDomainConfiguration):
    id: int


class VmDomain(BaseVMDomain):

    def __init__(
        self, configuration: VmDomainConfiguration, middleware: Middleware, start_config: dict[str, Any] | None = None,
    ):
        self.configuration: VmDomainConfiguration = configuration
        super().__init__(configuration)
        self.middleware = middleware
        self.start_config: dict[str, Any] = start_config or {}

    @contextlib.contextmanager
    def run(self) -> Generator[None]:
        self.middleware.call_sync2(
            self.middleware.services.vm.init_guest_vmemory,
            self.configuration.id, self.start_config.get("overcommit", False),
        )
        try:
            yield
        finally:
            self.middleware.call_sync2(
                self.middleware.services.vm.teardown_guest_vmemory, self.configuration.id,
            )
