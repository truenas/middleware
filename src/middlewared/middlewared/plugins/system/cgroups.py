import os

from middlewared.service import CallError, private, Service

from .utils import (
    CGROUP_ROOT_PATH, RE_CGROUP_CONTROLLERS, get_available_controllers_for_consumption,
    update_available_controllers_for_consumption,
)


class SystemService(Service):

    class Config:
        namespace = 'system'

    @private
    def ensure_cgroups_are_setup(self):
        # Logic copied over from kubernetes
        # https://github.com/kubernetes/kubernetes/blob/08fbe92fa76d35048b4b4891b41fc6912e689cc7/
        # pkg/kubelet/cm/cgroup_manager_linux.go#L238
        supported_controllers = {'cpu', 'cpuset', 'memory', 'hugetlb', 'pids'}
        system_supported_controllers_path = os.path.join(CGROUP_ROOT_PATH, 'cgroup.controllers')
        try:
            with open(system_supported_controllers_path, 'r') as f:
                available_controllers = set(RE_CGROUP_CONTROLLERS.findall(f.read()))
        except FileNotFoundError:
            raise CallError(
                'Unable to determine available cgroup controllers as '
                f'{system_supported_controllers_path!r} does not exist'
            )

        needed_controllers = supported_controllers & available_controllers
        available_controllers_for_consumption = get_available_controllers_for_consumption()
        if missing_controllers := needed_controllers - available_controllers_for_consumption:
            # If we have missing controllers, lets try adding them to subtree control
            available_controllers_for_consumption = update_available_controllers_for_consumption(missing_controllers)

        missing_controllers = needed_controllers - available_controllers_for_consumption
        if missing_controllers:
            raise CallError(
                f'Missing {", ".join(missing_controllers)!r} cgroup controller(s) '
                'which are required for apps to function'
            )
