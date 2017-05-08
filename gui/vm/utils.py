from freenasUI.middleware.client import client


def vm_enabled():
    with client as c:
        flags = c.call('vm.flags')
        if flags.get('intel_vmx'):
            return True
        elif flags.get('amd_rvi'):
            return True
        else:
            return False
