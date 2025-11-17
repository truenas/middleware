import pytest

from auto_config import ha
from middlewared.test.integration.utils import call, disable_failover
from middlewared.test.integration.utils.audit import expect_audit_method_calls
from middlewared.test.integration.utils.client import truenas_server
from middlewared.test.integration.utils.ssh import ssh


@pytest.fixture(scope='function')
def network_interface_prep():
    """Create dummy interface and clean up when done"""
    dummy_if = "dummy99"
    vlan_name = "vlan999"
    remote_ip = ""
    if ha:
        node_ips = {'A': truenas_server.nodea_ip, 'B': truenas_server.nodeb_ip}
        remote_node = call('failover.call_remote', 'failover.node')
        remote_ip = node_ips[remote_node]

    # Cleanup any existing VLAN from previous test runs
    try:
        call('interface.delete', vlan_name)
        call('interface.commit', {'rollback': False})
    except Exception:
        pass

    # Cleanup any existing dummy interface from previous test runs
    ssh(f"ip link delete {dummy_if}", check=False)
    if ha:
        ssh(f"ip link delete {dummy_if}", ip=remote_ip, check=False)

    try:
        # Create dummy interface
        ssh(f"ip link add {dummy_if} type dummy")
        ssh(f"ip link set {dummy_if} up")
        if ha:
            ssh(f"ip link add {dummy_if} type dummy", ip=remote_ip)
            ssh(f"ip link set {dummy_if} up", ip=remote_ip)

        # Register the dummy interface in the datastore so it survives sync()
        with disable_failover():
            call('interface.update', dummy_if, {
                'ipv4_dhcp': False,
                'ipv6_auto': False,
                'description': 'Test dummy interface',
            })
            call('interface.commit', {'rollback': False})

        yield (dummy_if, vlan_name)

    finally:
        # DELETE VLAN
        try:
            # VLAN delete is usually not necessary, unless
            # the test has a premature failure.
            with disable_failover():
                call('interface.delete', vlan_name)

                # Complete VLAN cleanup: Commit the deletion
                call('interface.commit')
        except Exception:
            # VLAN may not exist
            pass

        # Cleanup dummy interface from datastore AND system
        try:
            with disable_failover():
                call('interface.delete', dummy_if)
                call('interface.commit')
        except Exception:
            # Dummy interface may not be in datastore if test failed early
            pass

        # Final cleanup at OS level
        ssh(f"ip link delete {dummy_if}", check=False)
        if ha:
            ssh(f"ip link delete {dummy_if}", ip=remote_ip, check=False)

        # Make sure we're cleaned up
        ds_list = call('datastore.query', 'network.interfaces', [], {"select": ["int_interface"]})
        query_list = call('interface.query', [], {"select": ["name"]})
        choices = call('interface.choices')
        assert not any(d.get('int_interface') == f'{vlan_name}' for d in ds_list)
        assert not any(d.get('name') == f'{vlan_name}' for d in query_list)
        assert not (vlan_name in choices)
        assert not any(d.get('int_interface') == f'{dummy_if}' for d in ds_list)
        assert not any(d.get('name') == f'{dummy_if}' for d in query_list)
        assert not (dummy_if in choices)


def test_network_globalconfig_audit():
    """
    Test the auditing of network global configuration changes
    """
    initial_network_config = call('network.configuration.config')
    try:
        # UPDATE
        temp_hostname = '-'.join([initial_network_config['hostname'], 'temporary'])
        payload = {
            'hostname': temp_hostname
        }
        with expect_audit_method_calls([{
            'method': 'network.configuration.update',
            'params': [payload],
            'description': 'Update network global configuration',
        }]):
            call('network.configuration.update', payload)
    finally:
        # Restore initial state
        restore_payload = {
            'hostname': initial_network_config['hostname'],
        }
        call('network.configuration.update', restore_payload)


def test_network_interface_audit(network_interface_prep):
    """
    Test the auditing of interface create, update, delete, commit and rollback operations
    """
    dummy_if, vlan_name = network_interface_prep
    vlan_tag = 100
    test_ip = "192.168.99.1"
    test_netmask = 24

    try:
        # CREATE VLAN
        create_payload = {
            'type': 'VLAN',
            'name': vlan_name,
            'vlan_parent_interface': dummy_if,
            'vlan_tag': vlan_tag,
            'ipv4_dhcp': False,
            'ipv6_auto': False,
        }
        with disable_failover():
            with expect_audit_method_calls([{
                'method': 'interface.create',
                'params': [create_payload],
                'description': f'Network interface create {vlan_name}',
            }]):
                result = call('interface.create', create_payload)
                assert result['name'] == vlan_name
                assert result['type'] == 'VLAN'

        # Commit the changes and confirm the audit entry
        with disable_failover():
            with expect_audit_method_calls([{
                'method': 'interface.commit',
                'params': [{'rollback': False}],
                'description': 'Network interface commit pending changes',
            }]):
                call('interface.commit', {'rollback': False})

        # Verify the VLAN was created
        ds_list = call('datastore.query', 'network.interfaces', [], {"select": ["int_interface"]})
        query_list = call('interface.query', [], {"select": ["name"]})
        assert any(d.get('int_interface') == 'dummy99' for d in ds_list)
        assert any(d.get('name') == 'dummy99' for d in query_list)

        vlan_iface = call('interface.get_instance', vlan_name)
        assert vlan_iface is not None, f"VLAN {vlan_name} was not created"

        # UPDATE VLAN with static IP
        update_payload = {
            'aliases': [{
                'type': 'INET',
                'address': test_ip,
                'netmask': test_netmask,
            }]
        }
        with disable_failover():
            with expect_audit_method_calls([{
                'method': 'interface.update',
                'params': [vlan_iface['id'], update_payload],
                'description': f'Network interface update {vlan_name}',
            }]):
                call('interface.update', vlan_iface['id'], update_payload)

        # Rollback the update and confirm the audit entry
        with expect_audit_method_calls([{
            'method': 'interface.rollback',
            'params': [],
            'description': 'Network interface rollback pending changes',
        }]):
            # Rollback does not check for disabled failover
            call('interface.rollback')

    finally:
        # DELETE VLAN
        try:
            with disable_failover():
                with expect_audit_method_calls([{
                    'method': 'interface.delete',
                    'params': [vlan_name],
                    'description': f'Network interface delete {vlan_name}',
                }]):
                    call('interface.delete', vlan_name)

                # Complete VLAN cleanup: Commit the deletion
                call('interface.commit')
        except Exception:
            # VLAN may not exist if test failed early
            pass
