
# To use this:
# from . import Avatar
# os_type = Avatar()

# We may want to have more
# platform-specific stuff.

try:
    import sys
    sys.path.append("/usr/local/www")
    from freenasUI.common.system import get_sw_name
    _os_type = get_sw_name()
except:
    _os_type = "FreeNAS"

def Avatar():
    return _os_type

