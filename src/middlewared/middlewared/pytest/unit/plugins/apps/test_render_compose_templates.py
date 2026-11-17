import errno
import os
import subprocess
import unittest.mock

import pytest

from middlewared.plugins.apps.ix_apps.lifecycle import render_compose_templates
from middlewared.service import CallError


@unittest.mock.patch('middlewared.plugins.apps.ix_apps.lifecycle.run')
def test_render_compose_templates_success(mock_run):
    mock_run.return_value = subprocess.CompletedProcess([], 0, stdout='', stderr='')
    render_compose_templates('/mnt/.ix-apps/app_configs/plex/versions/1.1.13', '/tmp/values.yaml')
    mock_run.assert_called_once_with([
        '/usr/bin/apps_render_app', 'render', '--path', '/mnt/.ix-apps/app_configs/plex/versions/1.1.13',
        '--values', '/tmp/values.yaml',
    ])


@pytest.mark.parametrize('returncode, stderr, errmsg, error_number', [
    (
        os.EX_CONFIG,
        'Invalid port [0]. Valid ports are between 1 and 65535\n',
        'Invalid port [0]. Valid ports are between 1 and 65535',
        errno.EINVAL,
    ),
    (1, 'Traceback\n', 'Failed to render compose templates: Traceback\n', errno.EFAULT),
])
@unittest.mock.patch('middlewared.plugins.apps.ix_apps.lifecycle.run')
def test_render_compose_templates_failure(mock_run, returncode, stderr, errmsg, error_number):
    mock_run.return_value = subprocess.CompletedProcess([], returncode, stdout='', stderr=stderr)

    with pytest.raises(CallError) as e:
        render_compose_templates('/mnt/.ix-apps/app_configs/plex/versions/1.1.13', '/tmp/values.yaml')

    assert e.value.errmsg == errmsg
    assert e.value.errno == error_number
