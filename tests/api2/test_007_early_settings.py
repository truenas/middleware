import stat

from middlewared.test.integration.utils import call

# this is found in middlewared.plugins.sysctl.sysctl_info
# but the client running the tests isn't guaranteed to have
# the middlewared application installed locally
DEFAULT_ARC_MAX_FILE = '/var/run/middleware/default_arc_max'


def test_sysctl_arc_max_is_set():
    """Middleware should have created this file and written a number
    to it early in the boot process. That's why we check it here in
    this test so early"""
    assert call('filesystem.stat', DEFAULT_ARC_MAX_FILE)['size']


def test_data_dir_perms():
    default_dir_mode = 0o700
    default_file_mode = 0o600
    data_subsystems_mode = 0o755

    def check_permissions(directory):
        contents = call('filesystem.listdir', directory)
        for i in contents:
            i_path = i['path']
            i_mode = stat.S_IMODE(i['mode'])
            if i['type'] == 'DIRECTORY':
                assert i_mode == data_subsystems_mode, \
                    f'Incorrect permissions for {i_path}, should be {stat.S_IMODE(data_subsystems_mode):#o}'
                check_permissions(i_path)

    # Check perms of `/data`
    data_dir_mode = call('filesystem.stat', '/data')['mode']
    assert stat.S_IMODE(data_dir_mode) == data_subsystems_mode, \
        f'Incorrect permissions for /data, should be {stat.S_IMODE(data_subsystems_mode):#o}'

    # Check perms of contents `/data`
    data_contents = call('filesystem.listdir', '/data')
    for item in data_contents:
        item_path = item['path']
        if item_path == '/data/subsystems':
            continue
        item_mode = stat.S_IMODE(item['mode'])
        desired_mode = default_dir_mode if item['type'] == 'DIRECTORY' else default_file_mode
        assert item_mode == desired_mode, \
            f'Incorrect permissions for {item_path}, should be {stat.S_IMODE(desired_mode):#o}'

    # Check perms of `/data/subsystems`
    ss_dir_mode = stat.S_IMODE(call('filesystem.stat', '/data/subsystems')['mode'])
    assert ss_dir_mode == data_subsystems_mode, \
        f'Incorrect permissions for /data/subsystems, should be {stat.S_IMODE(data_subsystems_mode):#o}'

    # Check perms of contents of `/data/subsystems` recursively
    check_permissions('/data/subsystems')
