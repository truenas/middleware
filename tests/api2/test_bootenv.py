from middlewared.test.integration.utils import call, ssh


def test_promote_current_be_datasets():
    var_log = ssh('df | grep /var/log').split()[0]

    snapshot_name = 'snap-1'
    snapshot = f'{var_log}@{snapshot_name}'
    ssh(f'zfs snapshot {snapshot}')
    try:
        clone = 'boot-pool/ROOT/clone'
        ssh(f"zfs clone {snapshot} {clone}")
        try:
            ssh(f'zfs promote {clone}')

            assert ssh(f'zfs get -H -o value origin {var_log}').strip() == f'{clone}@{snapshot_name}'

            call('bootenv.promote_current_be_datasets')

            assert ssh(f'zfs get -H -o value origin {var_log}').strip() == '-'
        finally:
            ssh(f'zfs destroy {clone}')
    finally:
        ssh(f'zfs destroy {snapshot}')
