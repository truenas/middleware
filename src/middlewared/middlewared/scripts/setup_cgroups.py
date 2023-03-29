#!/usr/bin/python3
import contextlib
import os
import re


CGROUP_ROOT_PATH = '/sys/fs/cgroup'
CGROUP_AVAILABLE_CONTROLLERS_PATH = os.path.join(CGROUP_ROOT_PATH, 'cgroup.subtree_control')
RE_CGROUP_CONTROLLERS = re.compile(r'(\w+)\s+')


def get_available_controllers_for_consumption() -> set:
    try:
        with open(CGROUP_AVAILABLE_CONTROLLERS_PATH, 'r') as f:
            return set(RE_CGROUP_CONTROLLERS.findall(f.read()))
    except FileNotFoundError:
        raise Exception(
            'Unable to determine cgroup controllers which are available for consumption as '
            f'{CGROUP_AVAILABLE_CONTROLLERS_PATH!r} does not exist'
        )


def update_available_controllers_for_consumption(to_add_controllers: set) -> set:
    # This will try to update available controllers for consumption and return the current state
    # regardless of the update failing
    with contextlib.suppress(FileNotFoundError, OSError):
        with open(CGROUP_AVAILABLE_CONTROLLERS_PATH, 'w') as f:
            f.write(f'{" ".join(map(lambda s: f"+{s}", to_add_controllers))}')

    return get_available_controllers_for_consumption()


def main():
    # Logic copied over from kubernetes
    # https://github.com/kubernetes/kubernetes/blob/08fbe92fa76d35048b4b4891b41fc6912e689cc7/
    # pkg/kubelet/cm/cgroup_manager_linux.go#L238
    supported_controllers = {'cpu', 'cpuset', 'memory', 'hugetlb', 'pids'}
    system_supported_controllers_path = os.path.join(CGROUP_ROOT_PATH, 'cgroup.controllers')
    try:
        with open(system_supported_controllers_path, 'r') as f:
            available_controllers = set(RE_CGROUP_CONTROLLERS.findall(f.read()))
    except FileNotFoundError:
        raise Exception(
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
        raise Exception(
            f'Missing {", ".join(missing_controllers)!r} cgroup controller(s) '
            'which are required for apps to function'
        )


if __name__ == '__main__':
    main()
