import contextlib
import datetime
import re
import tempfile

import pytest
from assets.websocket.pool import zvol
from assets.websocket.service import ensure_service_started
from auto_config import password, pool_name, user
from functions import send_file

from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.client import truenas_server

SERVICE_NAME = 'iscsitarget'
ZVOL1_NAME = 'PYSCSTADMIN_ZVOL1'
ZVOL1_MB = 100
ZVOL2_NAME = 'PYSCSTADMIN_ZVOL2'
ZVOL2_MB = 200

SUSPEND_LOAD_SECONDS = 5
NOSUSPEND_LOAD_SECONDS = 20
SCSTADMIN_LOAD_SECONDS = 40

CHANGES_RE = re.compile(r"Done, (\d+) change\(s\) made.")
REMOVE_LUN_RE = re.compile(r"Removing LUN (\d+) from driver/target 'copy_manager/copy_manager_tgt': done.")

DEVICE_TEST1 = """
    DEVICE test1 {{
        filename /dev/zvol/{pool}/PYSCSTADMIN_ZVOL1
        blocksize 512
        read_only 0
        usn 038f0453d897b6a
        naa_id 0x6589cfc000000d9f095196d274132652
        prod_id "iSCSI Disk"
        rotational 0
        t10_vend_id TrueNAS
        t10_dev_id 038f0453d897b6a
        threads_num 32
    }}
""".format(pool=pool_name)

DEVICE_TEST1_NOT_ACTIVE = """
    DEVICE test1 {{
        filename /dev/zvol/{pool}/PYSCSTADMIN_ZVOL1
        blocksize 512
        read_only 0
        usn 038f0453d897b6a
        naa_id 0x6589cfc000000d9f095196d274132652
        prod_id "iSCSI Disk"
        rotational 0
        t10_vend_id TrueNAS
        t10_dev_id 038f0453d897b6a
        active 0
        threads_num 32
    }}
""".format(pool=pool_name)

DEVICE_TEST1_ALT = """
    DEVICE test1 {{
        filename /dev/zvol/{pool}/PYSCSTADMIN_ZVOL1
        blocksize 512
        read_only 0
        usn 038f0453d89beef
        naa_id 0x6589cfc000000d9f095196d274132642
        prod_id "iSCSI disk"
        rotational 0
        t10_vend_id TrueNAS2
        t10_dev_id 038f0453d89beef
        threads_num 32
    }}
""".format(pool=pool_name)

DEVICE_TEST2 = """
    DEVICE test2 {{
        filename /dev/zvol/{pool}/PYSCSTADMIN_ZVOL2
        blocksize 512
        read_only 0
        usn e7e8aa169c7a280
        naa_id 0x6589cfc00000038f4937570ed9a25ab6
        prod_id "iSCSI Disk"
        rotational 0
        t10_vend_id TrueNAS
        t10_dev_id e7e8aa169c7a280
        threads_num 32
    }}
""".format(pool=pool_name)


CONF_ONE_DEVICE = """
HANDLER vdisk_fileio {{
}}
HANDLER vdisk_blockio {{
    {device1}
}}
TARGET_DRIVER copy_manager {{
        TARGET copy_manager_tgt {{
                LUN 0 test1
        }}
}}
TARGET_DRIVER iscsi {{
    enabled 1
    link_local 0

}}
""".format(device1=DEVICE_TEST1)

CONF_ONE_DEVICE_ALT = """
HANDLER vdisk_fileio {{
}}
HANDLER vdisk_blockio {{
    {device1}
}}
TARGET_DRIVER copy_manager {{
        TARGET copy_manager_tgt {{
                LUN 0 test1
        }}
}}
TARGET_DRIVER iscsi {{
    enabled 1
    link_local 0

}}
""".format(device1=DEVICE_TEST1_ALT)

CONF_TWO_DEVICES = """
HANDLER vdisk_fileio {{
}}
HANDLER vdisk_blockio {{
    {device1}
    {device2}
}}
TARGET_DRIVER copy_manager {{
        TARGET copy_manager_tgt {{
                LUN 0 test1
                LUN 1 test2
        }}
}}
TARGET_DRIVER iscsi {{
    enabled 1
    link_local 0

}}
""".format(device1=DEVICE_TEST1, device2=DEVICE_TEST2)

TARGET_TEST1 = r"""
    TARGET iqn.2005-10.org.freenas.ctl:test1 {
        rel_tgt_id 1
        enabled 1
        per_portal_acl 1

        GROUP security_group {
            INITIATOR *\#*

            LUN 0 test1
        }
    }
"""

TARGET_TEST1_CHAP = r"""
    TARGET iqn.2005-10.org.freenas.ctl:test1 {
        rel_tgt_id 1
        enabled 1
        per_portal_acl 1
        IncomingUser "testuser testpassword1234"

        GROUP security_group {
            INITIATOR *\#*

            LUN 0 test1
        }
    }
"""

TARGET_TEST1_CHAP2 = r"""
    TARGET iqn.2005-10.org.freenas.ctl:test1 {
        rel_tgt_id 1
        enabled 1
        per_portal_acl 1
        IncomingUser "testuser testpassword1234"
        IncomingUser "testuser2 otherpass1234"

        GROUP security_group {
            INITIATOR *\#*

            LUN 0 test1
        }
    }
"""

TARGET_TEST1_TWO_LUNS = r"""
    TARGET iqn.2005-10.org.freenas.ctl:test1 {
        rel_tgt_id 1
        enabled 1
        per_portal_acl 1

        GROUP security_group {
            INITIATOR *\#*

            LUN 0 test1
            LUN 1 test2

        }
    }
"""

TARGET_TEST2 = r"""
    TARGET iqn.2005-10.org.freenas.ctl:test2 {
        rel_tgt_id 2
        enabled 1
        per_portal_acl 1

        GROUP security_group {
            INITIATOR *\#*

            LUN 0 test2
        }
    }
"""

CONF_ONE_DEVICE_ONE_TARGET = """
HANDLER vdisk_fileio {{
}}
HANDLER vdisk_blockio {{
    {device1}
}}
TARGET_DRIVER copy_manager {{
        TARGET copy_manager_tgt {{
                LUN 0 test1
        }}
}}
TARGET_DRIVER iscsi {{
    enabled 1
    link_local 0

    {target1}
}}
""".format(device1=DEVICE_TEST1, target1=TARGET_TEST1)

CONF_ONE_DEVICE_ONE_TARGET_CHAP = """
HANDLER vdisk_fileio {{
}}
HANDLER vdisk_blockio {{
    {device1}
}}
TARGET_DRIVER copy_manager {{
        TARGET copy_manager_tgt {{
                LUN 0 test1
        }}
}}
TARGET_DRIVER iscsi {{
    enabled 1
    link_local 0

    {target1}
}}
""".format(device1=DEVICE_TEST1, target1=TARGET_TEST1_CHAP)

CONF_ONE_DEVICE_ONE_TARGET_CHAP2 = """
HANDLER vdisk_fileio {{
}}
HANDLER vdisk_blockio {{
    {device1}
}}
TARGET_DRIVER copy_manager {{
        TARGET copy_manager_tgt {{
                LUN 0 test1
        }}
}}
TARGET_DRIVER iscsi {{
    enabled 1
    link_local 0

    {target1}
}}
""".format(device1=DEVICE_TEST1, target1=TARGET_TEST1_CHAP2)


CONF_TWO_DEVICES_ONE_TARGET = """
HANDLER vdisk_fileio {{
}}
HANDLER vdisk_blockio {{
    {device1}
    {device2}
}}
TARGET_DRIVER copy_manager {{
        TARGET copy_manager_tgt {{
                LUN 0 test1
                LUN 1 test2
        }}
}}
TARGET_DRIVER iscsi {{
    enabled 1
    link_local 0

    {target1}
}}
""".format(device1=DEVICE_TEST1, device2=DEVICE_TEST2, target1=TARGET_TEST1_TWO_LUNS)

CONF_TWO_DEVICES_TWO_TARGETS = """
HANDLER vdisk_fileio {{
}}
HANDLER vdisk_blockio {{
    {device1}
    {device2}
}}
TARGET_DRIVER copy_manager {{
        TARGET copy_manager_tgt {{
                LUN 0 test1
                LUN 1 test2
        }}
}}
TARGET_DRIVER iscsi {{
    enabled 1
    link_local 0

    {target1}
    {target2}
}}
""".format(
    device1=DEVICE_TEST1,
    device2=DEVICE_TEST2,
    target1=TARGET_TEST1,
    target2=TARGET_TEST2,
)

ALUA_ACTIVE = """
cluster_name HA
HANDLER dev_disk {{
}}
TARGET_DRIVER copy_manager {{
        TARGET copy_manager_tgt {{
                LUN 0 test1
        }}
}}

HANDLER vdisk_fileio {{
}}
HANDLER vdisk_blockio {{
    {device1}
}}

TARGET_DRIVER iscsi {{
    internal_portal 169.254.10.1
    enabled 1
    link_local 0

    {target1}
    TARGET iqn.2005-10.org.freenas.ctl:HA:test1 {{
        allowed_portal 169.254.10.1
        rel_tgt_id 32001
        enabled 1
        forward_dst 1
        aen_disabled 1
        forwarding 1

        LUN 0 test1
    }}
}}

DEVICE_GROUP targets {{
        DEVICE test1

        TARGET_GROUP controller_A {{
                group_id 101
                state active

                TARGET iqn.2005-10.org.freenas.ctl:test1
        }}

        TARGET_GROUP controller_B {{
                group_id 102
                state nonoptimized

                TARGET iqn.2005-10.org.freenas.ctl:HA:test1
        }}
}}
""".format(
    device1=DEVICE_TEST1,
    target1=TARGET_TEST1,
)


@pytest.fixture(scope='module')
def iscsi_running():
    with ensure_service_started(SERVICE_NAME, 3):
        yield


@pytest.fixture(scope='module')
def zvol1():
    with zvol(ZVOL1_NAME, ZVOL1_MB, pool_name) as config:
        yield config


@pytest.fixture(scope='module')
def zvol2():
    with zvol(ZVOL2_NAME, ZVOL2_MB, pool_name) as config:
        yield config


@pytest.fixture
def filepath20mb():
    filepath = f'/mnt/{pool_name}/FILE20MB'
    ssh(f"dd if=/dev/zero of={filepath} bs=1M count=20")
    try:
        yield filepath
    finally:
        ssh(f'rm {filepath}')


@contextlib.contextmanager
def conf(text):
    with tempfile.NamedTemporaryFile(prefix='scst_', suffix='.conf', mode='w') as f:
        f.write(text)
        f.flush()
        send_file(f.name, f.name, user, password, truenas_server.ip)
        try:
            yield f.name
        finally:
            ssh(f'rm -f {f.name}')


def check_config(scst_conf_filepath):
    results = ssh(
        f'scstadmin -config {scst_conf_filepath} -force -noprompt',
        complete_response=True,
        check=False,
    )
    assert results['returncode'] == 0, f"scstadmin failed with: {results['stderr']}"

    # Want to ensure no significant changes are applied
    # First check for no changes at all.
    if 'Done, 0 change(s) made.' in results['stdout']:
        return

    # We don't care if copy manager tgt removals are made.  Even
    # the perl scstadmin has some hysteresis in this regard.
    if result := CHANGES_RE.search(results['stdout']):
        change_count = int(result.group(1))
        if len(re.findall(REMOVE_LUN_RE, results['stdout'])) == change_count:
            return

    assert False, f"Expected no changes, but got: {results['stdout']}"


def apply_and_check_config(scst_conf_filepath):
    ssh(f'pyscstadmin -config {scst_conf_filepath}')
    check_config(scst_conf_filepath)


@contextlib.contextmanager
def check_time_limit(seconds, description):
    start_time = datetime.datetime.now()
    yield
    delta = datetime.datetime.now() - start_time
    assert delta.seconds < seconds
    print(f"{description}: {float(delta.total_seconds()):.2f}")


def test__devices(iscsi_running, zvol1, zvol2):
    try:
        with conf(CONF_ONE_DEVICE) as scst_conf_one_device:
            # Start off by writing one device to the config
            apply_and_check_config(scst_conf_one_device)

            # Add a second device
            with conf(CONF_TWO_DEVICES) as scst_conf_two_devices:
                apply_and_check_config(scst_conf_two_devices)

            # Drop back to one device
            apply_and_check_config(scst_conf_one_device)

            # Tweak some of the values
            with conf(CONF_ONE_DEVICE_ALT) as scst_conf_one_device_alt:
                apply_and_check_config(scst_conf_one_device_alt)

            # And back again
            apply_and_check_config(scst_conf_one_device)
    finally:
        ssh('pyscstadmin -clear_config')


def test__targets(iscsi_running, zvol1, zvol2):
    try:
        with conf(CONF_ONE_DEVICE_ONE_TARGET) as one_device_one_target:
            apply_and_check_config(one_device_one_target)

            with conf(CONF_TWO_DEVICES_ONE_TARGET) as filename:
                apply_and_check_config(filename)

            with conf(CONF_TWO_DEVICES_TWO_TARGETS) as filename:
                apply_and_check_config(filename)

            with conf(CONF_ONE_DEVICE_ONE_TARGET_CHAP) as chap_filename:
                apply_and_check_config(chap_filename)

                with conf(CONF_ONE_DEVICE_ONE_TARGET_CHAP2) as chap2_filename:
                    apply_and_check_config(chap2_filename)

                    apply_and_check_config(one_device_one_target)

                    apply_and_check_config(chap2_filename)

                apply_and_check_config(chap_filename)

            apply_and_check_config(one_device_one_target)

    finally:
        ssh('pyscstadmin -clear_config')


def test__alua(iscsi_running, zvol1, zvol2):
    try:
        with conf(ALUA_ACTIVE) as active_filename:
            apply_and_check_config(active_filename)

            disks = call('disk.get_unused')
            if disks:
                disk_hctl = disks[0]['hctl']

                ALUA_STANDBY = r"""
                cluster_name HA
                HANDLER dev_disk {{
                        DEVICE {disk}
                }}
                TARGET_DRIVER copy_manager {{
                        TARGET copy_manager_tgt {{
                                LUN 0 {disk}
                        }}
                }}
                HANDLER vdisk_fileio {{
                }}
                HANDLER vdisk_blockio {{
                    {device1}
                }}
                TARGET_DRIVER iscsi {{
                    internal_portal 169.254.10.1
                    enabled 1
                    link_local 0
                    TARGET iqn.2005-10.org.freenas.ctl:test1 {{
                        rel_tgt_id 1
                        enabled 1
                        per_portal_acl 1
                        GROUP security_group {{
                            INITIATOR *\#*
                            LUN 0 {disk}
                        }}
                    }}
                }}
                DEVICE_GROUP targets {{
                        DEVICE {disk}
                        TARGET_GROUP controller_B {{
                                group_id 102
                                state active
                                TARGET iqn.2005-10.org.freenas.ctl:alt:test1 {{
                                   rel_tgt_id 32001
                                }}
                        }}
                        TARGET_GROUP controller_A {{
                                group_id 101
                                state nonoptimized
                                TARGET iqn.2005-10.org.freenas.ctl:test1
                        }}
                }}
                """.format(device1=DEVICE_TEST1_NOT_ACTIVE, disk=disk_hctl)
                with conf(ALUA_STANDBY) as standby_filename:
                    apply_and_check_config(standby_filename)

    finally:
        ssh('pyscstadmin -clear_config')


def _device(filepath, number):
    digits = f"{number:04d}"
    return r"""
        DEVICE test{digits} {{
            filename {filepath}
            blocksize 512
            read_only 0
            usn 7b92740fc6e{digits}
            naa_id 0x6589cfc000000fd4fd8e289424d0{digits}
            prod_id "iSCSI Disk"
            rotational 0
            t10_vend_id TrueNAS
            t10_dev_id 7b92740fc6e{digits}
        }}
    """.format(digits=digits, filepath=filepath)


def test__many_file_based_targets(iscsi_running, filepath20mb):
    """Test loading many extents and targets"""
    # It appears that SCST will object if we try to reuse the same
    # ZVOL under multiple extents.  OTOH, no such objection to the
    # dangerous behavior of doing the same with a file.  So, just to
    # test pyscstadmin we will create many extents/targets all using
    # the same file.  We're not planning on writing data and this will
    # save time wrt test setup/teardown.

    COUNT = 101

    def _target(number):
        digits = f"{number:04d}"
        return r"""
        TARGET iqn.2005-10.org.freenas.ctl:test{digits} {{
            rel_tgt_id {rel_tgt_id}
            enabled 1
            per_portal_acl 1

            GROUP security_group {{
                INITIATOR *\#*

                LUN 0 test{digits}
            }}
        }}
        """.format(digits=digits, rel_tgt_id=number)

    lines = [r'HANDLER vdisk_fileio {']
    for i in range(1, COUNT):
        lines.append(_device(filepath20mb, i))
    lines.append(r'}')

    lines.append(r'HANDLER vdisk_blockio {')
    lines.append(r'}')

    # Do not force copy_manager targets
    # In real-world these are only populated automatically and
    # the same values written to scst.conf (HA only).  In this
    # test environment this would cause all the LUNs to be
    # rewritten.  Let's avoid.
    # target_driver = r"""
    #     TARGET_DRIVER copy_manager {
    #         TARGET copy_manager_tgt {
    # """
    # lines.append(target_driver)
    # for i in range(1, COUNT):
    #     lines.append(f'            LUN {i-1} test{i:04d}')
    # lines.append(r'    }')
    # lines.append(r'}')

    target_driver = r"""
        TARGET_DRIVER iscsi {
            enabled 1
            link_local 0
    """
    lines.append(target_driver)
    for i in range(1, COUNT):
        lines.append(_target(i))
    lines.append(r'}')

    CONF_MANY_TARGETS = '\n'.join(lines)
    try:
        with conf(CONF_MANY_TARGETS) as many_targets:
            # We want to be sure that the config loads in a reasonable amount of time: suspend
            ssh('pyscstadmin -clear_config')
            with check_time_limit(SUSPEND_LOAD_SECONDS, f"LOAD {COUNT-1} using pyscstadmin -suspend"):
                ssh(f'pyscstadmin -config {many_targets} -suspend 5')

            # We want to be sure that the config loads in a reasonable amount of time: no suspend
            ssh('pyscstadmin -clear_config')
            with check_time_limit(NOSUSPEND_LOAD_SECONDS, f"LOAD {COUNT-1} using pyscstadmin"):
                ssh(f'pyscstadmin -config {many_targets}')

            # Do the old scstadmin mechanism too
            ssh('pyscstadmin -clear_config')
            with check_time_limit(SCSTADMIN_LOAD_SECONDS, f"LOAD {COUNT-1} using scstadmin"):
                ssh(f'scstadmin -config {many_targets} -force -noprompt')

    finally:
        ssh('pyscstadmin -clear_config')
