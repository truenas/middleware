from functions import wait_on_job
from middlewared.test.integration.utils import call, ssh

def test_get_default_environment_and_make_new_one():
    active_be_id = call('bootenv.query', [['activated', '=', True]], {'get': True})['id']

    # create duplicate name to test failure
    payload = {"name": active_be_id, "source": active_be_id}
    results = call("bootenv.create", payload)
    assert results == f'[EEXIST] bootenv_create.name: The name "{active_be_id}" already exists'

    # create new bootenv and activate it
    payload = {"name": "bootenv01", "source": active_be_id}
    call("bootenv.create", payload)

    assert len(call('bootenv.query', [['name', '=', 'bootenv01']]).json()) == 1
    call("bootenv.activate", "bootenv01")


# Update tests
def test_cloning_a_new_boot_environment():
    payload = {"name": "bootenv02", "source": "bootenv01"}
    results = call("bootenv.create", payload)

    results = call("bootenv.activate", "bootenv02")


def test_change_boot_environment_name_and_attributes():
    payload = {"name": "bootenv03"}
    results = call("bootenv.update", "bootenv01", payload)

    payload = {"keep": True}
    results = call("bootenv.set_attribute", "bootenv03", payload)

    results = call("bootenv.activate", "bootenv03")


# Delete tests
def test_removing_a_boot_environment_02():
    job_id = call("bootenv.delete", "bootenv02")

    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS'


def test_activate_original_bootenv():
    be_id = call('bootenv.query', [['name', '!=', 'bootenv03']])[0]["id"]
    call("bootenv.activate", be_id)


def test_removing_a_boot_environment_03():
    payload = {'keep': False}
    results = call('bootenv.set_attribute', 'bootenv03', payload)

    results = call('bootenv.delete', 'bootenv03')
    job_id = results

    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_promote_current_be_datasets():
    var_log = ssh("df | grep /var/log").split()[0]

    snapshot_name = "snap-1"
    snapshot = f"{var_log}@{snapshot_name}"
    ssh(f"zfs snapshot {snapshot}")
    try:
        clone = "boot-pool/ROOT/clone"
        ssh(f"zfs clone {snapshot} {clone}")
        try:
            ssh(f"zfs promote {clone}")

            assert ssh(f"zfs get -H -o value origin {var_log}").strip() == f"{clone}@{snapshot_name}"

            call("bootenv.promote_current_be_datasets")

            assert ssh(f"zfs get -H -o value origin {var_log}").strip() == "-"
        finally:
            ssh(f"zfs destroy {clone}")
    finally:
        ssh(f"zfs destroy {snapshot}")
