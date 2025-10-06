import pytest
import subprocess


@pytest.fixture(scope='module')
def systemctl_service_status():
    """ Get and pre-process systemctl output
    YIELD:  systemctl output formatted into a list of strings """

    try:
        raw_list_units = subprocess.run(['systemctl', 'list-units', '--all', '--type=service'], capture_output=True)
        svc_data = raw_list_units.stdout.decode().strip().splitlines()
        yield svc_data
    except Exception:
        pass


def process_svc_data(svc_entry: str):
    """ Process a service entry
    RETURN: dictionary {alarm: None | 'set', status: (LOAD, ACTIVE, SUB)} """

    assert svc_entry is not None
    assert svc_entry != ""

    retval = {"alarm": None, "status": ()}
    retval["alarm"] = None if svc_entry[0] == "" else "active"

    svc_parts = svc_entry[1:].split()
    retval["status"] = (svc_parts[1], svc_parts[2], svc_parts[3])

    return retval


@pytest.mark.parametrize('svc_name,expected', [
    ("nscd", {"state": "listed", "alarm": None, "status": ("loaded", "active", "running")}),
    ("rpcbind", {"state": "listed", "alarm": None, "status": ("loaded", "inactive", "dead")}),
    ("systemd-sysusers", {"state": "listed", "alarm": None, "status": ("loaded", "inactive", "dead")}),
])
def test__systemctl_unit_state(systemctl_service_status, svc_name, expected):
    """ Confirm status of services at boot """

    svc_data = systemctl_service_status
    svc_entry = [svc for svc in svc_data if svc_name in svc]

    if expected['state'] == 'listed':
        assert svc_entry != [], f"Expected to find {svc_name}"
        assert len(svc_entry) == 1

        svc = process_svc_data(svc_entry[0])
        assert svc['status'] == expected['status'], \
            f"{svc_name}: expected {expected['status']}, but found {svc['status']}"
    else:
        assert svc_entry == []
