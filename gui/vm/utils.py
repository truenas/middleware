from freenasUI.middleware.client import client


def vm_enabled():
    with client as c:
        flags = c.call('vm.flags')
        if flags['intel_vmx'] and flags['unrestricted_guest']:
            return True
        else:
            return False
