from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

from truenas_pylibvirt import VmDomain as BaseVMDomain, VmDomainConfiguration as BaseVmDomainConfiguration


if TYPE_CHECKING:
    from middlewared.main import Middleware


@dataclass(kw_only=True)
class VmDomainConfiguration(BaseVmDomainConfiguration):
    id: int


class VmDomain(BaseVMDomain):

    def __init__(self, configuration: VmDomainConfiguration, middleware: Middleware, start_config: dict | None = None):
        self.configuration: VmDomainConfiguration = configuration
        super().__init__(configuration)
        self.middleware = middleware
        self.start_config = start_config or {}

    @contextlib.contextmanager
    def run(self):
        # Allocate memory before starting VM
        self.middleware.call_sync(
            'vm.init_guest_vmemory', self.configuration.id, self.start_config.get('overcommit', False)
        )
        try:
            yield
        finally:
            self.middleware.call_sync('vm.teardown_guest_vmemory', self.configuration.id)
