import contextlib
import os
import sys
from time import sleep

apifolder = os.getcwd()
sys.path.append(apifolder)
from middlewared.test.integration.utils import call


@contextlib.contextmanager
def ensure_service_started(service_name, delay=0):
    old_value = call('service.started', service_name)
    if old_value:
        yield
    else:
        call('service.start', service_name)
        if delay:
            sleep(delay)
        try:
            yield
        finally:
            call('service.stop', service_name)
            if delay:
                sleep(delay)


@contextlib.contextmanager
def ensure_service_stopped(service_name, delay=0):
    old_value = call('service.started', service_name)
    if not old_value:
        yield
    else:
        call('service.stop', service_name)
        if delay:
            sleep(delay)
        try:
            yield
        finally:
            call('service.start', service_name)
            if delay:
                sleep(delay)


@contextlib.contextmanager
def ensure_service_enabled(service_name):
    """Ensure that the specified service is enabled.

    When finished restore the service config to the state
    upon call."""
    old_config = call('service.query', [['service', '=', service_name]])[0]
    try:
        if old_config['enable']:
            # No change necessary
            yield
        else:
            # Change necessary, so restore when done
            call('service.update', old_config['id'], {'enable': True})
            try:
                yield
            finally:
                call('service.update', old_config['id'], {'enable': False})
    finally:
        # Also restore the current state (if necessary)
        new_config = call('service.query', [['service', '=', service_name]])[0]
        if new_config['state'] != old_config['state']:
            if old_config['state'] == 'RUNNING':
                call('service.start', service_name)
            else:
                call('service.stop', service_name)


@contextlib.contextmanager
def ensure_service_disabled(service_name):
    """Ensure that the specified service is disabled.

    When finished restore the service config to the state
    upon call."""
    old_config = call('service.query', [['service', '=', service_name]])[0]
    try:
        if not old_config['enable']:
            # No change necessary
            yield
        else:
            # Change necessary, so restore when done
            call('service.update', old_config['id'], {'enable': False})
            try:
                yield
            finally:
                call('service.update', old_config['id'], {'enable': True})
    finally:
        # Also restore the current state (if necessary)
        new_config = call('service.query', [['service', '=', service_name]])[0]
        if new_config['state'] != old_config['state']:
            if old_config['state'] == 'RUNNING':
                call('service.start', service_name)
            else:
                call('service.stop', service_name)
